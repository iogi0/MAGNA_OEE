"""FastAPI aplikácia (ARCHITECTURE §7, §10.5).

- `create_app(settings)` — továreň; testy si vytvárajú vlastné `Settings` (nikdy nie `data/local/oee.db`).
- `lifespan`: priečinok a schéma DB, seed číselníka (idempotentný), katalóg; pri vypnutí `engine.dispose()`.
- Šablóny `TemplateResponse(request, ...)`, assety iba lokálne z `/static/vendor` (demo offline).
- Jedno rozhranie bez rozdelenia na operátora a manažéra (PLANNING D14).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import quote
from uuid import uuid4

from fastapi import BackgroundTasks, Depends, FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from oee import __version__
from oee.ai.client import Generator, OllamaClient
from oee.catalog.loader import Catalog, load_catalog, load_example_settings, load_stations
from oee.config import Settings, get_settings
from oee.contracts.shift_analytics import ShiftAnalytics
from oee.domain.shift_model import MINUTES_PER_HOUR, build_shift_plan
from oee.persistence.db import init_db, make_engine, make_session_factory
from oee.persistence.models import DefectType, IssueType, Shift
from oee.persistence.seed import seed_codebook
from oee.services.ai_orchestrator import (
    AiConfig,
    AiJob,
    AiState,
    link_job,
    lookup,
    run_job,
    shift_summary_job,
)
from oee.services.analytics import PeriodType, build_period, build_shift
from oee.services.analytics import ShiftNotFound as AnalyticsShiftNotFound
from oee.services.codebook import CodeError, add_code, code_categories, get_active_codes, list_codes
from oee.services.history import (
    TOP_SIZE,
    TREND_ARROWS,
    PeriodError,
    category_losses,
    latest_shift_date,
    linked_defects_by_stop,
    month_key,
    neighbour_periods,
    parse_month,
    parse_week,
    ranking_view,
    series_payload,
    shift_history,
    top10,
    week_key,
)
from oee.services.import_template import build_example_workbook
from oee.services.importer import DatasetError, ImportResult, import_excel
from oee.services.line_xray import LineXray, build_line_xray
from oee.services.link_view import link_matrix, link_occurrences
from oee.services.reporting import (
    NoActiveShiftModel,
    ShiftNotFound,
    ShiftOverview,
    effective_status,
    get_shift,
    hour_state,
    open_shift,
    save_hour,
    shift_overview,
)
from oee.services.shift_models import activate_shift_model, get_active_model
from oee.services.shift_view import (
    IssueSort,
    ParetoMode,
    bucket_label,
    charts_payload,
    group_issues,
    pareto,
    sorted_issues,
    status_label,
)
from oee.web.forms import HourForm, ModelForm, empty_form, form_from_config, parse_hour_form, parse_model_form

WEB_DIR = Path(__file__).resolve().parent
logger = logging.getLogger(__name__)
WEEKDAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
# kontroly TASK §11.7 po zmenách (kľúče z `services.importer`) → popis v UI
CHECK_LABELS = {
    "plan_min": "Planned minutes",
    "downtime": "Downtime minutes",
    "balance_s": "Time balance",
    "kontrola_ks": "Piece balance",
    "kpi_range": "KPI in range",
    "kontrola_zmien": "Shift summary sheet",
    "model_snapshot": "Shift model snapshot",
}
SAVED_MESSAGES = {"model": "Shift model saved", "code": "Problem code added"}

NAV = (
    ("/report", "Hourly Reporting"),
    ("/shift", "Shift Dashboard"),
    ("/history", "Production History"),
    ("/correlations", "Correlations"),
    ("/line", "Line X-Ray"),
    ("/settings", "Settings"),
    ("/import", "Import"),
)

templates = Jinja2Templates(directory=WEB_DIR / "templates")


def _num(value: float) -> str:
    """Číslo na zobrazenie: max. 2 desatinné miesta bez koncových núl (iba prezentácia)."""
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _pct(share: float) -> str:
    """Podiel 0–1 ako percentá s 1 desatinným miestom (iba prezentácia)."""
    return f"{share * 100:.1f} %"


templates.env.filters["num"] = _num
templates.env.filters["pct"] = _pct


def _hours(minutes: int) -> int:
    """Dĺžka zmeny v celých hodinách (iba prezentácia)."""
    return minutes // MINUTES_PER_HOUR


templates.env.filters["hours"] = _hours


def _signed(value: float) -> str:
    """Číslo so znamienkom (typografické mínus) — iba prezentácia."""
    return f"−{_num(-value)}" if value < 0 else _num(value)


def _pp(value: float) -> str:
    """Odchýlka v percentuálnych bodoch, 1 desatinné miesto."""
    return f"{'−' if value < 0 else '+'}{abs(value):.1f} p.p."


def _pct2(share: float) -> str:
    return f"{share * 100:.2f} %"


templates.env.filters["signed"] = _signed
templates.env.filters["pp"] = _pp
templates.env.filters["pct2"] = _pct2


def _num1(value: float) -> str:
    """Odhad na 1 desatinné miesto (zmätky navyše, súhrnný vplyv väzby) — iba prezentácia."""
    text = f"{value:.1f}".rstrip("0").rstrip(".")
    return "0" if text == "-0" else text


templates.env.filters["num1"] = _num1


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


def _page(request: Request, template: str, title: str, **context: object) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        template,
        {
            "title": title,
            "nav": NAV,
            "path": request.url.path,
            "version": __version__,
            "line": request.app.state.settings.line_id,
            # verzia CSS podľa času zmeny súboru → prehliadač nepoužije zastaraný štýl z cache
            "css_version": int((WEB_DIR / "static" / "app.css").stat().st_mtime),
            **context,
        },
    )


def _utc_now() -> datetime:
    """Čas auditu v naivnom UTC (ARCHITECTURE §10.3)."""
    return datetime.now(UTC).replace(tzinfo=None)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = make_engine(settings.db_path)
        init_db(engine)
        factory = make_session_factory(engine)
        catalog = load_catalog()
        with factory() as session:
            seed_codebook(session, catalog)
            session.commit()
        app.state.engine = engine
        app.state.session_factory = factory
        app.state.catalog = catalog
        # lokálne AI (iba 127.0.0.1); bez Ollama aplikácia funguje s fallback textami (CLAUDE.md bod 3)
        app.state.ai_client = (
            OllamaClient(settings.ollama_url, settings.ollama_model, timeout_s=settings.ai_timeout_s)
            if settings.ai_enabled
            else None
        )
        try:
            yield
        finally:
            engine.dispose()  # Windows: uvoľní súbor DB

    app = FastAPI(title="AI OEE Improvement Engine", version=__version__, lifespan=lifespan)
    app.state.settings = settings
    app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse("/report", status_code=303)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    # --- lokálne AI (P0-24) -------------------------------------------------------------------------

    def _ai_config() -> AiConfig:
        client = app.state.ai_client
        model = client.model if isinstance(client, OllamaClient) else settings.ollama_model
        # zaseknutý pending = viac ako 2 × timeout (ARCHITECTURE §10.6)
        return AiConfig(
            model=model, lang=settings.ai_lang, stale_after=timedelta(seconds=2 * settings.ai_timeout_s)
        )

    def _ai_state(session: Session, job: AiJob, background: BackgroundTasks) -> AiState:
        """Stav AI výstupu; pri chýbajúcom výstupe naplánuje generovanie na pozadí (vlastná session)."""
        generator: Generator | None = app.state.ai_client
        config = _ai_config()
        state = lookup(session, job, config=config, now=_utc_now(), ai_enabled=generator is not None)
        session.commit()
        if state.status == "start":
            background.add_task(
                run_job, app.state.session_factory, job, generator, config=config, now=_utc_now
            )
        return state

    def _ai_block(request: Request, url: str, kind: str, state: AiState) -> HTMLResponse:
        return templates.TemplateResponse(
            request, "_ai_block.html", {"url": url, "kind": kind, "state": state}
        )

    @app.get("/ai/shift_summary/{shift_id}", response_class=HTMLResponse)
    def ai_shift_summary(
        request: Request, session: SessionDep, background: BackgroundTasks, shift_id: str
    ) -> HTMLResponse:
        try:
            job = shift_summary_job(
                session, shift_id, catalog=request_catalog(), config=_ai_config(), now=_utc_now()
            )
        except AnalyticsShiftNotFound:
            raise HTTPException(status_code=404, detail="Shift not found") from None
        state = _ai_state(session, job, background)
        return _ai_block(request, f"/ai/shift_summary/{quote(shift_id, safe='')}", "shift_summary", state)

    @app.get("/ai/link_explanation/{month}/{cause}/{effect}", response_class=HTMLResponse)
    def ai_link_explanation(
        request: Request,
        session: SessionDep,
        background: BackgroundTasks,
        month: str,
        cause: str,
        effect: str,
    ) -> HTMLResponse:
        try:
            start, end = parse_month(month)
        except PeriodError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        job = link_job(
            session,
            start=start,
            end=end,
            period_key=month,
            cause=cause,
            effect=effect,
            line=settings.line_id,
            catalog=request_catalog(),
            config=_ai_config(),
            now=_utc_now(),
        )
        if job is None:
            raise HTTPException(status_code=404, detail="Not a problem link in this period")
        state = _ai_state(session, job, background)
        url = f"/ai/link_explanation/{month}/{quote(cause, safe='')}/{quote(effect, safe='')}"
        return _ai_block(request, url, "link_explanation", state)

    @app.get("/health")
    def health(request: Request) -> dict[str, object]:
        """Stav aplikácie a lokálneho AI — nikdy nezlyhá, ak Ollama nebeží (ARCHITECTURE §7)."""
        client = request.app.state.ai_client
        if client is None:
            ai: dict[str, object] = {
                "enabled": False,
                "available": False,
                "model": settings.ollama_model,
                "model_present": False,
                "message": "AI is disabled (OEE_AI_ENABLED=false)",
            }
        elif not isinstance(client, OllamaClient):  # testovací generátor (FakeGenerator)
            ai = {
                "enabled": True,
                "available": True,
                "model": type(client).__name__,
                "model_present": True,
                "message": f"custom generator {type(client).__name__}",
            }
        else:
            h = client.health()
            ai = {
                "enabled": True,
                "available": h.available,
                "model": client.model,
                "model_present": h.model_present,
                "message": h.message,
            }
        return {"status": "ok", "version": __version__, "ai": ai}

    def _report_start(request: Request, session: Session, *, status_code: int = 200) -> HTMLResponse:
        model = get_active_model(session, line=settings.line_id)
        hours = None if model is None else model.config.duration_min // MINUTES_PER_HOUR
        recent = session.scalars(
            select(Shift).where(Shift.line_id == settings.line_id).order_by(Shift.date.desc()).limit(10)
        ).all()
        response = _page(
            request,
            "report.html",
            "Hourly Reporting",
            model=model,
            hours=hours,
            today=datetime.now().date(),  # lokálny čas linky (ARCHITECTURE §10.3)
            recent=recent,
        )
        response.status_code = status_code
        return response

    @app.get("/report", response_class=HTMLResponse)
    def hourly_reporting(request: Request, session: SessionDep) -> HTMLResponse:
        return _report_start(request, session)

    @app.post("/report", response_class=HTMLResponse, response_model=None)
    def open_report_shift(
        request: Request, session: SessionDep, day: Annotated[date, Form()]
    ) -> HTMLResponse | RedirectResponse:
        try:
            shift = open_shift(session, line=settings.line_id, day=day, now=_utc_now())
        except NoActiveShiftModel:
            return _report_start(request, session, status_code=422)
        return RedirectResponse(f"/report/{shift.shift_id}", status_code=303)

    def _overview(session: Session, shift_id: str, now_local: datetime | None = None) -> ShiftOverview:
        try:
            return shift_overview(session, shift_id, now_local=now_local or datetime.now())
        except ShiftNotFound:
            raise HTTPException(status_code=404, detail="Shift not found") from None

    def _hour_context(
        session: Session, overview: ShiftOverview, hour_no: int, form: HourForm | None
    ) -> dict[str, object]:
        try:
            state = hour_state(overview, session, hour_no)
        except LookupError:
            raise HTTPException(status_code=404, detail="Hour not part of this shift") from None
        stops, defects = list_codes(session)
        codes = get_active_codes(session)
        if form is None:  # predvyplnenie z uloženého stavu (rovnaký tvar ako odoslaný formulár)
            tile = state.tile
            values = {
                "produced": "" if tile.produced is None else str(tile.produced),
                "rejects": "0" if tile.rejects is None else str(tile.rejects),
                "issues": [
                    {
                        "issue_id": i.issue_id,
                        "issue_key": i.client_key,
                        "issue_code": i.code,
                        "issue_duration": f"{i.duration_min:g}",
                        "issue_start": "" if i.start is None else i.start.strftime("%H:%M"),
                        "issue_continues": i.continues_issue_id or "",
                        "issue_comment": i.comment or "",
                    }
                    for i in state.issues
                ],
                "defects": [
                    {"defect_code": d.code or "", "defect_qty": str(d.qty), "defect_comment": d.comment or ""}
                    for d in state.defects
                ],
                "errors": [],
            }
        else:
            values = {
                "produced": form.produced,
                "rejects": form.rejects,
                "issues": form.issues,
                "defects": form.defects,
                "errors": form.errors,
            }
        return {
            "overview": overview,
            "state": state,
            "values": values,
            "stops": stops,
            "defects": defects,
            "other_stop": codes.other_stop_code,
            "other_defect": codes.other_defect_code,
            "new_key": lambda: uuid4().hex,
        }

    @app.get("/report/{shift_id}", response_class=HTMLResponse)
    def report_shift(
        request: Request, session: SessionDep, shift_id: str, hour: int | None = None
    ) -> HTMLResponse:
        now_local = datetime.now()  # lokálny čas linky (ARCHITECTURE §10.3)
        overview = _overview(session, shift_id, now_local)
        context: dict[str, object] = {"overview": overview, "selected": hour}
        if hour is not None:
            context |= _hour_context(session, overview, hour, None)
        current = next((t.hour_no for t in overview.tiles if t.start <= now_local < t.end), None)
        saved = request.query_params.get("saved", "")
        return _page(
            request,
            "report_shift.html",
            "Hourly Reporting",
            current_hour=current,
            saved=f"Hour {saved} saved" if saved.isdigit() else None,
            **context,
        )

    @app.post("/report/{shift_id}/hour/{hour_no}", response_class=HTMLResponse, response_model=None)
    async def save_report_hour(
        request: Request, session: SessionDep, background: BackgroundTasks, shift_id: str, hour_no: int
    ) -> HTMLResponse | RedirectResponse:
        overview = _overview(session, shift_id)
        tile = next((t for t in overview.tiles if t.hour_no == hour_no), None)
        if tile is None:
            raise HTTPException(status_code=404, detail="Hour not part of this shift")
        form = parse_hour_form(
            await request.form(),
            shift_id=shift_id,
            hour_id=tile.hour_id,
            day=overview.shift.date,
            hour_no=hour_no,
        )
        if form.report is not None:
            try:
                result = save_hour(
                    session, shift_id, form.report, codes=get_active_codes(session), now=_utc_now()
                )
            except ValueError:  # nekonzistentná požiadavka (napr. cudzí issue_id, zastaraný formulár)
                session.rollback()
                form.errors.append("The form is out of date — reload the hour and enter the change again.")
            else:
                if result.saved:
                    if result.shift_status == "completed":  # ARCHITECTURE §6: AI zhrnutie po dokončení zmeny
                        try:
                            job = shift_summary_job(
                                session,
                                shift_id,
                                catalog=request_catalog(),
                                config=_ai_config(),
                                now=_utc_now(),
                            )
                            _ai_state(session, job, background)
                        except Exception:  # AI nesmie zhodiť uloženie hodiny; dashboard ho dogeneruje
                            session.rollback()
                            logger.exception("AI summary could not be scheduled for %s", shift_id)
                    target = f"/report/{shift_id}?saved={hour_no}"
                    if request.headers.get("HX-Request"):
                        return HTMLResponse("", headers={"HX-Redirect": target})
                    return RedirectResponse(target, status_code=303)
                form.errors.extend(m.message for m in result.messages if m.level == "error")
        context = _hour_context(session, overview, hour_no, form)
        if request.headers.get("HX-Request"):
            return templates.TemplateResponse(request, "_hour_form.html", context)
        response = _page(
            request,
            "report_shift.html",
            "Hourly Reporting",
            selected=hour_no,
            current_hour=None,
            saved=None,
            **context,
        )
        response.status_code = 422
        return response

    @app.get("/report/{shift_id}/hour/{hour_no}/row", response_class=HTMLResponse)
    def report_row(
        request: Request, session: SessionDep, shift_id: str, hour_no: int, kind: str
    ) -> HTMLResponse:
        if kind not in ("issue", "defect"):
            raise HTTPException(status_code=404, detail="Unknown row kind")
        context = _hour_context(session, _overview(session, shift_id), hour_no, None)
        template = "_issue_row.html" if kind == "issue" else "_defect_row.html"
        return templates.TemplateResponse(request, template, {**context, "row": {}})

    def _analytics(session: Session, shift_id: str) -> ShiftAnalytics:
        try:
            return build_shift(session, shift_id, catalog=request_catalog(), now=_utc_now())
        except AnalyticsShiftNotFound:
            raise HTTPException(status_code=404, detail="Shift not found") from None

    def request_catalog() -> Catalog:
        return app.state.catalog  # type: ignore[no-any-return]

    def _shift_choices(session: Session) -> list[Shift]:
        return list(
            session.scalars(
                select(Shift).where(Shift.line_id == settings.line_id).order_by(Shift.date.desc())
            )
        )

    @app.get("/shift", response_class=HTMLResponse, response_model=None)
    def shift_dashboard(
        request: Request, session: SessionDep, id: str | None = None
    ) -> HTMLResponse | RedirectResponse:
        shifts = _shift_choices(session)
        if not id and shifts:  # bez výberu sa otvorí posledná zmena (zoznam je zoradený od najnovšej)
            id = shifts[0].shift_id
        if id:
            return RedirectResponse(f"/shift/{quote(id, safe='')}", status_code=303)
        return _page(request, "shift.html", "Shift Dashboard", shifts=shifts, a=None)

    @app.get("/shift/{shift_id}", response_class=HTMLResponse)
    def shift_detail(
        request: Request,
        session: SessionDep,
        shift_id: str,
        sort: IssueSort = "time",
        group: Literal["none", "type"] = "none",
        pareto_by: Annotated[ParetoMode, Query(alias="pareto")] = "type",
    ) -> HTMLResponse:
        a = _analytics(session, shift_id)
        effective = effective_status(get_shift(session, shift_id), now_local=datetime.now())
        month_start, month_end = parse_month(month_key(a.shift.date))  # väzby §8.6 za mesiac zmeny
        month_period = build_period(
            session,
            month_start,
            month_end,
            line=a.shift.line,
            period_type="month",
            catalog=request_catalog(),
            now=_utc_now(),
        )
        issues = sorted_issues(a.issues, sort)
        return _page(
            request,
            "shift.html",
            "Shift Dashboard",
            shifts=_shift_choices(session),
            a=a,
            status=status_label(a, effective),
            issues=issues,
            groups=group_issues(issues) if group == "type" else None,
            sort=sort,
            group=group,
            pareto_by=pareto_by,
            buckets=pareto(a, pareto_by),
            bucket_label=bucket_label,
            linked=linked_defects_by_stop(month_period),
            links_month=month_key(a.shift.date),
        )

    @app.get("/api/shift/{shift_id}/charts")
    def shift_charts(session: SessionDep, shift_id: str) -> dict[str, object]:
        return charts_payload(_analytics(session, shift_id))

    def _anchor_day(session: Session) -> date:
        """Predvolené obdobie = obdobie poslednej zmeny linky (inak dnešok)."""
        return latest_shift_date(session, line=settings.line_id) or datetime.now().date()

    @app.get("/history", response_class=HTMLResponse)
    def production_history(
        request: Request, session: SessionDep, start: date | None = None, end: date | None = None
    ) -> HTMLResponse:
        if start is None or end is None:
            first, last = parse_month(month_key(_anchor_day(session)))
            start, end = start or first, end or last
        try:
            rows = shift_history(
                session,
                start,
                end,
                line=settings.line_id,
                catalog=request_catalog(),
                now=_utc_now(),
                now_local=datetime.now(),
            )
        except PeriodError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        return _page(
            request,
            "history.html",
            "Production History",
            tab="shifts",
            start=start,
            end=end,
            rows=rows,
            week=week_key(end),
            month=month_key(end),
        )

    def _period_page(
        request: Request, session: Session, *, kind: PeriodType, key: str, start: date, end: date
    ) -> HTMLResponse:
        period = build_period(
            session,
            start,
            end,
            line=settings.line_id,
            period_type=kind,
            catalog=request_catalog(),
            now=_utc_now(),
        )
        top_stops, top_defects = top10(session, period, request_catalog())
        previous, following = neighbour_periods(kind, start, end)
        return _page(
            request,
            "history_period.html",
            "Production History",
            tab=kind,
            p=period,
            key=key,
            start=start,
            end=end,
            week=week_key(start) if kind == "week" else week_key(end),
            month=month_key(start),
            top_stops=top_stops,
            top_defects=top_defects,
            categories=category_losses(period),
            ranking=period.problem_ranking[:TOP_SIZE],
            goal_met=sum(s.status == "goal_met" for s in period.shift_series),
            catalog_categories=request_catalog().categories,
            series_json=series_payload(period),
            previous=previous,
            following=following,
        )

    @app.get("/history/week", response_class=HTMLResponse)
    def history_week(request: Request, session: SessionDep, week: str | None = None) -> HTMLResponse:
        key = week or week_key(_anchor_day(session))
        try:
            start, end = parse_week(key)
        except PeriodError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        return _period_page(request, session, kind="week", key=key, start=start, end=end)

    @app.get("/history/month", response_class=HTMLResponse)
    def history_month(request: Request, session: SessionDep, month: str | None = None) -> HTMLResponse:
        key = month or month_key(_anchor_day(session))
        try:
            start, end = parse_month(key)
        except PeriodError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        return _period_page(request, session, kind="month", key=key, start=start, end=end)

    def _analysis_period(
        session: Session, week: str | None, month: str | None
    ) -> tuple[PeriodType, str, date, date]:
        """Obdobie pre Ranking a Links: týždeň, ak je zadaný, inak mesiac (predvolene posledný)."""
        try:
            if week:
                return ("week", week, *parse_week(week))
            key = month or month_key(_anchor_day(session))
            return ("month", key, *parse_month(key))
        except PeriodError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None

    def _code_names(session: Session) -> dict[str, str]:
        rows = [
            *session.execute(select(IssueType.code, IssueType.name_en)),
            *session.execute(select(DefectType.code, DefectType.name_en)),
        ]
        return {code: name for code, name in rows}

    def _analysis_page(
        request: Request,
        session: Session,
        tab: str,
        week: str | None,
        month: str | None,
    ) -> HTMLResponse:
        kind, key, start, end = _analysis_period(session, week, month)
        period = build_period(
            session,
            start,
            end,
            line=settings.line_id,
            period_type=kind,
            catalog=request_catalog(),
            now=_utc_now(),
        )
        previous, following = neighbour_periods(kind, start, end)
        return _page(
            request,
            "history_analysis.html",
            "Production History",
            tab=tab,
            kind=kind,
            p=period,
            key=key,
            start=start,
            end=end,
            week=week_key(start) if kind == "week" else week_key(end),
            month=month_key(start),
            previous=previous,
            following=following,
            ranking=ranking_view(period),
            arrows=TREND_ARROWS,
        )

    @app.get("/correlations", response_class=HTMLResponse)
    def correlations(
        request: Request,
        session: SessionDep,
        view: Literal["week", "month"] = "month",
        week: str | None = None,
        month: str | None = None,
        cause: str | None = None,
        effect: str | None = None,
    ) -> HTMLResponse:
        """Korelácie prestoj → neskorší zmätok (TASK §8.6): matica väzieb, vybraný pár, časová os výskytov.

        Väzby počíta `build_period` (kód, nie AI); obdobie ponúka iba týždne / mesiace so zmenami.
        """
        shifts = _shift_choices(session)
        if week and not month:
            view = "week"
        keys = sorted({(week_key if view == "week" else month_key)(s.date) for s in shifts}, reverse=True)
        chosen = (week if view == "week" else month) or (keys[0] if keys else None)
        if chosen is not None and keys and chosen not in keys:
            raise HTTPException(status_code=404, detail=f"No shifts for {view} {chosen}")
        context: dict[str, object] = {"view": view, "options": keys, "chosen": chosen, "period": None}
        if chosen is not None and keys:
            try:
                start, end = (parse_week if view == "week" else parse_month)(chosen)
            except PeriodError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from None
            period = build_period(
                session,
                start,
                end,
                line=settings.line_id,
                period_type=view,
                catalog=request_catalog(),
                now=_utc_now(),
            )
            matrix = link_matrix(period.problem_links, cause, effect)
            context |= {
                "period": period,
                "matrix": matrix,
                "occurrences": [] if matrix.selected is None else link_occurrences(session, matrix.selected),
                "code_names": _code_names(session),
            }
        return _page(request, "correlations.html", "Correlations", shifts=shifts, **context)

    @app.get("/line", response_class=HTMLResponse)
    def line_xray(
        request: Request,
        session: SessionDep,
        view: Literal["shift", "week", "month"] = "shift",
        shift: str | None = None,
        week: str | None = None,
        month: str | None = None,
    ) -> HTMLResponse:
        """Line X-Ray: problémy po staniciach (mapovanie = predpoklad, TASK §2) za zmenu, týždeň alebo mesiac.

        `view` = perspektíva; zoznam ponúka iba obdobia, v ktorých sú zmeny. Bez výberu = najnovšie.
        """
        shifts = _shift_choices(session)
        catalog = request_catalog()
        stations = load_stations(catalog)
        if week and not month and view == "shift":
            view = "week"
        if month and not week and view == "shift":
            view = "month"
        options: list[tuple[str, str]]
        if view == "shift":
            options = [
                (s.shift_id, f"{s.date.isoformat()} {WEEKDAY_NAMES[s.date.weekday()]} · {s.status}")
                for s in shifts
            ]
            chosen = shift
        elif view == "week":
            keys = sorted({week_key(s.date) for s in shifts}, reverse=True)
            options = [(k, k) for k in keys]
            chosen = week
        else:
            keys = sorted({month_key(s.date) for s in shifts}, reverse=True)
            options = [(k, k) for k in keys]
            chosen = month
        if chosen is None and options:
            chosen = options[0][0]
        if chosen is not None and options and chosen not in {k for k, _ in options}:
            raise HTTPException(status_code=404, detail=f"No shifts for {view} {chosen}")
        xray: LineXray | None = None
        label = ""
        if chosen is not None and options:
            common = {"line": settings.line_id, "catalog": catalog, "stations": stations}
            if view == "shift":
                xray = build_line_xray(session, shift_id=chosen, **common)  # type: ignore[arg-type]
                label = f"Shift {dict(options)[chosen]}"
            else:
                try:
                    start, end = (parse_week if view == "week" else parse_month)(chosen)
                except PeriodError as exc:
                    raise HTTPException(status_code=422, detail=str(exc)) from None
                xray = build_line_xray(session, start=start, end=end, **common)  # type: ignore[arg-type]
                label = f"{view.capitalize()} {chosen} · {xray.shifts} shifts"
        return _page(
            request,
            "line.html",
            "Line X-Ray",
            shifts=shifts,
            view=view,
            options=options,
            chosen=chosen,
            label=label,
            xray=xray,
        )

    @app.get("/history/ranking", response_class=HTMLResponse)
    def history_ranking(
        request: Request, session: SessionDep, week: str | None = None, month: str | None = None
    ) -> HTMLResponse:
        return _analysis_page(request, session, "ranking", week, month)

    def _preview(form: ModelForm) -> dict[str, object]:
        plan = None if form.config is None else build_shift_plan(form.config, datetime.now().date())
        return {"form": form, "plan": plan}

    def _settings(
        request: Request,
        session: SessionDep,
        *,
        form: ModelForm | None = None,
        code_error: str | None = None,
        code_input: dict[str, str] | None = None,
        status_code: int = 200,
    ) -> HTMLResponse:
        model = get_active_model(session, line=settings.line_id)
        if form is None:
            form = (
                empty_form()
                if model is None
                else form_from_config(model.config, product=model.product, grace_min=model.grace_min)
            )
        stops, defects = list_codes(session)
        response = _page(
            request,
            "settings.html",
            "Settings",
            model=model,
            model_hours=None if model is None else model.config.duration_min // MINUTES_PER_HOUR,
            weekdays=WEEKDAY_NAMES,
            saved=SAVED_MESSAGES.get(request.query_params.get("saved", "")),
            stops=stops,
            defects=defects,
            code_categories=code_categories(session),
            code_error=code_error,
            code_input=code_input or {"kind": "stop", "name": "", "category": ""},
            added=request.query_params.get("code"),
            categories=request.app.state.catalog.categories,
            **_preview(form),
        )
        response.status_code = status_code
        return response

    @app.get("/settings", response_class=HTMLResponse)
    def settings_page(request: Request, session: SessionDep, example: bool = False) -> HTMLResponse:
        form = None
        if example:
            ex = load_example_settings()
            form = form_from_config(ex.config, product=ex.product, grace_min=ex.grace_min)
        return _settings(request, session, form=form)

    @app.post("/settings/preview", response_class=HTMLResponse)
    async def settings_preview(request: Request) -> HTMLResponse:
        form = parse_model_form(await request.form())
        return templates.TemplateResponse(request, "_model_preview.html", _preview(form))

    @app.post("/settings/model", response_class=HTMLResponse, response_model=None)
    async def save_model(request: Request, session: SessionDep) -> HTMLResponse | RedirectResponse:
        form = parse_model_form(await request.form())
        if not form.ok or form.config is None or form.product is None or form.grace_min is None:
            return _settings(request, session, form=form, status_code=422)
        activate_shift_model(
            session,
            form.config,
            line=settings.line_id,
            product=form.product,
            grace_min=form.grace_min,
            now=_utc_now(),
        )
        session.commit()
        return RedirectResponse("/settings?saved=model", status_code=303)

    @app.post("/settings/codes", response_class=HTMLResponse, response_model=None)
    async def add_problem_code(request: Request, session: SessionDep) -> HTMLResponse | RedirectResponse:
        data = await request.form()
        entered = {k: str(data.get(k) or "") for k in ("kind", "name", "category")}
        try:
            new = add_code(session, **entered)
        except CodeError as exc:
            session.rollback()
            return _settings(request, session, code_error=str(exc), code_input=entered, status_code=422)
        session.commit()
        return RedirectResponse(f"/settings?saved=code&code={new.code}#codes", status_code=303)

    def _import_page(
        request: Request,
        *,
        result: ImportResult | None = None,
        error: str | None = None,
        status_code: int = 200,
    ) -> HTMLResponse:
        path = settings.dataset_path
        response = _page(
            request,
            "import.html",
            "Import",
            dataset=path,
            dataset_name=path.name,
            dataset_exists=path.is_file(),
            result=result,
            error=error,
            check_labels=CHECK_LABELS,
        )
        response.status_code = status_code
        return response

    @app.get("/import", response_class=HTMLResponse)
    def import_page(request: Request) -> HTMLResponse:
        return _import_page(request)

    @app.get("/import/example.xlsx")
    def import_example() -> Response:
        """Vzorový súbor vo formáte importu (generovaný z konštánt importéra, D8 príklad modelu)."""
        content = build_example_workbook(datetime.now().date(), line=settings.line_id)
        return Response(
            content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="oee_import_example.xlsx"'},
        )

    @app.post("/import", response_class=HTMLResponse)
    def run_import(request: Request, session: SessionDep) -> HTMLResponse:
        """Ten istý `import_excel` ako v testoch a skriptoch (jedna transakcia, Excel iba na čítanie)."""
        try:
            result = import_excel(session, settings.dataset_path, now=_utc_now())
        except DatasetError as exc:
            return _import_page(request, error=str(exc), status_code=422)
        return _import_page(request, result=result)

    return app


app = create_app()

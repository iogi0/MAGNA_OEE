"""FastAPI aplikácia (ARCHITECTURE §7, §10.5).

- `create_app(settings)` — továreň; testy si vytvárajú vlastné `Settings` (nikdy nie `data/local/oee.db`).
- `lifespan`: priečinok a schéma DB, seed číselníka (idempotentný), katalóg; pri vypnutí `engine.dispose()`.
- Šablóny `TemplateResponse(request, ...)`, assety iba lokálne z `/static/vendor` (demo offline).
- Jedno rozhranie bez rozdelenia na operátora a manažéra (PLANNING D14).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import quote
from uuid import uuid4

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from oee import __version__
from oee.ai.client import OllamaClient
from oee.catalog.loader import Catalog, load_catalog, load_example_settings
from oee.config import Settings, get_settings
from oee.contracts.shift_analytics import ShiftAnalytics
from oee.domain.shift_model import MINUTES_PER_HOUR, build_shift_plan
from oee.persistence.db import init_db, make_engine, make_session_factory
from oee.persistence.models import Shift
from oee.persistence.seed import seed_codebook
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

    @app.get("/health")
    def health(request: Request) -> dict[str, object]:
        """Stav aplikácie a lokálneho AI — nikdy nezlyhá, ak Ollama nebeží (ARCHITECTURE §7)."""
        client: OllamaClient | None = request.app.state.ai_client
        if client is None:
            ai: dict[str, object] = {
                "enabled": False,
                "available": False,
                "model": settings.ollama_model,
                "model_present": False,
                "message": "AI is disabled (OEE_AI_ENABLED=false)",
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
        request: Request, session: SessionDep, shift_id: str, hour_no: int
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
        if id:
            return RedirectResponse(f"/shift/{quote(id, safe='')}", status_code=303)
        return _page(request, "shift.html", "Shift Dashboard", shifts=_shift_choices(session), a=None)

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

    def _analysis_page(
        request: Request, session: Session, tab: str, week: str | None, month: str | None
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

    @app.get("/history/ranking", response_class=HTMLResponse)
    def history_ranking(
        request: Request, session: SessionDep, week: str | None = None, month: str | None = None
    ) -> HTMLResponse:
        return _analysis_page(request, session, "ranking", week, month)

    @app.get("/history/links", response_class=HTMLResponse)
    def history_links(
        request: Request, session: SessionDep, week: str | None = None, month: str | None = None
    ) -> HTMLResponse:
        return _analysis_page(request, session, "links", week, month)

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

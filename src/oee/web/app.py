"""FastAPI aplikácia (ARCHITECTURE §7, §10.5).

- `create_app(settings)` — továreň; testy si vytvárajú vlastné `Settings` (nikdy nie `data/local/oee.db`).
- `lifespan`: priečinok a schéma DB, seed číselníka (idempotentný), katalóg; pri vypnutí `engine.dispose()`.
- Šablóny `TemplateResponse(request, ...)`, assety iba lokálne z `/static/vendor` (demo offline).
- Jedno rozhranie bez rozdelenia na operátora a manažéra (PLANNING D14).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from oee import __version__
from oee.catalog.loader import load_catalog, load_example_settings
from oee.config import Settings, get_settings
from oee.domain.shift_model import MINUTES_PER_HOUR, build_shift_plan
from oee.persistence.db import init_db, make_engine, make_session_factory
from oee.persistence.models import Shift
from oee.persistence.seed import seed_codebook
from oee.services.codebook import CodeError, add_code, code_categories, list_codes
from oee.services.shift_models import activate_shift_model, get_active_model
from oee.web.forms import ModelForm, empty_form, form_from_config, parse_model_form

WEB_DIR = Path(__file__).resolve().parent
WEEKDAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
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

    @app.get("/report", response_class=HTMLResponse)
    def hourly_reporting(request: Request, session: SessionDep) -> HTMLResponse:
        model = get_active_model(session, line=settings.line_id)
        hours = None if model is None else model.config.duration_min // MINUTES_PER_HOUR
        return _page(
            request, "report.html", "Hourly Reporting", model=model, hours=hours, today=datetime.now().date()
        )

    @app.get("/shift", response_class=HTMLResponse)
    def shift_dashboard(request: Request) -> HTMLResponse:
        return _page(request, "placeholder.html", "Shift Dashboard", task="P0-19")

    @app.get("/history", response_class=HTMLResponse)
    def production_history(request: Request, session: SessionDep) -> HTMLResponse:
        shifts = session.scalar(
            select(func.count()).select_from(Shift).where(Shift.line_id == settings.line_id)
        )
        return _page(request, "history.html", "Production History", shift_count=shifts or 0)

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
            now=datetime.now(UTC).replace(tzinfo=None),  # audit v naivnom UTC (ARCHITECTURE §10.3)
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

    @app.get("/import", response_class=HTMLResponse)
    def import_page(request: Request) -> HTMLResponse:
        return _page(request, "placeholder.html", "Import", task="P0-18")

    return app


app = create_app()

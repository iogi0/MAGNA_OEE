"""P0-15: web kostra — create_app, lifespan (DB, seed), layout, navigácia, offline assety.

ARCHITECTURE §10.5, §10.7.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from oee.config import PROJECT_ROOT, Settings
from oee.persistence.models import IssueType, ShiftModelRow
from oee.web.app import create_app

PAGES = {
    "/report": "Hourly Reporting",
    "/shift": "Shift Dashboard",
    "/history": "Production History",
    "/settings": "Settings",
    "/import": "Import",
}
EXTERNAL_URL = re.compile(
    r"""(?:src|href|action)\s*=\s*["']\s*(?:https?:)?//(?!(?:localhost|127\.0\.0\.1)[:/"'])""", re.I
)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None, db_path=tmp_path / "web" / "oee.db", ai_enabled=False)  # type: ignore[call-arg]


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as c:
        yield c


@pytest.mark.parametrize(("path", "title"), PAGES.items())
def test_pages_render(client: TestClient, path: str, title: str) -> None:
    r = client.get(path)
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert f"<title>{title}" in r.text
    for label in PAGES.values():  # navigácia na každej stránke
        assert label in r.text


def test_root_redirects_to_hourly_reporting(client: TestClient) -> None:
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (302, 303, 307)
    assert r.headers["location"].endswith("/report")


@pytest.mark.parametrize("path", list(PAGES))
def test_html_has_no_external_urls(client: TestClient, path: str) -> None:
    html = client.get(path).text
    assert not EXTERNAL_URL.search(html), EXTERNAL_URL.findall(html)
    assert "/static/vendor/htmx.min.js" in html
    assert "/static/vendor/pico.min.css" in html


@pytest.mark.parametrize("asset", ["htmx.min.js", "chart.umd.min.js", "pico.min.css"])
def test_vendored_assets_are_served(client: TestClient, asset: str) -> None:
    r = client.get(f"/static/vendor/{asset}")
    assert r.status_code == 200 and len(r.content) > 10_000


def test_lifespan_creates_db_in_configured_path_and_seeds_codebook(
    client: TestClient, settings: Settings
) -> None:
    assert settings.db_path.is_file()
    assert settings.db_path != PROJECT_ROOT / "data" / "local" / "oee.db"
    with client.app.state.session_factory() as s:  # type: ignore[attr-defined]
        assert s.scalar(select(func.count()).select_from(IssueType)) == 48
        assert s.scalar(select(func.count()).select_from(ShiftModelRow)) == 0  # model sa neseeduje (D8)


def test_restart_does_not_duplicate_seed(settings: Settings) -> None:
    for _ in range(2):
        with TestClient(create_app(settings)) as c, c.app.state.session_factory() as s:  # type: ignore[attr-defined]
            assert s.scalar(select(func.count()).select_from(IssueType)) == 48


@pytest.mark.parametrize("path", list(PAGES))
def test_single_interface_without_roles(client: TestClient, path: str) -> None:
    html = client.get(path).text  # D14: jedno rozhranie, žiadny prepínač operátor / manažér
    assert "data-role" not in html and 'action="/role"' not in html
    assert "Operator" not in html and "Manager" not in html


def test_role_endpoint_is_gone(client: TestClient) -> None:
    assert client.post("/role", data={"role": "manager"}).status_code in (404, 405)


def test_hourly_reporting_without_model_points_to_settings(client: TestClient) -> None:
    html = client.get("/report").text
    assert 'href="/settings"' in html
    assert "No active shift model" in html


def test_healthz(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok"}


def test_unknown_page_is_404(client: TestClient) -> None:
    assert client.get("/nope").status_code == 404


def test_pages_with_active_non_example_model(client: TestClient) -> None:
    from datetime import datetime, time

    from oee.domain.shift_model import Allowance, ShiftModelConfig
    from oee.services.shift_models import activate_shift_model

    config = ShiftModelConfig(
        rate_per_hour=75,
        start=time(14, 0),
        duration_min=360,
        break_=Allowance(minutes=20, hour_no=3),
        am=Allowance(minutes=15, hour_no=1),
        target_oee=0.8,
        working_days=frozenset({0, 2, 4}),
    )
    with client.app.state.session_factory() as s:  # type: ignore[attr-defined]
        activate_shift_model(s, config, line="L01", product="P02", grace_min=30, now=datetime(2026, 12, 1))
        s.commit()
    report = " ".join(client.get("/report").text.split())
    assert "start 14:00, 6 h, 75 pcs/h" in report
    assert "No active shift model" not in report
    settings_html = " ".join(client.get("/settings").text.split())
    assert "v1 (P02)" in settings_html and "OEE goal 80.0 %" in settings_html

"""P0-16: Settings — model zmeny so živým prepočtom targetu a výber Top-10 (TASK §3.2, §5.4, D8, D9)."""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from oee.catalog.loader import load_catalog
from oee.config import Settings
from oee.contracts.hourly_report import HourlyReport
from oee.persistence.models import IssueEvent, ShiftModelRow
from oee.services.codebook import get_active_codes
from oee.services.reporting import open_shift, save_hour
from oee.services.shift_models import get_active_model
from oee.web.app import create_app
from oee.web.forms import TEXT_FIELDS

CATALOG = load_catalog()
NOW = datetime(2026, 12, 9, 10, 0)
# Iná konfigurácia než príklad (D8): 6 h od 14:00, 45 ks/h, prestávka 20 min v 3. hodine (+10), AM 15 min v 1.
SIX: dict[str, str | list[str]] = {
    "product": "P02",
    "rate_per_hour": "45",
    "start": "14:00",
    "duration_h": "6",
    "break_min": "20",
    "break_hour_no": "3",
    "break_offset_min": "10",
    "am_min": "15",
    "am_hour_no": "1",
    "am_offset_min": "0",
    "target_oee_pct": "80",
    "working_days": ["0", "2", "4"],
    "grace_min": "30",
}
EIGHT: dict[str, str | list[str]] = {
    **SIX,
    "rate_per_hour": "60",
    "start": "06:00",
    "duration_h": "8",
    "break_min": "30",
    "break_hour_no": "5",
    "break_offset_min": "0",
    "am_min": "10",
}
INPUT_VALUE = re.compile(r'<input[^>]*name="(\w+)"[^>]*value="([^"]*)"')


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(_env_file=None, db_path=tmp_path / "oee.db", ai_enabled=False)  # type: ignore[call-arg]
    with TestClient(create_app(settings)) as c:
        yield c


def db(client: TestClient) -> Session:
    return client.app.state.session_factory()  # type: ignore[attr-defined,no-any-return]


def inputs(html: str) -> dict[str, str]:
    return dict(INPUT_VALUE.findall(html))


def model_count(client: TestClient) -> int:
    with db(client) as s:
        return int(s.scalar(select(func.count()).select_from(ShiftModelRow)) or 0)


# --- model zmeny --------------------------------------------------------------------------------


def test_empty_form_has_no_hidden_defaults(client: TestClient) -> None:
    html = client.get("/settings").text
    values = inputs(html)
    for name in TEXT_FIELDS:
        assert values[name] == "", name  # D8: žiadne 60 / 480 / 85 % ani grace ako skrytý predvolený stav
    assert not re.search(r'name="working_days" value="\d" checked', html)
    assert "Fill with example" in html


def test_fill_with_example_prefills_form_and_preview_without_saving(client: TestClient) -> None:
    html = client.get("/settings", params={"example": "1"}).text
    values = inputs(html)
    assert (values["rate_per_hour"], values["duration_h"], values["target_oee_pct"]) == ("60", "8", "85")
    assert (values["product"], values["grace_min"]) == ("P01", "60")
    assert 'data-testid="shift-target">440<' in html  # 60 × 440 / 60
    assert model_count(client) == 0


def test_live_preview_computes_planned_time_and_targets(client: TestClient) -> None:
    r = client.post("/settings/preview", data=SIX)
    assert r.status_code == 200
    # planned = 360 − 20 − 15 = 325 min; target = 45 × 325 / 60 = 243,75; ideal cycle 3600 / 45 = 80 s
    assert 'data-testid="planned-min">325<' in r.text
    assert 'data-testid="shift-target">243.75<' in r.text
    assert 'data-testid="ideal-cycle">80<' in r.text
    assert 'data-testid="goal-good">195<' in r.text  # cieľ OEE 80 % × 243,75
    hourly = re.findall(r'data-testid="hour-target">([\d.]+)<', r.text)
    assert hourly == ["33.75", "45", "30", "45", "45", "45"]
    assert "<html" not in r.text  # HTMX fragment


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("rate_per_hour", "0", "line rate"),
        ("rate_per_hour", "abc", "Line rate"),
        ("duration_h", "0", "whole number of hours"),
        ("break_hour_no", "7", "outside the shift"),
        ("am_offset_min", "25", "overlap"),
        ("target_oee_pct", "120", "OEE goal"),
        ("start", "25:00", "Shift start"),
        ("product", " ", "Product"),
        ("grace_min", "-5", "Grace"),
    ],
)
def test_invalid_config_shows_error_and_is_not_saved(
    client: TestClient, field: str, value: str, message: str
) -> None:
    data = {**SIX, field: value}
    if field == "am_offset_min":
        data |= {"am_hour_no": "3", "am_min": "15"}  # AM 25–40 prekrýva prestávku 10–30 v 3. hodine
    preview = client.post("/settings/preview", data=data)
    assert message in preview.text and "shift-target" not in preview.text
    r = client.post("/settings/model", data=data, follow_redirects=False)
    assert r.status_code == 422
    assert message in r.text
    assert inputs(r.text)[field] == value.strip() or field == "product"  # formulár drží zadané hodnoty
    assert model_count(client) == 0


def test_no_working_day_is_rejected(client: TestClient) -> None:
    data = {k: v for k, v in SIX.items() if k != "working_days"}
    r = client.post("/settings/model", data=data, follow_redirects=False)
    assert r.status_code == 422 and "working day" in r.text
    assert model_count(client) == 0


def test_save_model_activates_new_version(client: TestClient) -> None:
    r = client.post("/settings/model", data=SIX, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/settings?saved=model"
    with db(client) as s:
        model = get_active_model(s, line="L01")
    assert model is not None and model.version == 1
    assert (model.product, model.grace_min) == ("P02", 30)
    assert model.config.duration_min == 360 and model.config.rate_per_hour == 45
    assert model.config.target_oee == pytest.approx(0.8)
    assert model.config.working_days == frozenset({0, 2, 4})

    page = client.get("/settings?saved=model").text
    assert "Shift model saved" in page and "v1" in page
    assert inputs(page)["rate_per_hour"] == "45"  # formulár ukazuje aktívny model
    assert client.get("/report").status_code == 200 and "Go to Settings" not in client.get("/report").text


def test_new_model_applies_to_new_shifts_old_keep_snapshot(client: TestClient) -> None:
    client.post("/settings/model", data=EIGHT)
    with db(client) as s:
        old = open_shift(s, line="L01", day=date(2026, 12, 9), now=NOW)
        s.commit()
    client.post("/settings/model", data=SIX)
    with db(client) as s:
        new = open_shift(s, line="L01", day=date(2026, 12, 10), now=NOW)
        again = open_shift(s, line="L01", day=date(2026, 12, 9), now=NOW)
        s.commit()
        assert get_active_model(s, line="L01").version == 2  # type: ignore[union-attr]
    assert old.model_snapshot["duration_min"] == 480 and again.model_snapshot["duration_min"] == 480
    assert new.model_snapshot["duration_min"] == 360 and new.model_snapshot["rate_per_hour"] == 45


# --- číselník problémov (D15) -------------------------------------------------------------------


def test_codes_section_lists_full_codebook_without_selection(client: TestClient) -> None:
    html = client.get("/settings").text
    assert 'name="stop"' not in html and 'name="defect"' not in html  # žiadny výber Top-10
    for code in ("ST-001", "ST-002", "ST-047", "Q-001", "Q-031"):
        assert f"<strong>{code}</strong>" in html
    assert (
        f"<strong>{CATALOG.other_stop}</strong>" not in html
    )  # Other je vždy k dispozícii, nie je v zozname
    assert "Stops (ST) — 47 + Other" in html and "Defects (Q) — 33 + Other" in html
    assert 'action="/settings/codes"' in html


def test_add_code_appears_in_list_and_in_reporting(client: TestClient) -> None:
    r = client.post(
        "/settings/codes",
        data={"kind": "stop", "name": "Conveyor belt jammed", "category": "general"},
        follow_redirects=False,
    )
    assert r.status_code == 303 and r.headers["location"] == "/settings?saved=code&code=ST-049#codes"
    html = client.get("/settings?saved=code&code=ST-049").text
    assert (
        "Problem code added" in html and "<strong>ST-049</strong>" in html and "Conveyor belt jammed" in html
    )
    with db(client) as s:
        assert "ST-049" in get_active_codes(s).stop_codes


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({"kind": "defect", "name": " ", "category": "general"}, "Enter a name"),
        ({"kind": "stop", "name": "Belt jam", "category": "other"}, "Unknown category"),
        ({"kind": "stop", "name": "part unavailable at station", "category": "general"}, "already exists"),
    ],
)
def test_invalid_new_code_is_not_saved(client: TestClient, data: dict[str, str], message: str) -> None:
    r = client.post("/settings/codes", data=data, follow_redirects=False)
    assert r.status_code == 422 and message in r.text
    assert f'name="name" value="{data["name"]}"' in r.text  # formulár drží zadané hodnoty
    with db(client) as s:
        codes = get_active_codes(s)
    assert (len(codes.stop_codes), len(codes.defect_codes)) == (47, 33)


def test_any_codebook_code_can_be_reported_and_unknown_cannot(client: TestClient) -> None:
    client.post("/settings/model", data=EIGHT)
    with db(client) as s:
        shift = open_shift(s, line="L01", day=date(2026, 12, 9), now=NOW)

        def report(hour: int, code: str) -> HourlyReport:
            return HourlyReport.model_validate(
                {
                    "hour_id": f"L01-20261209-{hour:02d}",
                    "shift_id": shift.shift_id,
                    "date": "2026-12-09",
                    "hour_no": hour,
                    "produced": 40,
                    "rejects": 0,
                    "issues": [{"client_key": f"k{hour}", "issue_type_code": code, "duration_min": 10}],
                }
            )

        codes = get_active_codes(s)
        assert save_hour(
            s, shift.shift_id, report(2, "ST-002"), codes=codes, now=NOW
        ).saved  # mimo TASK Top-10
        result = save_hour(s, shift.shift_id, report(3, "ST-999"), codes=codes, now=NOW)
        s.commit()
        assert s.scalar(select(IssueEvent).where(IssueEvent.issue_type_code == "ST-002")) is not None
    assert not result.saved
    assert [m.rule for m in result.messages if m.level == "error"] == ["V11"]

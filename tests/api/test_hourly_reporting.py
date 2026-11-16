"""P0-17: Hourly Reporting — výber dňa, dlaždice hodín, formulár hodiny (TASK §4.3, §5.1–5.3, D8, D15)."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from oee.config import Settings
from oee.persistence.models import IssueEvent, ProductionRecord, QualityRecord, Shift
from oee.web.app import create_app

DAY = "2026-12-09"
SHIFT = "L01-20261209-M"
# Iná konfigurácia než príklad (D8): 6 h od 14:00, 45 ks/h; AM 15 min v 1. hod., prestávka 20 min v 3. hod.
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


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(_env_file=None, db_path=tmp_path / "oee.db", ai_enabled=False)  # type: ignore[call-arg]
    with TestClient(create_app(settings)) as c:
        yield c


@pytest.fixture
def shift(client: TestClient) -> str:
    assert client.post("/settings/model", data=SIX, follow_redirects=False).status_code == 303
    r = client.post("/report", data={"day": DAY}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == f"/report/{SHIFT}"
    return SHIFT


def issue(
    key: str, code: str, minutes: str, start: str = "", continues: str = "", comment: str = ""
) -> dict[str, list[str]]:
    """Jeden riadok problému vo formulári hodiny."""
    return {
        "issue_key": [key],
        "issue_id": [""],
        "issue_code": [code],
        "issue_duration": [minutes],
        "issue_start": [start],
        "issue_continues": [continues],
        "issue_comment": [comment],
    }


def db(client: TestClient) -> Session:
    return client.app.state.session_factory()  # type: ignore[attr-defined,no-any-return]


def text(html: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


def save(client: TestClient, hour: int, data: dict[str, object], htmx: bool = False):  # type: ignore[no-untyped-def]
    headers = {"HX-Request": "true"} if htmx else {}
    return client.post(f"/report/{SHIFT}/hour/{hour}", data=data, headers=headers, follow_redirects=False)


# --- zmena --------------------------------------------------------------------------------------


def test_without_shift_model_opening_a_shift_points_to_settings(client: TestClient) -> None:
    r = client.post("/report", data={"day": DAY}, follow_redirects=False)
    assert r.status_code == 422
    assert 'href="/settings"' in r.text and "No active shift model" in r.text
    with db(client) as s:
        assert s.scalar(select(Shift)) is None


def test_report_page_offers_date_picker_defaulting_to_today(client: TestClient) -> None:
    client.post("/settings/model", data=SIX)
    html = client.get("/report").text
    assert re.search(r'<input[^>]*type="date"[^>]*name="day"[^>]*value="\d{4}-\d{2}-\d{2}"', html)
    assert 'action="/report"' in html


def test_open_shift_shows_header_and_one_tile_per_hour(client: TestClient, shift: str) -> None:
    page = text(client.get(f"/report/{shift}").text)
    for part in (DAY, "L01", SHIFT, "P02", "0/6"):
        assert part in page
    html = client.get(f"/report/{shift}").text
    tiles = re.findall(r'data-testid="tile-(\d+)"[^>]*data-status="(\w+)"', html)
    assert tiles == [(str(h), "empty") for h in range(1, 7)]
    assert "14:00–15:00" in page and "19:00–20:00" in page
    # hodinové targety z modelu (1. hodina 45 min → 33,75; 3. hodina 40 min → 30)
    assert "target 33.75" in page and "target 30" in page


def test_opening_same_day_again_does_not_duplicate(client: TestClient, shift: str) -> None:
    r = client.post("/report", data={"day": DAY}, follow_redirects=False)
    assert r.headers["location"] == f"/report/{shift}"
    with db(client) as s:
        assert len(list(s.scalars(select(Shift)))) == 1


def test_unknown_shift_is_404(client: TestClient) -> None:
    assert client.get("/report/L01-20991231-M").status_code == 404


# --- hodina ------------------------------------------------------------------------------------


def test_hour_form_defaults_rejects_to_zero_and_focuses_produced(client: TestClient, shift: str) -> None:
    html = client.get(f"/report/{shift}", params={"hour": 2}).text
    assert re.search(r'<input[^>]*name="produced"[^>]*autofocus', html)
    assert re.search(r'<input[^>]*name="rejects"[^>]*value="0"', html)
    assert 'data-testid="tile-2"' in html and 'aria-current="true"' in html


def test_hour_without_problems_takes_two_actions(client: TestClient, shift: str) -> None:
    r = save(client, 2, {"produced": "44", "rejects": "0"})  # 1) zadať kusy, 2) uložiť
    assert r.status_code == 303 and r.headers["location"] == f"/report/{shift}?saved=2"
    with db(client) as s:
        prod = s.get(ProductionRecord, "L01-20261209-02")
        assert prod is not None and (prod.produced_qty, prod.rejects_qty) == (44, 0)
    page = client.get(f"/report/{shift}?saved=2").text
    assert re.search(r'data-testid="tile-2"[^>]*data-status="submitted"', page)
    assert "1/6" in text(page) and "Hour 2 saved" in page


def test_rejects_field_missing_means_zero(client: TestClient, shift: str) -> None:
    assert save(client, 2, {"produced": "44"}).status_code == 303
    with db(client) as s:
        assert s.get(ProductionRecord, "L01-20261209-02").rejects_qty == 0  # type: ignore[union-attr]


def test_other_without_comment_is_inline_error_and_nothing_saved(client: TestClient, shift: str) -> None:
    data = {
        "produced": "30",
        "issue_key": ["k-other"],
        "issue_id": [""],
        "issue_code": ["ST-048"],
        "issue_duration": ["10"],
        "issue_start": [""],
        "issue_continues": [""],
        "issue_comment": [""],
    }
    r = save(client, 2, data, htmx=True)
    assert r.status_code == 200 and "A comment is required for Other" in r.text
    assert "<html" not in r.text  # HTMX fragment formulára
    assert 'value="30"' in r.text  # zadané hodnoty zostanú
    with db(client) as s:
        assert s.get(ProductionRecord, "L01-20261209-02") is None


def test_htmx_success_redirects_via_header(client: TestClient, shift: str) -> None:
    r = save(client, 2, {"produced": "40"}, htmx=True)
    assert r.status_code == 200 and r.headers["HX-Redirect"] == f"/report/{shift}?saved=2"


def test_problems_and_defects_from_full_codebook_are_saved_and_prefilled(
    client: TestClient, shift: str
) -> None:
    data = {
        "produced": "35",
        "rejects": "3",
        "defect_code": ["Q-001", "Q-034"],  # Q-001 nie je v štartovacom zozname (D15)
        "defect_qty": ["2", "1"],
        "defect_comment": ["", "scratched label"],
        "issue_key": ["k1"],
        "issue_id": [""],
        "issue_code": ["ST-002"],
        "issue_duration": ["12.5"],
        "issue_start": ["15:05"],
        "issue_continues": [""],
        "issue_comment": ["nest jam"],
    }
    assert save(client, 2, data).status_code == 303
    with db(client) as s:
        event = s.scalar(select(IssueEvent).where(IssueEvent.client_key == "k1"))
        assert event is not None and event.issue_type_code == "ST-002" and event.duration_min == 12.5
        assert event.start_at is not None and event.start_at.strftime("%H:%M") == "15:05"
        lines = sorted((q.defect_type_code, q.qty) for q in s.scalars(select(QualityRecord)))
        assert lines == [("Q-001", 2), ("Q-034", 1)]
    html = client.get(f"/report/{shift}", params={"hour": 2}).text
    assert 'value="35"' in html and 'value="3"' in html and 'value="12.5"' in html and 'value="15:05"' in html
    assert 'value="ST-002" selected' in html and 'value="Q-001" selected' in html
    assert re.search(r'data-testid="tile-2"[^>]*>.*?1 problem', html, re.S)


def test_resubmitting_hour_does_not_duplicate_and_removed_row_is_deleted(
    client: TestClient, shift: str
) -> None:
    row = issue("k1", "ST-001", "5")
    save(client, 2, {"produced": "40", **row})
    save(client, 2, {"produced": "40", **row})
    with db(client) as s:
        assert len(list(s.scalars(select(IssueEvent).where(IssueEvent.deleted_at.is_(None))))) == 1
    save(client, 2, {"produced": "41"})  # riadok odstránený vo formulári → soft delete
    with db(client) as s:
        assert list(s.scalars(select(IssueEvent).where(IssueEvent.deleted_at.is_(None)))) == []


def test_breakdown_must_match_rejects(client: TestClient, shift: str) -> None:
    data = {
        "produced": "40",
        "rejects": "3",
        "defect_code": ["Q-031"],
        "defect_qty": ["2"],
        "defect_comment": [""],
    }
    r = save(client, 2, data, htmx=True)
    assert "Breakdown sums to 2, but Rejects is 3" in r.text


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({"produced": "abc"}, "Produced"),
        ({"produced": "-1"}, "Produced"),
        ({"produced": "10", "rejects": "x"}, "Rejects"),
        (
            {
                "produced": "10",
                "issue_key": ["k"],
                "issue_id": [""],
                "issue_code": ["ST-001"],
                "issue_duration": ["0"],
                "issue_start": [""],
                "issue_continues": [""],
                "issue_comment": [""],
            },
            "Duration",
        ),
        (
            {
                "produced": "10",
                "issue_key": ["k"],
                "issue_id": [""],
                "issue_code": ["ST-001"],
                "issue_duration": ["5"],
                "issue_start": ["25:99"],
                "issue_continues": [""],
                "issue_comment": [""],
            },
            "Start time",
        ),
    ],
)
def test_bad_input_is_an_inline_error_not_a_crash(
    client: TestClient, shift: str, data: dict[str, object], message: str
) -> None:
    r = save(client, 2, data, htmx=True)
    assert r.status_code == 200 and message in r.text and "HX-Redirect" not in r.headers
    with db(client) as s:
        assert s.get(ProductionRecord, "L01-20261209-02") is None


def test_problem_can_continue_previous_hour(client: TestClient, shift: str) -> None:
    first = {"produced": "20", **issue("a", "ST-038", "15", start="14:45")}
    assert save(client, 1, first).status_code == 303
    with db(client) as s:
        prev = s.scalar(select(IssueEvent).where(IssueEvent.client_key == "a"))
        assert prev is not None
        prev_id = prev.issue_id
    row = client.get(f"/report/{shift}/hour/2/row", params={"kind": "issue"}).text
    assert re.search(rf'<option value="{prev_id}">ST-038 · 15 min from 14:45', row)  # pokračovanie z hodiny 1
    second = {"produced": "35", **issue("b", "ST-038", "10", start="15:00", continues=prev_id)}
    assert save(client, 2, second).status_code == 303
    with db(client) as s:
        cont = s.scalar(select(IssueEvent).where(IssueEvent.client_key == "b"))
        assert cont is not None and cont.continues_issue_id == prev_id


def test_all_hours_complete_the_shift(client: TestClient, shift: str) -> None:
    for hour in range(1, 7):
        assert save(client, hour, {"produced": "30"}).status_code == 303
    page = text(client.get(f"/report/{shift}").text)
    assert "6/6" in page and "Shift completed" in page
    with db(client) as s:
        assert s.get(Shift, shift).status == "completed"  # type: ignore[union-attr]


def test_hour_outside_shift_is_404(client: TestClient, shift: str) -> None:
    assert client.get(f"/report/{shift}", params={"hour": 7}).status_code == 404
    assert save(client, 7, {"produced": "1"}).status_code == 404


@pytest.mark.parametrize(("kind", "field"), [("issue", "issue_code"), ("defect", "defect_code")])
def test_add_row_fragment_offers_full_codebook_and_other(
    client: TestClient, shift: str, kind: str, field: str
) -> None:
    r = client.get(f"/report/{shift}/hour/2/row", params={"kind": kind})
    assert r.status_code == 200 and "<html" not in r.text
    assert f'name="{field}"' in r.text
    codes = re.findall(r'<option value="([\w-]+)"', r.text)
    if kind == "issue":
        assert len(codes) == 48 and "ST-048" in codes and "ST-002" in codes  # 47 + Other
        assert re.search(r'name="issue_key" value="[\w-]{8,}"', r.text)  # nový kľúč idempotencie
    else:
        assert len(codes) == 34 and "Q-034" in codes


def test_unknown_code_is_rejected_inline(client: TestClient, shift: str) -> None:
    r = save(client, 2, {"produced": "10", **issue("k", "ST-999", "5")}, htmx=True)
    assert "Choose a problem type from the codebook or Other" in r.text and "HX-Redirect" not in r.headers


def test_unspecified_rejects_are_not_shown_as_breakdown_rows(client: TestClient, shift: str) -> None:
    assert save(client, 2, {"produced": "10", "rejects": "2"}).status_code == 303
    with db(client) as s:
        assert [(q.defect_type_code, q.qty) for q in s.scalars(select(QualityRecord))] == [(None, 2)]
    html = client.get(f"/report/{shift}", params={"hour": 2}).text
    assert 'name="defect_code"' not in html and re.search(r'name="rejects"[^>]*value="2"', html)


def test_completed_banner_follows_shift_status(client: TestClient, shift: str) -> None:
    for hour in range(1, 6):
        save(client, hour, {"produced": "30"})
    assert "Shift completed" not in client.get(f"/report/{shift}").text

"""P0-20: Production History — Shift History, Weekly, Monthly, Top-10 (TASK §8.1–8.3, D15)."""

from __future__ import annotations

import html
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from oee.catalog.loader import load_catalog
from oee.config import PROJECT_ROOT, Settings
from oee.web.app import create_app

DATASET = PROJECT_ROOT / "data" / "raw" / "dummy_data.xlsx"
CATALOG = load_catalog()


def text(page: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", page)).split())


def make(tmp_path: Path) -> TestClient:
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None, db_path=tmp_path / "oee.db", dataset_path=DATASET, ai_enabled=False
    )
    return TestClient(create_app(settings))


@pytest.fixture(scope="module")
def imported(tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestClient]:
    if not DATASET.is_file():
        pytest.skip("dataset data/raw/dummy_data.xlsx missing")
    with make(tmp_path_factory.mktemp("history")) as c:
        assert c.post("/import").status_code == 200
        yield c


@pytest.fixture
def empty(tmp_path: Path) -> Iterator[TestClient]:
    with make(tmp_path) as c:
        yield c


def top_codes(page: str, kind: str) -> list[str]:
    block = page.split(f'data-top="{kind}"', 1)[1].split("</table>", 1)[0]
    return re.findall(r'data-code="([\w-]+)"', block)


# --- Shift History (§8.1) ------------------------------------------------------------------------


@pytest.mark.golden
def test_shift_history_lists_all_21_shifts_with_links(imported: TestClient) -> None:
    page = imported.get("/history").text  # predvolene mesiac poslednej zmeny = november 2026
    rows = re.findall(r'<tr data-shift="([\w-]+)"', page)
    assert len(rows) == 21 and rows[0] == "L01-20261102-M" and rows[-1] == "L01-20261130-M"
    assert 'href="/shift/L01-20261125-M"' in page
    row25 = text(page.split('data-shift="L01-20261125-M"', 1)[1].split("</tr>", 1)[0])
    # TASK §12.3: OEE 78.2 %, target 440, produced 350 (79.5 %), good 344, rejects 6, 48 min / 3 events
    for part in ("2026-11-25", "Wed", "78.2 %", "440", "350", "79.5 %", "344", "6", "48", "3", "completed"):
        assert part in row25, part
    assert "Below goal −6.8 p.p." in row25


@pytest.mark.golden
def test_shift_history_date_filter(imported: TestClient) -> None:
    page = imported.get("/history", params={"start": "2026-11-23", "end": "2026-11-27"}).text
    assert len(re.findall(r'<tr data-shift="', page)) == 5
    assert re.search(r'<input[^>]*name="start"[^>]*value="2026-11-23"', page)


def test_shift_history_without_shifts(empty: TestClient) -> None:
    assert "No shifts in this period" in empty.get("/history").text


def test_invalid_filters_are_rejected(empty: TestClient) -> None:
    assert empty.get("/history", params={"start": "2026-12-31", "end": "2026-12-01"}).status_code == 422
    assert empty.get("/history/week", params={"week": "2026-48"}).status_code == 422
    assert empty.get("/history/week", params={"week": "2026-W54"}).status_code == 422
    assert empty.get("/history/month", params={"month": "2026-13"}).status_code == 422


# --- Weekly (§8.2) -------------------------------------------------------------------------------


@pytest.mark.golden
def test_week_48_matches_task_12_2(imported: TestClient) -> None:
    page = text(imported.get("/history/week", params={"week": "2026-W48"}).text)
    assert "2026-11-23 – 2026-11-29" in page and "5 shifts" in page  # ISO týždeň Po–Ne, zmeny Po–Pi
    assert "OEE 87.1 %" in page  # TASK §12.2: 87.09 %
    assert "Most frequent problems" in page and "Longest problems" in page


@pytest.mark.golden
def test_week_49_is_partial(imported: TestClient) -> None:
    page = text(imported.get("/history/week", params={"week": "2026-W49"}).text)
    assert "· 1 shift ·" in page and "OEE 89.5 %" in page  # TASK §12.2: 89.55 % (presne 89.545 %)


# --- Monthly (§8.3) ------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def month_page(imported: TestClient) -> str:
    r = imported.get("/history/month", params={"month": "2026-11"})
    assert r.status_code == 200
    return r.text


@pytest.mark.golden
def test_month_matches_task_12_1(month_page: str) -> None:
    t = text(month_page)
    # TASK §12.1: OEE 88.01 % (+3.01 p. b.), target 9240, produced 8251, good 8132, prestoje 410 min / 33
    assert re.search(r"OEE 88\.0 % .*Goal met .*\+3\.0 p\.p\.", t)
    for part in (
        "Target 9240",
        "Produced 8251 89.3 %",
        "Good 8132",
        "Rejects 119",
        "Downtime 410 min · 33 events",
    ):
        assert part in t, part
    assert "21 shifts" in t and "17 of 21 shifts met the OEE goal" in t


@pytest.mark.golden
def test_month_weeks_table_marks_partial_week(month_page: str) -> None:
    weeks = re.findall(r'<tr data-week="(\d+)"[^>]*data-partial="(\w+)"', month_page)
    assert weeks == [("45", "no"), ("46", "no"), ("47", "no"), ("48", "no"), ("49", "yes")]


@pytest.mark.golden
def test_month_type_table_and_categories(month_page: str) -> None:
    t = text(month_page)
    # TASK §12.4: ST-038 4 udalosti, 100 min, priemer 25; ST-001 7 / 60 / 8.57
    assert "ST-038 Camera malfunction 4 100 25" in t
    assert "ST-001 Material shortage 7 60 8.57" in t
    assert "Camera malfunction 11 170" in t  # straty podľa kategórie: ST-038 + ST-016


@pytest.mark.golden
def test_month_top10_by_frequency(month_page: str) -> None:
    # D15: poradie podľa výskytov; zvyšok doplní štartovací zoznam s nulami
    assert top_codes(month_page, "stop") == [
        "ST-016", "ST-046", "ST-001", "ST-038", "ST-047", "ST-017", "ST-020", "ST-026", "ST-032", "ST-040",
    ]  # fmt: skip
    assert top_codes(month_page, "defect") == [
        "Q-031", "Q-020", "Q-026", "Q-030", "Q-021", "Q-022", "Q-025", "Q-027", "Q-032", "Q-003",
    ]  # fmt: skip


@pytest.mark.golden
def test_week_top10_by_frequency(imported: TestClient) -> None:
    page = imported.get("/history/week", params={"week": "2026-W48"}).text
    codes = top_codes(page, "stop")
    assert len(codes) == 10 and codes[0] in {"ST-016", "ST-046", "ST-001", "ST-038", "ST-047", "ST-017"}


def test_top10_without_data_is_starting_list_with_zero_progress(empty: TestClient) -> None:
    page = empty.get("/history/month", params={"month": "2026-11"}).text
    assert top_codes(page, "stop") == list(CATALOG.top10_stop)
    assert top_codes(page, "defect") == list(CATALOG.top10_defect)
    block = page.split('data-top="stop"', 1)[1].split("</table>", 1)[0]
    assert set(re.findall(r'<progress[^>]*value="([\d.]+)"', block)) == {"0"}


def test_new_code_from_settings_enters_top10_when_frequent(empty: TestClient) -> None:
    empty.post("/settings/codes", data={"kind": "stop", "name": "Conveyor jam", "category": "general"})
    form = {
        "product": "P02", "rate_per_hour": "45", "start": "06:00", "duration_h": "2", "break_min": "0",
        "break_hour_no": "1", "break_offset_min": "0", "am_min": "0", "am_hour_no": "1", "am_offset_min": "0",
        "target_oee_pct": "80", "working_days": ["0", "1", "2", "3", "4", "5", "6"], "grace_min": "0",
    }  # fmt: skip
    empty.post("/settings/model", data=form)
    shift = empty.post("/report", data={"day": "2026-11-10"}, follow_redirects=False).headers["location"]
    for hour in (1, 2):
        row = {
            "produced": "30", "issue_key": [f"k{hour}"], "issue_id": [""], "issue_code": ["ST-049"],
            "issue_duration": ["5"], "issue_start": [""], "issue_continues": [""], "issue_comment": [""],
        }  # fmt: skip
        assert empty.post(f"{shift}/hour/{hour}", data=row, follow_redirects=False).status_code == 303
    page = empty.get("/history/month", params={"month": "2026-11"}).text
    assert top_codes(page, "stop")[0] == "ST-049"


def test_history_chart_script_is_local_and_does_no_data_math() -> None:
    js = (PROJECT_ROOT / "src" / "oee" / "web" / "static" / "history_charts.js").read_text(encoding="utf-8")
    assert "http" not in js
    data_math = r"\b(?:data|s|w)(?:\.\w+|\[\w+\])+\s*[-+*/]\s*[\w(]"
    assert not re.search(data_math, js), re.findall(data_math, js)


def test_period_navigation_previous_and_next(empty: TestClient) -> None:
    week = empty.get("/history/week", params={"week": "2026-W01"}).text
    assert 'href="/history/week?week=2025-W52"' in week and 'href="/history/week?week=2026-W02"' in week
    month = empty.get("/history/month", params={"month": "2026-01"}).text
    assert 'href="/history/month?month=2025-12"' in month and 'href="/history/month?month=2026-02"' in month
    assert re.search(r'<input[^>]*name="month"[^>]*value="2026-01"', month)

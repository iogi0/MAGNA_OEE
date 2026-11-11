"""P0-19: Shift Dashboard A–E (TASK §7) — čísla z `ShiftAnalytics`, žiadny výpočet v šablóne ani v JS."""

from __future__ import annotations

import html
import re
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from oee.config import PROJECT_ROOT, Settings
from oee.services.analytics import build_shift
from oee.web.app import create_app

DATASET = PROJECT_ROOT / "data" / "raw" / "dummy_data.xlsx"
S25 = "L01-20261125-M"
SIX: dict[str, str | list[str]] = {  # iná konfigurácia než príklad (D8)
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
    "working_days": ["0", "1", "2", "3", "4", "5", "6"],
    "grace_min": "30",
}


def text(page: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", page)).split())


def make(tmp_path: Path, dataset: Path = DATASET) -> TestClient:
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None, db_path=tmp_path / "oee.db", dataset_path=dataset, ai_enabled=False
    )
    return TestClient(create_app(settings))


@pytest.fixture(scope="module")
def imported(tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestClient]:
    if not DATASET.is_file():
        pytest.skip("dataset data/raw/dummy_data.xlsx missing")
    with make(tmp_path_factory.mktemp("dash")) as c:
        assert c.post("/import").status_code == 200
        yield c


@pytest.fixture
def empty(tmp_path: Path) -> Iterator[TestClient]:
    with make(tmp_path) as c:
        yield c


# --- výber zmeny --------------------------------------------------------------------------------


def test_shift_page_without_shifts_points_to_reporting(empty: TestClient) -> None:
    html = empty.get("/shift").text
    assert "No shifts yet" in html and 'href="/report"' in html


@pytest.mark.golden
def test_shift_selector_lists_shifts_and_opens_latest(imported: TestClient) -> None:
    html = imported.get("/shift").text
    assert html.count('<option value="L01-2026') == 21
    r = imported.get("/shift", params={"id": S25}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == f"/shift/{S25}"


def test_unknown_shift_is_404(empty: TestClient) -> None:
    assert empty.get("/shift/L01-20991231-M").status_code == 404
    assert empty.get("/api/shift/L01-20991231-M/charts").status_code == 404


# --- 25.11.2026 = TASK §12.3 -------------------------------------------------------------------


@pytest.fixture(scope="module")
def page25(imported: TestClient) -> str:
    r = imported.get(f"/shift/{S25}")
    assert r.status_code == 200
    return r.text


@pytest.mark.golden
def test_header(page25: str) -> None:
    t = text(page25)
    for part in (S25, "2026-11-25", "Wed", "L01", "P01", "completed"):
        assert part in t, part
    assert "provisional" not in t


@pytest.mark.golden
def test_section_a_kpi_cards(page25: str) -> None:
    t = text(page25)
    # TASK §12.3: OEE 78.2 % (−6.8 p. b. pod cieľom 85 %) · A 89.1 % · P 89.3 % · Q 98.3 %
    assert re.search(r"OEE 78\.2 % .*Below goal .*−6\.8 p\.p\.", t)
    for label, value in (("Availability", "89.1 %"), ("Performance", "89.3 %"), ("Quality", "98.3 %")):
        assert f"{label} {value}" in t, label
    # príspevok strát v kusoch (D, S, R)
    assert "Downtime −48 pcs" in t and "Speed −42 pcs" in t and "Rejects −6 pcs" in t


@pytest.mark.golden
def test_section_b_waterfall_table(page25: str) -> None:
    t = text(page25)
    for row in (
        "Target 440",
        "Technical losses −48",
        "Speed loss −42",
        "Produced 350 79.5 %",
        "Rejects −6",
        "Good 344",
        "Deviation from target −96",
        "OEE goal (85.0 %) 374",
    ):
        assert row in t, row


@pytest.mark.golden
def test_section_c_hourly_table_and_flags(page25: str) -> None:
    rows = re.findall(r'<tr data-hour="(\d)" data-flags="([^"]*)">', page25)
    assert [int(h) for h, _ in rows] == list(range(1, 9))
    below = [int(h) for h, f in rows if "below_goal" in f]
    downtime = [int(h) for h, f in rows if "downtime_ge_5_min" in f]
    assert below == [1, 2, 4, 5, 6] and downtime == [2, 4, 6]  # TASK §12.3
    assert "not submitted" not in text(page25)


@pytest.mark.golden
def test_section_d_issues_and_defects(page25: str) -> None:
    t = text(page25)
    assert re.search(r"2 07:08 Leak test issue ST-046 .*? 13 13 2\.95 %", t)
    assert re.search(r"4 09:08 Camera malfunction ST-038 .*? 25 25 5\.68 %", t)
    assert "> 5 min" in t
    assert "Q-030 3" in t and "Q-020 2" in t and "Q-031 1" in t


@pytest.mark.golden
def test_section_d_sort_and_group_without_merging(imported: TestClient) -> None:
    by_duration = text(imported.get(f"/shift/{S25}", params={"sort": "duration"}).text)
    assert by_duration.index("09:08") < by_duration.index("07:08") < by_duration.index("11:08")
    grouped = imported.get(f"/shift/{S25}", params={"group": "type"}).text
    t = text(grouped)
    assert "ST-046 · 2 events · 23 min" in t and "ST-038 · 1 event · 25 min" in t
    assert grouped.count('data-issue-row="') == 3  # udalosti sa nezlúčia


@pytest.mark.golden
def test_section_e_pareto_by_type_and_category(page25: str, imported: TestClient) -> None:
    t = text(page25)
    assert re.search(r"Unattributed speed loss 42 43\.8 % .*ST-038 25 26\.0 % .*ST-046 23 24\.0 %", t)
    cat = text(imported.get(f"/shift/{S25}", params={"pareto": "category"}).text)
    assert re.search(r"Unattributed speed loss 42 .*Camera malfunction 28 .*Leak test issue 24", cat)


@pytest.mark.golden
def test_charts_api_returns_the_same_numbers_as_shift_analytics(imported: TestClient) -> None:
    data = imported.get(f"/api/shift/{S25}/charts").json()
    with imported.app.state.session_factory() as s:  # type: ignore[attr-defined]
        a = build_shift(s, S25, catalog=imported.app.state.catalog, now=datetime(2026, 12, 1))  # type: ignore[attr-defined]
    assert data["waterfall"] == a.waterfall_pcs.model_dump(mode="json")
    # hranice stĺpcov waterfallu = kaskáda Target → Target − D → Produced → Good (TASK §12.3: 440/48/350/344)
    assert [s["range"] for s in data["waterfall_steps"]] == [
        [0, 440],
        [392, 440],
        [350, 392],
        [0, 350],
        [344, 350],
        [0, 344],
    ]
    assert [s["value"] for s in data["waterfall_steps"]] == [440, -48, -42, 350, -6, 344]  # popisy stĺpcov
    # spojnice schodov: úroveň, na ktorej krok končí a ďalší začína (posledný krok nemá spojnicu)
    assert [s["connect"] for s in data["waterfall_steps"]] == [440, 392, 350, 350, 344, None]
    assert (
        data["oee_goal_pcs"] == a.target_vs_actual.oee_goal_pcs and data["target_oee"] == a.model.target_oee
    )
    assert [h["oee"] for h in data["hourly"]] == [h.oee for h in a.hourly]
    assert [h["target_pcs"] for h in data["hourly"]] == [h.target_pcs for h in a.hourly]
    assert [(b["bucket"], b["pcs"]) for b in data["pareto"]["type"]] == [
        (b.bucket, b.pcs) for b in a.loss_pareto
    ]
    assert sum(b["pcs"] for b in data["pareto"]["category"]) == pytest.approx(
        sum(b.pcs for b in a.loss_pareto)
    )


def test_chart_script_is_local_and_does_no_math() -> None:
    js = (PROJECT_ROOT / "src" / "oee" / "web" / "static" / "shift_charts.js").read_text(encoding="utf-8")
    assert "http" not in js
    # žiadna aritmetika nad dátami zo servera (polia d, h, b, s, w); pixelová geometria plátna je povolená
    data_math = r"\b(?:d|h|b|s|w)(?:\.\w+|\[\w+\])+\s*[-+*/]\s*[\w(]"
    assert not re.search(data_math, js), re.findall(data_math, js)
    # JS iba kreslí: žiadne sčítanie / delenie hodnôt KPI (okrem prevodu podielu na % pri osi)
    assert not re.search(r"\b(reduce|Math\.(round|floor|ceil))\b", js)


# --- rozpracovaná zmena = provisional -----------------------------------------------------------


def test_in_progress_shift_is_provisional_and_missing_hours_are_not_zero(empty: TestClient) -> None:
    empty.post("/settings/model", data=SIX)
    day = "2099-01-05"  # budúca zmena: nikdy nie je po grace → stav nezávisí od času behu testu
    shift = (
        empty.post("/report", data={"day": day}, follow_redirects=False).headers["location"].split("/")[-1]
    )
    for hour in (1, 2):
        assert empty.post(f"/report/{shift}/hour/{hour}", data={"produced": "30"}).status_code in (200, 303)
    t = text(empty.get(f"/shift/{shift}").text)
    assert "in_progress 2/6 — provisional" in t
    assert t.count("not submitted") == 4
    hourly = empty.get(f"/api/shift/{shift}/charts").json()["hourly"]
    assert [h["oee"] is None for h in hourly] == [False, False, True, True, True, True]


def test_shift_selector_escapes_id_in_redirect(empty: TestClient) -> None:
    r = empty.get("/shift", params={"id": "a/b?c"}, follow_redirects=False)
    assert r.headers["location"] == "/shift/a%2Fb%3Fc"

"""Line X-Ray (TASK §2, §7): problémy po staniciach a intervaly prestojov po hodinách."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from oee.config import PROJECT_ROOT, Settings
from oee.web.app import create_app

DATASET = PROJECT_ROOT / "data" / "raw" / "dummy_data.xlsx"
S25 = "L01-20261125-M"


def make(tmp_path: Path) -> TestClient:
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None, db_path=tmp_path / "oee.db", dataset_path=DATASET, ai_enabled=False
    )
    return TestClient(create_app(settings))


@pytest.fixture
def imported(tmp_path: Path) -> Iterator[TestClient]:
    if not DATASET.is_file():
        pytest.skip("dataset data/raw/dummy_data.xlsx missing")
    with make(tmp_path) as c:
        assert c.post("/import").status_code == 200
        yield c


def levels(html: str) -> dict[str, str]:
    return dict(re.findall(r'data-station="(\d+)" data-level="(\w+)"', html))


def test_nav_has_line_xray_between_history_and_settings(tmp_path: Path) -> None:
    with make(tmp_path) as c:
        html = c.get("/line").text
        assert html.index('href="/history"') < html.index('href="/line"') < html.index('href="/settings"')
        assert "No shifts yet" in html


@pytest.mark.golden
def test_shift_25_11_camera_station_is_high(imported: TestClient) -> None:
    html = imported.get("/line", params={"shift": S25}).text
    lv = levels(html)
    assert len(lv) == 10
    # TASK §12.3: ST-038 25 min (camera → stanica 3); leak test ST-046 / ST-047 → stanica 9
    assert lv["3"] == "high"
    assert lv["9"] in {"elevated", "high"}
    assert lv["1"] == "none" and lv["10"] == "none"
    # hodinová páska: 8 hodín, interval ST-038 o 09:08
    assert len(re.findall(r'class="hour(?: unreported)?"', html)) == 8
    assert re.search(r'title="ST-038 · 09:08 · 25 min"', html)


@pytest.mark.golden
def test_perspective_lists_only_periods_with_shifts(imported: TestClient) -> None:
    default = imported.get("/line").text
    assert "Shift 2026-11-30" in default and 'aria-current="true">Shift' in default
    assert default.count('<option value="L01-2026') == 21

    weeks = imported.get("/line", params={"view": "week"}).text
    listed = re.findall(r'<option value="(\d{4}-W\d{2})"', weeks)
    assert listed and listed == sorted(listed, reverse=True) and "2026-W48" in listed
    assert 'name="week"' in weeks and "Week 2026-W" in weeks
    assert 'class="hour-strip"' not in weeks  # páska iba pre jednu zmenu

    month = imported.get("/line", params={"view": "month"}).text
    assert re.findall(r'<option value="(\d{4}-\d{2})"', month) == ["2026-11"]
    assert "Month 2026-11 · 21 shifts" in month and "33 downtime records" in month
    assert levels(month)["3"] == "high"

    chosen = imported.get("/line", params={"view": "week", "week": "2026-W48"}).text
    assert '<option value="2026-W48" selected>' in chosen and "Week 2026-W48" in chosen


def test_unknown_shift_or_period_is_404(imported: TestClient) -> None:
    assert imported.get("/line", params={"shift": "L01-20991231-M"}).status_code == 404
    assert imported.get("/line", params={"view": "month", "month": "2026-13"}).status_code == 404
    assert imported.get("/line", params={"view": "week", "week": "2030-W01"}).status_code == 404

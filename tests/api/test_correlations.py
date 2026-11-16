"""Záložka Correlations (TASK §8.6, §12.8): matica väzieb, vybraný pár, časová os výskytov."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from oee.config import PROJECT_ROOT, Settings
from oee.web.app import create_app

DATASET = PROJECT_ROOT / "data" / "raw" / "dummy_data.xlsx"
# TASK §12.8: 5 väzieb za november
LINKS = {
    ("ST-038", "Q-030"),
    ("ST-016", "Q-031"),
    ("ST-047", "Q-030"),
    ("ST-017", "Q-031"),
    ("ST-046", "Q-020"),
}


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


def cells(html: str) -> set[tuple[str, str]]:
    return set(re.findall(r"cause=(ST-\d{3})&effect=(Q-\d{3})", html))


def test_nav_order_and_empty_db(tmp_path: Path) -> None:
    with make(tmp_path) as c:
        html = c.get("/correlations").text
        order = [html.index(f'href="{u}"') for u in ("/history", "/correlations", "/line", "/settings")]
        assert order == sorted(order)
        assert "No shifts yet" in html


@pytest.mark.golden
def test_month_matrix_matches_task_12_8_and_selects_strongest(imported: TestClient) -> None:
    html = imported.get("/correlations").text  # predvolene najnovší mesiac
    assert '<option value="2026-11" selected>' in html
    assert cells(html) == LINKS
    assert 'data-cause="ST-038" data-effect="Q-030"' in html  # najsilnejšia väzba je vybraná
    assert "4.8×" in html
    # časová os: 4 výskyty ST-038 (support), každý s časom začiatku
    assert html.count('class="tl-row"') == 4
    assert "ST-038 starts" in html


@pytest.mark.golden
def test_selecting_a_pair_and_week_view(imported: TestClient) -> None:
    html = imported.get(
        "/correlations", params={"view": "month", "month": "2026-11", "cause": "ST-016", "effect": "Q-031"}
    ).text
    assert 'data-cause="ST-016" data-effect="Q-031"' in html
    assert html.count('class="tl-row"') == 7  # TASK §12.8: support 7
    week = imported.get("/correlations", params={"view": "week"}).text
    weeks = re.findall(r'<option value="(\d{4}-W\d{2})"', week)
    assert weeks and weeks == sorted(weeks, reverse=True)


def test_unknown_period_is_404(imported: TestClient) -> None:
    assert imported.get("/correlations", params={"view": "month", "month": "2030-01"}).status_code == 404


@pytest.mark.golden
def test_cells_swap_detail_without_full_reload(imported: TestClient) -> None:
    html = imported.get("/correlations").text
    assert 'hx-select="#corr"' in html and 'hx-target="#corr"' in html and 'hx-push-url="true"' in html
    assert "First recorded anomaly" not in html
    assert html.count('class="tl-dot stop start"') == 4  # bod začiatku každého prestoja ST-038

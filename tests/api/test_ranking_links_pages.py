"""P0-21: záložky Problem Ranking a Problem Links, odznak väzby (TASK §8.4, §8.6, §12.5, §12.8)."""

from __future__ import annotations

import html
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from oee.config import PROJECT_ROOT, Settings
from oee.web.app import create_app

DATASET = PROJECT_ROOT / "data" / "raw" / "dummy_data.xlsx"
RANKING = [  # TASK §12.5: poradie a triedy
    ("ST-038", "A"), ("ST-016", "A"), ("ST-046", "A"), ("ST-001", "A"), ("ST-047", "A"),
    ("ST-017", "A"), ("Q-031", "A"), ("Q-020", "B"), ("Q-026", "B"), ("Q-030", "C"),
]  # fmt: skip
LINKS = {
    ("ST-038", "Q-030"),
    ("ST-016", "Q-031"),
    ("ST-047", "Q-030"),
    ("ST-017", "Q-031"),
    ("ST-046", "Q-020"),
}


def text(page: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", page)).split())


@pytest.fixture(scope="module")
def client(tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestClient]:
    if not DATASET.is_file():
        pytest.skip("dataset data/raw/dummy_data.xlsx missing")
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        db_path=tmp_path_factory.mktemp("rank") / "oee.db",
        dataset_path=DATASET,
        ai_enabled=False,
    )
    with TestClient(create_app(settings)) as c:
        assert c.post("/import").status_code == 200
        yield c


@pytest.fixture(scope="module")
def ranking(client: TestClient) -> str:
    r = client.get("/history/ranking", params={"month": "2026-11"})
    assert r.status_code == 200
    return r.text


@pytest.fixture(scope="module")
def links(client: TestClient) -> str:
    r = client.get("/history/links", params={"month": "2026-11"})
    assert r.status_code == 200
    return r.text


# --- Ranking (§8.4, §12.5) -----------------------------------------------------------------------


@pytest.mark.golden
def test_ranking_order_and_classes(ranking: str) -> None:
    rows = re.findall(r'<tr data-rank="\d+" data-code="([\w-]+)" data-class="(\w)"', ranking)
    assert rows == RANKING


@pytest.mark.golden
def test_unattributed_speed_loss_is_not_in_ranking(ranking: str) -> None:
    # rozhodnutie vlastníka (PLANNING D18): nepriradená strata rýchlosti → bez riadku v rebríčku
    assert 'class="pinned"' not in ranking
    table = ranking.split("<table", 1)[1].split("</table>", 1)[0]
    assert "Unattributed speed loss" not in table
    assert "/history/month?month=2026-11#speed-by-hour" in ranking  # odkaz na analýzu hodín zmeny


@pytest.mark.golden
def test_ranking_row_values_and_trend(ranking: str) -> None:
    row = text(ranking.split('data-code="ST-016"', 1)[1].split("</tr>", 1)[0])
    # TASK §12.5: 70 ks, 13.2 % zaznamenaných, 6.3 % všetkých strát, Availability −0.76 p. b., trend ↑
    for part in ("Vision station interrupted operation", "Camera malfunction", "70", "13.2 %", "6.3 %", "↑"):
        assert part in row, part


@pytest.mark.golden
def test_ranking_shows_linked_defect_and_combined_impact_outside_score(ranking: str) -> None:
    row = text(ranking.split('data-code="ST-038"', 1)[1].split("</tr>", 1)[0])
    assert "Q-030" in row and "102.4" in row  # §12.8: 100 ks + extra 2,4 ks
    q030 = text(ranking.split('data-code="Q-030"', 1)[1].split("</tr>", 1)[0])
    assert "ST-038" in q030 and "ST-047" in q030
    # súhrnný vplyv nemení poradie (ST-038 je prvý aj bez neho, Q-030 zostáva posledný)
    assert re.findall(r'data-code="([\w-]+)" data-class', ranking)[-1] == "Q-030"


# --- Links (§8.6, §12.8) -------------------------------------------------------------------------


@pytest.mark.golden
def test_links_table_has_exactly_the_five_pairs(links: str) -> None:
    pairs = set(re.findall(r'<tr data-cause="([\w-]+)" data-effect="([\w-]+)"', links))
    assert pairs == LINKS


@pytest.mark.golden
def test_link_row_values(links: str) -> None:
    row = text(links.split('data-cause="ST-038" data-effect="Q-030"', 1)[1].split("</tr>", 1)[0])
    # TASK §12.8: support 4, Q v okne 3 / 228, 1.32 % vs 0.27 %, lift 4.8, extra 2.4, same_process, low
    for part in ("4", "3", "228", "1.32 %", "0.27 %", "4.8", "2.4", "same process", "Camera", "low"):
        assert part in row, part
    assert "not a proven cause" in text(links).lower()  # korelácia ≠ príčina


def test_links_page_without_data_says_insufficient(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, db_path=tmp_path / "e.db", ai_enabled=False)  # type: ignore[call-arg]
    with TestClient(create_app(settings)) as c:
        assert "No links in this period" in c.get("/history/links", params={"month": "2026-11"}).text
        assert "No ranked problems" in c.get("/history/ranking", params={"month": "2026-11"}).text


def test_tabs_offer_ranking_and_links(client: TestClient) -> None:
    page = client.get("/history").text
    assert 'href="/history/ranking?month=' in page and 'href="/history/links?month=' in page


# --- odznak na dashboarde zmeny (§8.6 „Kde je to vidieť") ---------------------------------------


@pytest.mark.golden
def test_dashboard_events_show_linked_defect_badge(client: TestClient) -> None:
    page = client.get("/shift/L01-20261125-M").text
    st038 = text(page.split("ST-038", 1)[1].split("</tr>", 1)[0])
    assert "linked defect Q-030" in st038
    # ST-046 → Q-020 je väzba v novembri; obe udalosti ST-046 majú odznak
    assert text(page).count("linked defect Q-020") == 2


@pytest.mark.golden
def test_month_page_has_speed_loss_by_hour_target_of_pinned_link(client: TestClient) -> None:
    page = client.get("/history/month", params={"month": "2026-11"}).text
    block = text(page.split('id="speed-by-hour"', 1)[1].split("</table>", 1)[0])
    assert "579" in block and "52.3 %" in block  # TASK §12.1, §12.4
    assert "1 115 88.5 %" in block and "5 80 86.9 %" in block  # najslabšie hodiny 1 a 5

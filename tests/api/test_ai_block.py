"""P0-24: AI blok v UI — Shift Summary (§7.F), vysvetlenia väzieb (§8.6), polling, fallback bez Ollama."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from oee.ai.client import FakeGenerator
from oee.config import PROJECT_ROOT, Settings
from oee.persistence.models import AiOutput
from oee.web.app import create_app

DATASET = PROJECT_ROOT / "data" / "raw" / "dummy_data.xlsx"
S25 = "L01-20261125-M"
SUMMARY = f"Shift {S25}: OEE 78.2 % below the 85 % goal; longest problem ST-038, 25 min at 09:08."
SIX: dict[str, str | list[str]] = {  # iná konfigurácia než príklad (D8)
    "product": "P02", "rate_per_hour": "45", "start": "14:00", "duration_h": "2", "break_min": "0",
    "break_hour_no": "1", "break_offset_min": "0", "am_min": "0", "am_hour_no": "1", "am_offset_min": "0",
    "target_oee_pct": "80", "working_days": ["0", "1", "2", "3", "4", "5", "6"], "grace_min": "0",
}  # fmt: skip


def make(tmp_path: Path, *, ai_enabled: bool = True) -> TestClient:
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None, db_path=tmp_path / "oee.db", dataset_path=DATASET, ai_enabled=ai_enabled
    )
    return TestClient(create_app(settings))


@pytest.fixture
def imported(tmp_path: Path) -> Iterator[TestClient]:
    if not DATASET.is_file():
        pytest.skip("dataset data/raw/dummy_data.xlsx missing")
    with make(tmp_path) as c:
        assert c.post("/import").status_code == 200
        yield c


def rows(client: TestClient) -> list[AiOutput]:
    with client.app.state.session_factory() as s:  # type: ignore[attr-defined]
        return list(s.scalars(select(AiOutput)))


# --- Shift Summary -------------------------------------------------------------------------------


@pytest.mark.golden
def test_dashboard_loads_ai_block_lazily(imported: TestClient) -> None:
    page = imported.get(f"/shift/{S25}").text
    assert "F · Shift summary" in page
    assert re.search(rf'hx-get="/ai/shift_summary/{S25}"[^>]*hx-trigger="load"', page)


@pytest.mark.golden
def test_imported_shift_gets_ai_output_on_first_open_and_polling_stops(imported: TestClient) -> None:
    fake = FakeGenerator([{"text": SUMMARY}])
    imported.app.state.ai_client = fake  # type: ignore[attr-defined]
    first = imported.get(f"/ai/shift_summary/{S25}")
    assert first.status_code == 200 and "<html" not in first.text
    assert 'hx-trigger="every 3s"' in first.text  # pending → polling
    assert "Local AI is writing" in first.text and "OEE 78.2 %" in first.text  # medzitým fallback (§7.F)
    # BackgroundTasks v TestClient dobehnú pred návratom odpovede → výstup je uložený
    saved = rows(imported)
    assert [(r.kind, r.subject_key, r.status) for r in saved] == [("shift_summary", S25, "ok")]
    second = imported.get(f"/ai/shift_summary/{S25}")
    assert SUMMARY in second.text and "local AI" in second.text
    assert "hx-trigger" not in second.text  # polling sa zastavil
    assert len(fake.calls) == 1


@pytest.mark.golden
def test_invalid_ai_text_shows_template(imported: TestClient) -> None:
    imported.app.state.ai_client = FakeGenerator([{"text": "OEE 99.9 %."}])  # type: ignore[attr-defined]
    imported.get(f"/ai/shift_summary/{S25}")
    page = imported.get(f"/ai/shift_summary/{S25}").text
    assert "99.9" not in page and "OEE 78.2 %" in page and "template" in page
    assert [r.status for r in rows(imported)] == ["fallback"]


@pytest.mark.golden
def test_without_ollama_pages_work_and_show_template(tmp_path: Path) -> None:
    if not DATASET.is_file():
        pytest.skip("dataset missing")
    with make(tmp_path, ai_enabled=False) as c:
        c.post("/import")
        assert c.get(f"/shift/{S25}").status_code == 200
        block = c.get(f"/ai/shift_summary/{S25}").text
        assert "OEE 78.2 %" in block and "hx-trigger" not in block and "template" in block
        assert c.get("/health").json()["ai"]["enabled"] is False
        assert rows(c) == []


def test_unknown_shift_ai_block_is_404(tmp_path: Path) -> None:
    with make(tmp_path) as c:
        assert c.get("/ai/shift_summary/L01-20991231-M").status_code == 404


def test_completing_a_shift_generates_summary_in_background(tmp_path: Path) -> None:
    with make(tmp_path) as c:
        fake = FakeGenerator([{"text": "Shift L01-20261209-M is complete."}])
        c.app.state.ai_client = fake  # type: ignore[attr-defined]
        c.post("/settings/model", data=SIX)
        shift = c.post("/report", data={"day": "2026-12-09"}, follow_redirects=False).headers["location"]
        assert c.post(f"{shift}/hour/1", data={"produced": "40"}, follow_redirects=False).status_code == 303
        assert rows(c) == []  # zmena ešte nie je dokončená
        assert c.post(f"{shift}/hour/2", data={"produced": "40"}, follow_redirects=False).status_code == 303
        assert [(r.subject_key, r.status) for r in rows(c)] == [("L01-20261209-M", "ok")]
        assert "Shift L01-20261209-M is complete." in c.get("/ai/shift_summary/L01-20261209-M").text


def test_health_with_fake_generator_does_not_fail(tmp_path: Path) -> None:
    with make(tmp_path) as c:
        c.app.state.ai_client = FakeGenerator([{"text": "x"}])  # type: ignore[attr-defined]
        assert c.get("/health").json()["status"] == "ok"


# --- vysvetlenia väzieb (§8.6, D1) ---------------------------------------------------------------


@pytest.mark.golden
def test_correlations_loads_explanation_for_selected_pair(imported: TestClient) -> None:
    page = imported.get("/correlations", params={"view": "month", "month": "2026-11"}).text
    assert re.findall(r'hx-get="/ai/link_explanation/2026-11/(ST-\d{3})/(Q-\d{3})"', page) == [
        ("ST-038", "Q-030")
    ]


@pytest.mark.golden
def test_link_explanation_block(imported: TestClient) -> None:
    answer = {
        "fact": "After 4 stops of ST-038 there were 3 pcs of Q-030 on 228 parts.",
        "link": "Lift 4.8×, same process (Camera), confidence low.",
        "hypothesis": "Unstable light may cause false rejects — to be verified, not a proven cause.",
        "impact": "Combined impact about 102.4 pcs.",
    }
    imported.app.state.ai_client = FakeGenerator([answer])  # type: ignore[attr-defined]
    imported.get("/ai/link_explanation/2026-11/ST-038/Q-030")
    block = imported.get("/ai/link_explanation/2026-11/ST-038/Q-030").text
    for value in answer.values():
        assert value in block
    assert "hx-trigger" not in block


@pytest.mark.golden
def test_link_explanation_for_non_link_pair_is_404(imported: TestClient) -> None:
    assert imported.get("/ai/link_explanation/2026-11/ST-046/Q-031").status_code == 404  # §12.8: nie je väzba
    assert imported.get("/ai/link_explanation/2026-13/ST-038/Q-030").status_code == 422

"""P0-25: demo podľa TASK §14 bez siete (DoD 9, 10, 12) — Ollama nedostupné, všetko funguje s fallbackom.

Zablokované sú všetky spojenia mimo loopback a aj port Ollama (= bez internetu, Ollama nebeží).
Loopback ostáva povolený iba pre interný `socketpair` asyncio na Windows.
Aplikácia beží so skutočným `OllamaClient` (AI zapnuté).
"""

from __future__ import annotations

import socket
from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from oee.ai.client import OllamaClient
from oee.config import PROJECT_ROOT, Settings
from oee.services.demo import build_demo_shift, ensure_active_model
from oee.web.app import create_app

DATASET = PROJECT_ROOT / "data" / "raw" / "dummy_data.xlsx"
DEMO_DAY = date(2026, 12, 1)
NOW = datetime(2026, 12, 1, 16, 0)
LOOPBACK = {"127.0.0.1", "::1"}
OLLAMA_PORT = 11434


@pytest.fixture
def no_network(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    attempts: list[Any] = []
    original = socket.socket.connect

    def blocked(address: Any) -> bool:
        host, port = (address[0], address[1]) if isinstance(address, tuple) else ("", 0)
        return host not in LOOPBACK or port == OLLAMA_PORT

    def connect(self: socket.socket, address: Any) -> None:
        if blocked(address):
            attempts.append(address)
            raise OSError(f"network disabled in test: {address}")
        original(self, address)

    def create_connection(address: Any, *args: Any, **kwargs: Any) -> socket.socket:
        attempts.append(address)
        raise OSError(f"network disabled in test: {address}")

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket, "create_connection", create_connection)
    return attempts


@pytest.fixture
def demo(tmp_path: Path, no_network: list[Any]) -> Iterator[TestClient]:
    if not DATASET.is_file():
        pytest.skip("dataset data/raw/dummy_data.xlsx missing")
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None, db_path=tmp_path / "oee.db", dataset_path=DATASET, ai_enabled=True, ai_timeout_s=1
    )
    with TestClient(create_app(settings)) as client:
        assert isinstance(client.app.state.ai_client, OllamaClient)  # type: ignore[attr-defined]
        assert client.post("/import").status_code == 200
        with client.app.state.session_factory() as s:  # type: ignore[attr-defined]
            ensure_active_model(s, line="L01", now=NOW)
            build_demo_shift(s, line="L01", day=DEMO_DAY, now=NOW)
        yield client


@pytest.mark.golden
def test_demo_scenario_works_offline(demo: TestClient, no_network: list[Any]) -> None:
    # §14.2 mesiac november, §14.3 dashboard 25.11.
    month = demo.get("/history/month", params={"month": "2026-11"})
    assert month.status_code == 200 and "88.0 %" in month.text
    shift = demo.get("/shift/L01-20261125-M")
    assert shift.status_code == 200 and "78.2" in shift.text

    # §14.4 ručne zadaná zmena je v histórii, §14.5 väzba ST-038 → Q-030 a jej vysvetlenie
    links = demo.get("/history/links", params={"month": "2026-12"}).text
    assert 'hx-get="/ai/link_explanation/2026-12/ST-038/Q-030"' in links
    block = demo.get("/ai/link_explanation/2026-12/ST-038/Q-030")
    assert block.status_code == 200 and "ST-038" in block.text
    # prvé volanie rezervuje generovanie (pending), BackgroundTasks v TestClient dobehne → druhé = fallback
    summary = demo.get("/ai/shift_summary/L01-20261201-M")
    assert (
        summary.status_code == 200
        and "Text from the template" in demo.get("/ai/shift_summary/L01-20261201-M").text
    )

    health = demo.get("/health").json()
    assert health["status"] == "ok" and health["ai"]["available"] is False
    assert no_network, "the app tried to reach Ollama — the guard must have been exercised"

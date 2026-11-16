"""P0-24: orchestrácia AI — cache podľa faktov, pending ako zámok, beh na pozadí, fallback."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime, time, timedelta

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from oee.ai.client import AiTimeout, FakeGenerator
from oee.catalog.loader import load_catalog
from oee.domain.shift_model import Allowance, ShiftModelConfig
from oee.persistence.db import make_session_factory
from oee.persistence.models import AiOutput
from oee.persistence.seed import seed_codebook
from oee.services.ai_orchestrator import AiConfig, lookup, run_job, shift_summary_job
from tests.builders import add_issue, add_shift

CATALOG = load_catalog()
NOW = datetime(2026, 12, 10, 8, 0)
CONFIG = AiConfig(model="qwen2.5:3b", lang="en", stale_after=timedelta(seconds=60))
SIX = ShiftModelConfig(  # iná konfigurácia než príklad (D8)
    rate_per_hour=45,
    start=time(14, 0),
    duration_min=360,
    break_=Allowance(minutes=20, hour_no=3, offset_min=10),
    am=Allowance(minutes=15, hour_no=1),
    target_oee=0.8,
    working_days=frozenset({0, 2, 4}),
)
SHIFT = "L01-20261209-M"


@pytest.fixture
def factory(engine: Engine) -> Iterator[sessionmaker[Session]]:
    f = make_session_factory(engine)
    with f() as s:
        seed_codebook(s, CATALOG)
        add_shift(s, SIX, date(2026, 12, 9), {h: (40, 1) for h in range(1, 7)}, status="completed")
        add_issue(s, date(2026, 12, 9), 2, "ST-046", 7, datetime(2026, 12, 9, 15, 20))
        s.commit()
    yield f


def count(factory: sessionmaker[Session]) -> int:
    with factory() as s:
        return int(s.scalar(select(func.count()).select_from(AiOutput)) or 0)


def job(factory: sessionmaker[Session]):  # type: ignore[no-untyped-def]
    with factory() as s:
        return shift_summary_job(s, SHIFT, catalog=CATALOG, config=CONFIG, now=NOW)


def test_first_lookup_claims_pending_and_shows_fallback(factory: sessionmaker[Session]) -> None:
    j = job(factory)
    with factory() as s:
        state = lookup(s, j, config=CONFIG, now=NOW, ai_enabled=True)
        s.commit()
    assert state.status == "start" and state.pending
    assert "L01-20261209-M" in state.payload["text"]  # medzitým fallback text
    assert count(factory) == 1


def test_background_run_stores_valid_ai_output(factory: sessionmaker[Session]) -> None:
    j = job(factory)
    fake = FakeGenerator([{"text": f"Shift {SHIFT}: produced 240 pieces."}])
    with factory() as s:
        lookup(s, j, config=CONFIG, now=NOW, ai_enabled=True)
        s.commit()
    run_job(factory, j, fake, config=CONFIG, now=lambda: NOW)
    with factory() as s:
        state = lookup(s, j, config=CONFIG, now=NOW, ai_enabled=True)
    assert (state.status, state.source, state.pending) == ("ready", "local_ai", False)
    assert state.payload["text"] == f"Shift {SHIFT}: produced 240 pieces."
    assert len(fake.calls) == 1


def test_invalid_ai_output_is_stored_as_fallback(factory: sessionmaker[Session]) -> None:
    j = job(factory)
    fake = FakeGenerator([{"text": "OEE 99.9 %."}])
    with factory() as s:
        lookup(s, j, config=CONFIG, now=NOW, ai_enabled=True)
        s.commit()
    run_job(factory, j, fake, config=CONFIG, now=lambda: NOW)
    with factory() as s:
        row = s.scalar(select(AiOutput))
        state = lookup(s, j, config=CONFIG, now=NOW, ai_enabled=True)
    assert row is not None and row.status == "fallback"
    assert (state.status, state.source) == ("ready", "template")
    assert len(fake.calls) == 2  # 1 opakovanie


def test_same_facts_are_not_generated_again(factory: sessionmaker[Session]) -> None:
    j = job(factory)
    fake = FakeGenerator([{"text": "Shift ok."}])
    with factory() as s:
        lookup(s, j, config=CONFIG, now=NOW, ai_enabled=True)
        s.commit()
    run_job(factory, j, fake, config=CONFIG, now=lambda: NOW)
    with factory() as s:
        assert lookup(s, job(factory), config=CONFIG, now=NOW, ai_enabled=True).status == "ready"
    assert count(factory) == 1 and len(fake.calls) == 1


def test_changed_facts_get_a_new_entry(factory: sessionmaker[Session]) -> None:
    first = job(factory)
    with factory() as s:
        lookup(s, first, config=CONFIG, now=NOW, ai_enabled=True)
        add_issue(s, date(2026, 12, 9), 4, "ST-038", 9, datetime(2026, 12, 9, 17, 5))  # oprava zmeny
        s.commit()
    second = job(factory)
    assert second.key.facts_hash != first.key.facts_hash
    with factory() as s:
        assert lookup(s, second, config=CONFIG, now=NOW, ai_enabled=True).status == "start"
        s.commit()
    assert count(factory) == 2


def test_two_concurrent_requests_generate_once_without_integrity_error(
    factory: sessionmaker[Session],
) -> None:
    j = job(factory)
    with factory() as a, factory() as b:
        first = lookup(a, j, config=CONFIG, now=NOW, ai_enabled=True)
        a.commit()
        second = lookup(b, j, config=CONFIG, now=NOW + timedelta(seconds=1), ai_enabled=True)
        b.commit()
    assert (first.status, second.status) == ("start", "pending")  # iba prvý spustí generovanie
    assert count(factory) == 1


def test_stale_pending_is_started_again(factory: sessionmaker[Session]) -> None:
    j = job(factory)
    with factory() as s:
        lookup(s, j, config=CONFIG, now=NOW, ai_enabled=True)
        s.commit()
    with factory() as s:  # proces s generovaním padol
        state = lookup(s, j, config=CONFIG, now=NOW + timedelta(seconds=61), ai_enabled=True)
        s.commit()
    assert state.status == "start"


def test_ollama_down_stores_fallback(factory: sessionmaker[Session]) -> None:
    j = job(factory)
    with factory() as s:
        lookup(s, j, config=CONFIG, now=NOW, ai_enabled=True)
        s.commit()
    run_job(factory, j, FakeGenerator([AiTimeout("slow")]), config=CONFIG, now=lambda: NOW)
    with factory() as s:
        state = lookup(s, j, config=CONFIG, now=NOW, ai_enabled=True)
    assert (state.status, state.source) == ("ready", "template")


def test_ai_disabled_returns_template_without_db_rows(factory: sessionmaker[Session]) -> None:
    with factory() as s:
        state = lookup(s, job(factory), config=CONFIG, now=NOW, ai_enabled=False)
    assert (state.status, state.source, state.pending) == ("ready", "template", False)
    assert count(factory) == 0


def test_ollama_down_is_retried_after_stale_period(factory: sessionmaker[Session]) -> None:
    j = job(factory)
    with factory() as s:
        lookup(s, j, config=CONFIG, now=NOW, ai_enabled=True)
        s.commit()
    run_job(factory, j, FakeGenerator([AiTimeout("slow")]), config=CONFIG, now=lambda: NOW)
    with factory() as s:
        row = s.scalar(select(AiOutput))
        assert row is not None and row.status == "error"  # nedostupnosť sa nekešuje natrvalo
        soon = lookup(s, j, config=CONFIG, now=NOW + timedelta(seconds=30), ai_enabled=True)
        assert (soon.status, soon.source) == ("ready", "template")  # krátko po chybe neskúšať znova
        later = lookup(s, j, config=CONFIG, now=NOW + timedelta(seconds=61), ai_enabled=True)
        s.commit()
    assert later.status == "start"  # Ollama mohla medzitým naštartovať
    run_job(factory, j, FakeGenerator([{"text": "Shift ok."}]), config=CONFIG, now=lambda: NOW)
    with factory() as s:
        state = lookup(s, j, config=CONFIG, now=NOW, ai_enabled=True)
    assert (state.status, state.source, state.payload) == ("ready", "local_ai", {"text": "Shift ok."})

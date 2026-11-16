"""Spoločné pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from oee.persistence.db import init_db, make_engine, make_session_factory


@pytest.fixture
def engine() -> Iterator[Engine]:
    """Izolovaná in-memory SQLite (StaticPool) so schémou; nikdy nie data/local/oee.db."""
    eng = make_engine(None)
    init_db(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    factory = make_session_factory(engine)
    with factory() as s:
        yield s

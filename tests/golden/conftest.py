"""Spoločný import datasetu pre golden testy analytiky (jeden import na celé sedenie testov)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime

import pytest
from sqlalchemy.orm import Session

from oee.catalog.loader import Catalog, load_catalog
from oee.config import PROJECT_ROOT
from oee.contracts.period_analytics import PeriodAnalytics
from oee.persistence.db import init_db, make_engine, make_session_factory
from oee.persistence.seed import seed_codebook
from oee.services.analytics import build_period
from oee.services.importer import import_excel

DATASET = PROJECT_ROOT / "data" / "raw" / "dummy_data.xlsx"
IMPORT_NOW = datetime(2026, 12, 1, 8, 0)


@pytest.fixture(scope="session")
def catalog() -> Catalog:
    return load_catalog()


@pytest.fixture(scope="session")
def golden_db(catalog: Catalog) -> Iterator[Session]:
    """In-memory DB s importovaným datasetom (iba na čítanie v testoch)."""
    if not DATASET.is_file():
        pytest.skip("dataset data/raw/dummy_data.xlsx missing")
    engine = make_engine(None)
    init_db(engine)
    session = make_session_factory(engine)()
    seed_codebook(session, catalog)
    session.commit()
    import_excel(session, DATASET, now=IMPORT_NOW)
    yield session
    session.close()
    engine.dispose()


@pytest.fixture(scope="session")
def month(golden_db: Session, catalog: Catalog) -> PeriodAnalytics:
    """PeriodAnalytics za november 2026 (spoločné pre golden testy obdobia, rebríčka a väzieb)."""
    return build_period(
        golden_db,
        date(2026, 11, 1),
        date(2026, 11, 30),
        line="L01",
        period_type="month",
        catalog=catalog,
        now=datetime(2026, 12, 1, 9, 0),
    )

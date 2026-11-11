"""P0-09 (golden): import datasetu organizátorov (TASK §11.7, §11.8, §16 bod 3; docs/TESTING.md §3).

Excel sa iba číta; test overí, že sa súbor importom nezmení (CLAUDE.md pravidlo 9).
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import datetime, time

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from oee.catalog.loader import load_catalog
from oee.config import PROJECT_ROOT
from oee.domain.shift_model import build_shift_plan, config_from_snapshot
from oee.persistence.db import init_db, make_engine, make_session_factory
from oee.persistence.models import HourlyReportRow, IssueEvent, ProductionRecord, QualityRecord, Shift
from oee.persistence.seed import seed_codebook
from oee.services.importer import ImportResult, import_excel

DATASET = PROJECT_ROOT / "data" / "raw" / "dummy_data.xlsx"
NOW = datetime(2026, 12, 1, 8, 0)

pytestmark = [
    pytest.mark.golden,
    pytest.mark.skipif(not DATASET.is_file(), reason="dataset data/raw/dummy_data.xlsx missing"),
]


def sha256() -> str:
    return hashlib.sha256(DATASET.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def imported() -> Iterator[tuple[Session, ImportResult, ImportResult, str, str]]:
    engine = make_engine(None)
    init_db(engine)
    session = make_session_factory(engine)()
    seed_codebook(session, load_catalog())
    session.commit()
    before = sha256()
    first = import_excel(session, DATASET, now=NOW)
    second = import_excel(session, DATASET, now=NOW)
    after = sha256()
    yield session, first, second, before, after
    session.close()
    engine.dispose()


def count(s: Session, model: type) -> int:
    return int(s.scalar(select(func.count()).select_from(model)) or 0)


def test_counts(imported: tuple[Session, ImportResult, ImportResult, str, str]) -> None:
    session, first, _, _, _ = imported
    # TASK §11.2, §16 bod 3: 21 zmien / 168 hodín / 33 udalostí / 112 záznamov zmätkov
    assert (first.shifts_added, first.hours_added, first.issues_added, first.quality_added) == (
        21,
        168,
        33,
        112,
    )
    assert (count(session, Shift), count(session, HourlyReportRow), count(session, ProductionRecord)) == (
        21,
        168,
        168,
    )
    assert count(session, IssueEvent) == 33
    assert count(session, QualityRecord) == 112
    assert session.scalar(select(func.sum(QualityRecord.qty))) == 119  # TASK §11.2
    assert session.scalar(select(func.sum(ProductionRecord.produced_qty))) == 8251  # TASK §12.1
    assert session.scalar(select(func.sum(IssueEvent.duration_min))) == pytest.approx(410)  # TASK §12.1


def test_reimport_adds_nothing(imported: tuple[Session, ImportResult, ImportResult, str, str]) -> None:
    session, _, second, _, _ = imported
    assert (second.shifts_added, second.hours_added, second.issues_added, second.quality_added) == (
        0,
        0,
        0,
        0,
    )
    assert second.hours_skipped == 168
    assert count(session, IssueEvent) == 33 and count(session, QualityRecord) == 112


def test_derived_model_for_every_shift(
    imported: tuple[Session, ImportResult, ImportResult, str, str],
) -> None:
    session, first, _, _, _ = imported
    assert len(first.models) == 21
    for shift_id, model in first.models.items():
        # PLANNING P0-09 AC: 60 ks/h, 06:00, 480 min, prestávka 30 (hod. 5), AM 10 (hod. 1), cieľ 0,85, Po–Pi
        assert model.rate_per_hour == pytest.approx(60), shift_id
        assert model.start == time(6, 0)
        assert model.duration_min == 480
        assert (model.break_.minutes, model.break_.hour_no) == (30, 5)
        assert (model.am.minutes, model.am.hour_no) == (10, 1)
        assert model.target_oee == pytest.approx(0.85)
        assert model.working_days == frozenset({0, 1, 2, 3, 4})
        shift = session.get(Shift, shift_id)
        assert shift is not None and shift.status == "completed" and shift.revision == 0
        assert config_from_snapshot(shift.model_snapshot) == model
        assert build_shift_plan(model, shift.date).target == pytest.approx(440)  # TASK §3.2


def test_integrity_checks_pass_for_all_shifts(
    imported: tuple[Session, ImportResult, ImportResult, str, str],
) -> None:
    _, first, _, _, _ = imported
    assert len(first.checks) == 21
    for check in first.checks:
        # TASK §11.7: Plan = Interval − AM − Pauza, Bilancia_s = 0, Kontrola_ks = 0, NOK a prestoje sedia,
        # A/P/Q v [0, 1], Kontrola_zmien = SEDI a OEE sa zhoduje
        assert check.ok, (check.shift_id, check.checks)
        assert all(v is True for v in check.checks.values()), (check.shift_id, check.checks)


def test_issue_details(imported: tuple[Session, ImportResult, ImportResult, str, str]) -> None:
    session, _, _, _, _ = imported
    st038 = session.scalars(select(IssueEvent).where(IssueEvent.issue_type_code == "ST-038")).all()
    # TASK §12.6 P-1/P-2: ST-038 — streda, 4/4, o 09:08, 25 min
    assert sorted(e.start_at.strftime("%d.%m %H:%M") for e in st038 if e.start_at) == [
        "04.11 09:08",
        "11.11 09:08",
        "18.11 09:08",
        "25.11 09:08",
    ]
    assert all(e.duration_min == pytest.approx(25) for e in st038)
    assert all(e.external_ref and e.source == "import" and e.client_key is None for e in st038)


def test_excel_file_unchanged(imported: tuple[Session, ImportResult, ImportResult, str, str]) -> None:
    _, _, _, before, after = imported
    assert before == after  # CLAUDE.md pravidlo 9

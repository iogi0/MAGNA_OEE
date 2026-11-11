"""P0-13: build_period na syntetických zmenách — rôzne modely (D8), vylúčenie neúplných zmien, týždne."""

from __future__ import annotations

from datetime import date, datetime, time

import pytest
from sqlalchemy.orm import Session

from oee.catalog.loader import Catalog, load_catalog
from oee.domain.kpi import Cascade, sum_cascades
from oee.domain.shift_model import Allowance, ShiftModelConfig
from oee.persistence.seed import seed_codebook
from oee.services.analytics import build_period
from tests.builders import add_issue, add_shift

NOW = datetime(2026, 12, 20, 8, 0)
MODEL_A = ShiftModelConfig(  # 8 h, 60 ks/h, cieľ 0,85
    rate_per_hour=60,
    start=time(6, 0),
    duration_min=480,
    break_=Allowance(minutes=30, hour_no=5),
    am=Allowance(minutes=10, hour_no=1),
    target_oee=0.85,
    working_days=frozenset({0, 1}),
)
MODEL_B = ShiftModelConfig(  # 6 h, 45 ks/h, cieľ 0,8
    rate_per_hour=45,
    start=time(14, 0),
    duration_min=360,
    break_=Allowance(minutes=20, hour_no=3, offset_min=10),
    am=Allowance(minutes=15, hour_no=1),
    target_oee=0.8,
    working_days=frozenset({0, 1}),
)
MON, TUE = date(2026, 12, 7), date(2026, 12, 8)


@pytest.fixture
def catalog() -> Catalog:
    return load_catalog()


@pytest.fixture
def db(session: Session, catalog: Catalog) -> Session:
    seed_codebook(session, catalog)
    add_shift(session, MODEL_A, MON, {h: (50, 1) for h in range(1, 9)}, status="completed", retests=2)
    add_shift(session, MODEL_B, TUE, {h: (35, 0) for h in range(1, 7)}, status="completed", retests=None)
    add_issue(session, MON, 2, "ST-038", 10, datetime(2026, 12, 7, 7, 10))
    return session


def period(db: Session, catalog: Catalog, start: date = MON, end: date = TUE) -> object:
    return build_period(db, start, end, line="L01", period_type="range", catalog=catalog, now=NOW)


def test_period_of_two_models_uses_sums(db: Session, catalog: Catalog) -> None:
    pa = period(db, catalog)
    target_a, target_b = 440.0, 243.75
    assert pa.totals.target_pcs == pytest.approx(target_a + target_b)  # target = Σ targetov zmien
    # cieľ obdobia = Σ (target × cieľ) / Σ target
    goal = (target_a * 0.85 + target_b * 0.8) / (target_a + target_b)
    assert pa.totals.oee_goal_pcs == pytest.approx(target_a * 0.85 + target_b * 0.8)
    expected = sum_cascades(
        [
            Cascade.from_minutes(planned_min=440, downtime_min=10, produced=400, rejects=8, ideal_cycle_s=60),
            Cascade.from_minutes(planned_min=325, downtime_min=0, produced=210, rejects=0, ideal_cycle_s=80),
        ]
    )
    assert pa.kpi.oee == pytest.approx(expected.oee)
    assert pa.kpi.availability == pytest.approx(expected.availability)
    assert pa.kpi.oee_gap_pp == pytest.approx((expected.oee - goal) * 100)  # type: ignore[operator]
    assert pa.totals.planned_min == 765


def test_first_pass_quality_only_when_retests_recorded_everywhere(db: Session, catalog: Catalog) -> None:
    assert period(db, catalog).kpi.first_pass_quality is None  # zmena B nemá retesty
    pa = period(db, catalog, start=MON, end=MON)
    assert pa.kpi.first_pass_quality == pytest.approx((392 - 16) / 400)  # (Good − retesty) / Produced


def test_incomplete_shifts_are_excluded(db: Session, catalog: Catalog) -> None:
    add_shift(db, MODEL_A, date(2026, 12, 9), {1: (50, 0)}, status="in_progress")
    pa = period(db, catalog, end=date(2026, 12, 9))
    assert (pa.period.shifts_completed, pa.period.shifts_excluded_incomplete) == (2, 1)
    assert len(pa.shift_series) == 2


def test_week_complete_when_every_working_day_has_completed_shift(db: Session, catalog: Catalog) -> None:
    weeks = period(db, catalog).weekly
    assert [(w.iso_week, w.shifts, w.partial) for w in weeks] == [(50, 2, False)]  # pracovné dni Po, Ut
    weeks = period(db, catalog, end=MON).weekly
    assert [(w.iso_week, w.partial) for w in weeks] == [(50, True)]  # utorok mimo obdobia


def test_empty_period(db: Session, catalog: Catalog) -> None:
    pa = period(db, catalog, start=date(2027, 1, 1), end=date(2027, 1, 31))
    assert pa.period.shifts_completed == 0
    assert pa.kpi.oee is None
    assert pa.problem_ranking == () and pa.problem_links == () and pa.weekly == ()


def test_ranking_and_stats_present(db: Session, catalog: Catalog) -> None:
    pa = period(db, catalog)
    assert [s.code for s in pa.issue_stats] == ["ST-038"]
    assert pa.issue_stats[0].lost_pcs == pytest.approx(10)
    assert {r.code for r in pa.problem_ranking} == {"ST-038", "unspecified_defect"}  # zmätky bez rozpisu
    assert pa.defect_stats == ()  # „Unspecified" nemá kód zmätku

"""P0-10: build_shift na syntetickej zmene — iná konfigurácia (D8), provisional, pokračovanie, soft delete."""

from __future__ import annotations

import math
from datetime import date, datetime, time

import pytest
from sqlalchemy.orm import Session

from oee.catalog.loader import load_catalog
from oee.domain.shift_model import Allowance, ShiftModelConfig
from oee.persistence.models import IssueEvent
from oee.persistence.repositories import QualityLine, replace_hour_quality, soft_delete_issue
from oee.persistence.seed import seed_codebook
from oee.services.analytics import ShiftNotFound, build_shift
from tests import builders
from tests.builders import add_shift

DAY = date(2026, 12, 9)  # streda
NOW = datetime(2026, 12, 9, 18, 0)
CATALOG = load_catalog()
CONFIG = (
    ShiftModelConfig(  # 6 h od 14:00, 45 ks/h (takt 80 s), AM 15 min v 1. hod., prestávka 20 min v 3. hod.
        rate_per_hour=45,
        start=time(14, 0),
        duration_min=360,
        break_=Allowance(minutes=20, hour_no=3, offset_min=10),
        am=Allowance(minutes=15, hour_no=1),
        target_oee=0.8,
        working_days=frozenset({0, 2, 4}),
    )
)
SHIFT_ID = "L01-20261209-M"


def make_shift(s: Session, hours: dict[int, tuple[int, int]], status: str = "in_progress") -> None:
    add_shift(s, CONFIG, DAY, hours, status=status)


def add_issue(
    s: Session, hour_no: int, code: str, minutes: float, start: datetime | None, **kw: object
) -> IssueEvent:
    return builders.add_issue(s, DAY, hour_no, code, minutes, start, **kw)


@pytest.fixture
def db(session: Session) -> Session:
    seed_codebook(session, CATALOG)
    return session


def test_unknown_shift(db: Session) -> None:
    with pytest.raises(ShiftNotFound):
        build_shift(db, "L01-20990101-M", catalog=CATALOG, now=NOW)


def test_provisional_shift_uses_submitted_hours_only(db: Session) -> None:
    make_shift(db, {1: (30, 0), 2: (40, 1), 3: (25, 0)})  # 3 zo 6 hodín
    sa = build_shift(db, SHIFT_ID, catalog=CATALOG, now=NOW)
    assert (sa.shift.status, sa.shift.provisional, sa.shift.hours_submitted, sa.shift.hours_total) == (
        "in_progress",
        True,
        3,
        6,
    )
    assert sa.model.calendar_min == 360 and sa.model.planned_min == 325 and sa.model.ideal_cycle_s == 80
    # target odoslaných hodín: (45 + 60 + 40) min × 45 / 60 = 108,75 ks
    assert sa.target_vs_actual.target_pcs == pytest.approx(108.75)
    assert sa.target_vs_actual.produced_pcs == 95
    assert sa.kpi.oee == pytest.approx(94 / 108.75)
    assert [r.hour_no for r in sa.hourly] == [1, 2, 3, 4, 5, 6]
    missing = sa.hourly[4]
    assert (missing.produced, missing.oee, missing.flags) == (None, None, ("not_submitted",))
    assert missing.target_pcs == pytest.approx(45)  # plán hodiny je známy aj bez hlásenia
    assert list(sa.quality.by_hour) == [0, 1, 0, None, None, None]


def test_other_config_downtime_excludes_break_and_handles_continuation(db: Session) -> None:
    make_shift(db, {h: (30, 0) for h in range(1, 7)}, status="completed")
    root = add_issue(db, 3, "ST-046", 30, datetime(2026, 12, 9, 16, 0))  # 16:00–16:30, prestávka 16:10–16:30
    add_issue(db, 4, "ST-046", 10, datetime(2026, 12, 9, 17, 0), continues_issue_id=root.issue_id)
    sa = build_shift(db, SHIFT_ID, catalog=CATALOG, now=NOW)
    tl = sa.technical_losses
    assert tl.total_min == pytest.approx(20)  # 10 (bez prestávky) + 10
    assert tl.events == 1  # pokračovanie = jedna udalosť
    assert [(c.category, c.min, c.events) for c in tl.by_category] == [
        ("Leak test issue", pytest.approx(20), 1)
    ]
    assert sa.waterfall_pcs.technical_losses == pytest.approx(20 * 60 / 80)
    assert [i.flags for i in sa.issues] == [("over_5_min",), ("over_5_min", "continuation")]
    assert sa.issues[0].lost_pcs == pytest.approx(10 * 60 / 80)
    assert sa.hourly[2].downtime_min == pytest.approx(10)


def test_soft_deleted_issue_is_ignored(db: Session) -> None:
    make_shift(db, {1: (30, 0), 2: (40, 0)})
    e = add_issue(db, 2, "ST-038", 10, None)
    soft_delete_issue(db, e.issue_id, NOW)
    sa = build_shift(db, SHIFT_ID, catalog=CATALOG, now=NOW)
    assert sa.technical_losses.total_min == 0
    assert sa.issues == ()


def test_unspecified_rejects_in_quality_and_pareto(db: Session) -> None:
    make_shift(db, {1: (30, 2), 2: (40, 3)})
    replace_hour_quality(db, "L01-20261209-01", [], source="manual", now=NOW)  # bez rozpisu
    replace_hour_quality(db, "L01-20261209-02", [QualityLine("Q-030", 3)], source="manual", now=NOW)
    sa = build_shift(db, SHIFT_ID, catalog=CATALOG, now=NOW)
    assert [(d.code, d.qty) for d in sa.quality.by_defect] == [("Q-030", 3), (None, 2)]
    pareto = {b.bucket: b for b in sa.loss_pareto}
    assert pareto["unspecified_defect"].pcs == 2 and pareto["unspecified_defect"].kind == "quality"
    total = sa.waterfall_pcs.target - sa.waterfall_pcs.good
    assert math.isclose(sum(b.pcs for b in sa.loss_pareto), total, abs_tol=1e-9)


def test_untimed_issue_has_no_start_time(db: Session) -> None:
    make_shift(db, {2: (40, 0)})
    add_issue(db, 2, "ST-001", 4, None)
    sa = build_shift(db, SHIFT_ID, catalog=CATALOG, now=NOW)
    assert sa.issues[0].start_time is None
    assert sa.issues[0].category == "Material shortage"
    assert sa.issues[0].flags == ()  # 4 min ≤ 5


def test_empty_shift_has_no_kpis(db: Session) -> None:
    make_shift(db, {}, status="open")
    sa = build_shift(db, SHIFT_ID, catalog=CATALOG, now=NOW)
    assert sa.shift.hours_submitted == 0
    assert sa.kpi.oee is None and sa.kpi.oee_status is None
    assert sa.loss_pareto == ()


def test_negative_speed_loss_is_reported_as_data_quality(db: Session) -> None:
    make_shift(db, {2: (47, 0)})  # hodina 2: target 45 → S = −2
    sa = build_shift(db, SHIFT_ID, catalog=CATALOG, now=NOW)
    assert [(d.rule, d.level, d.subject) for d in sa.data_quality] == [("V3", "warning", "L01-20261209-02")]

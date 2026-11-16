"""P0-10 (golden): ShiftAnalytics pre zmeny 25.11. a 20.11.2026 (TASK §12.3, §10.2)."""

from __future__ import annotations

import math
from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from oee.catalog.loader import Catalog
from oee.contracts.shift_analytics import ShiftAnalytics
from oee.services.analytics import build_shift

pytestmark = pytest.mark.golden

NOW = datetime(2026, 12, 1, 9, 0)
PP = 1e-4  # ±0,01 p. b. ako podiel


@pytest.fixture(scope="module")
def s25(golden_db: Session, catalog: Catalog) -> ShiftAnalytics:
    return build_shift(golden_db, "L01-20261125-M", catalog=catalog, now=NOW)


def test_shift_header(s25: ShiftAnalytics) -> None:
    h = s25.shift
    assert (h.shift_id, str(h.date), h.weekday, h.line, h.product) == (
        "L01-20261125-M",
        "2026-11-25",
        "Wed",
        "L01",
        "P01",
    )
    assert (h.status, h.provisional, h.hours_submitted, h.hours_total) == ("completed", False, 8, 8)
    assert (s25.model.calendar_min, s25.model.planned_min, s25.model.ideal_cycle_s, s25.model.target_oee) == (
        480,
        440,
        60,
        0.85,
    )


def test_kpi(s25: ShiftAnalytics) -> None:
    # TASK §12.3: A 89.09 % · P 89.29 % · Q 98.29 % · OEE 78.18 % (−6.82 p. b.)
    k = s25.kpi
    assert k.availability == pytest.approx(0.8909, abs=PP)
    assert k.performance == pytest.approx(0.8929, abs=PP)
    assert k.quality == pytest.approx(0.9829, abs=PP)
    assert k.oee == pytest.approx(0.7818, abs=PP)
    assert k.oee_gap_pp == pytest.approx(-6.82, abs=0.01)
    assert k.oee_status == "below_goal"


def test_target_vs_actual_and_waterfall(s25: ShiftAnalytics) -> None:
    t = s25.target_vs_actual
    # TASK §12.3: Target 440 → Produced 350 (79.5 %) → Good 344; −96 = 48 + 42 + 6; cieľ OEE 374
    assert (t.target_pcs, t.produced_pcs, t.rejects_pcs, t.good_pcs) == (440, 350, 6, 344)
    assert t.production_vs_target == pytest.approx(0.795, abs=1e-3)
    assert t.good_vs_target == pytest.approx(0.782, abs=1e-3)
    assert t.deviation_from_target_pcs == pytest.approx(-96)
    assert t.oee_goal_pcs == pytest.approx(374)
    w = s25.waterfall_pcs
    assert (w.target, w.technical_losses, w.speed_loss, w.quality_loss, w.good) == pytest.approx(
        (440, 48, 42, 6, 344)
    )
    assert math.isclose(w.target - w.technical_losses - w.speed_loss - w.quality_loss, w.good, abs_tol=1e-9)


def test_technical_losses(s25: ShiftAnalytics) -> None:
    tl = s25.technical_losses
    # TASK §12.3: 48 min, 3 udalosti, 10.9 % targetu; Camera malfunction 25 (1), Leak test issue 23 (2)
    assert (tl.total_min, tl.events) == (pytest.approx(48), 3)
    assert tl.share_of_target == pytest.approx(0.109, abs=1e-3)
    assert [(c.category, c.min, c.events) for c in tl.by_category] == [
        ("Camera malfunction", pytest.approx(25), 1),
        ("Leak test issue", pytest.approx(23), 2),
    ]


def test_quality(s25: ShiftAnalytics) -> None:
    q = s25.quality
    # TASK §12.3: reject rate 1.71 %; Q-030 × 3, Q-020 × 2, Q-031 × 1; po hodinách 0 1 1 0 1 2 1 0
    assert q.rejects == 6
    assert q.reject_rate == pytest.approx(0.0171, abs=1e-4)
    assert [(d.code, d.qty) for d in q.by_defect] == [("Q-030", 3), ("Q-020", 2), ("Q-031", 1)]
    assert list(q.by_hour) == [0, 1, 1, 0, 1, 2, 1, 0]


HOURLY = [  # TASK §12.3: hodina, planned, target, produced, rejects, downtime, OEE
    (1, 50, 50, 42, 0, 0, 0.840),
    (2, 60, 60, 44, 1, 13, 0.717),
    (3, 60, 60, 54, 1, 0, 0.883),
    (4, 60, 60, 31, 0, 25, 0.517),
    (5, 30, 30, 25, 1, 0, 0.800),
    (6, 60, 60, 46, 2, 10, 0.733),
    (7, 60, 60, 54, 1, 0, 0.883),
    (8, 60, 60, 54, 0, 0, 0.900),
]


def test_hourly(s25: ShiftAnalytics) -> None:
    assert len(s25.hourly) == 8
    for row, (no, planned, target, produced, rejects, down, oee) in zip(s25.hourly, HOURLY, strict=True):
        assert (row.hour_no, row.planned_min, row.target_pcs, row.produced, row.rejects) == (
            no,
            planned,
            target,
            produced,
            rejects,
        )
        assert row.downtime_min == pytest.approx(down)
        assert row.oee == pytest.approx(oee, abs=5e-4)
    assert s25.hourly[0].slot == "06:00-07:00"
    assert s25.hourly[1].availability == pytest.approx(0.783, abs=5e-4)
    assert s25.hourly[3].performance == pytest.approx(0.886, abs=5e-4)
    # TASK §12.3: pod cieľom OEE 1, 2, 4, 5, 6; prestoj ≥ 5 min 2, 4, 6
    assert [r.hour_no for r in s25.hourly if "below_goal" in r.flags] == [1, 2, 4, 5, 6]
    assert [r.hour_no for r in s25.hourly if "downtime_ge_5_min" in r.flags] == [2, 4, 6]


def test_issues(s25: ShiftAnalytics) -> None:
    # TASK §10.2 / §12.3: ST-046 07:08 13 min (hod. 2), ST-038 09:08 25 min (hod. 4),
    # ST-046 11:08 10 min (hod. 6)
    rows = [(i.hour_no, str(i.start_time)[:5], i.issue_type, i.duration_min, i.lost_pcs) for i in s25.issues]
    assert rows == [
        (2, "07:08", "ST-046", 13, 13),
        (4, "09:08", "ST-038", 25, 25),
        (6, "11:08", "ST-046", 10, 10),
    ]
    first = s25.issues[0]
    assert first.category == "Leak test issue"
    assert first.name == "Leak measurement unit interrupted test"
    assert first.share_of_target == pytest.approx(0.0295, abs=1e-4)
    assert "over_5_min" in first.flags


def test_loss_pareto(s25: ShiftAnalytics) -> None:
    # TASK §12.3: Unattributed 42 (43.8 %) · ST-038 25 (26.0 %) · ST-046 23 (24.0 %)
    # · Q-030 3 · Q-020 2 · Q-031 1 = 96
    buckets = [(b.bucket, b.kind, b.pcs) for b in s25.loss_pareto]
    assert buckets == [
        ("unattributed_speed_loss", None, pytest.approx(42)),
        ("ST-038", "downtime", pytest.approx(25)),
        ("ST-046", "downtime", pytest.approx(23)),
        ("Q-030", "quality", 3),
        ("Q-020", "quality", 2),
        ("Q-031", "quality", 1),
    ]
    assert s25.loss_pareto[0].share_of_losses == pytest.approx(0.4375, abs=1e-4)
    assert s25.loss_pareto[1].share_of_losses == pytest.approx(0.2604, abs=1e-4)
    assert sum(b.pcs for b in s25.loss_pareto) == pytest.approx(440 - 344)


def test_shift_20_11(golden_db: Session, catalog: Catalog) -> None:
    sa = build_shift(golden_db, "L01-20261120-M", catalog=catalog, now=NOW)
    # TASK §12.3 (koniec): Downtime 9 · Produced 408 (92.7 %) · Rejects 4 · Good 404 (−36) · OEE 91.82 %
    assert sa.technical_losses.total_min == pytest.approx(9)
    assert (
        sa.target_vs_actual.produced_pcs,
        sa.target_vs_actual.rejects_pcs,
        sa.target_vs_actual.good_pcs,
    ) == (
        408,
        4,
        404,
    )
    assert sa.target_vs_actual.production_vs_target == pytest.approx(0.927, abs=1e-3)
    assert sa.target_vs_actual.deviation_from_target_pcs == pytest.approx(-36)
    assert sa.kpi.availability == pytest.approx(0.9795, abs=PP)
    assert sa.kpi.performance == pytest.approx(0.9466, abs=PP)
    assert sa.kpi.quality == pytest.approx(0.9902, abs=PP)
    assert sa.kpi.oee == pytest.approx(0.9182, abs=PP)
    assert sa.kpi.oee_status == "goal_met"


def test_output_passes_contract_round_trip(s25: ShiftAnalytics) -> None:
    assert ShiftAnalytics.model_validate(s25.model_dump(mode="json")) == s25

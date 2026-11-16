"""P0-13 (golden): PeriodAnalytics za november 2026 (TASK §12.1, §12.2, §12.4, §10.3)."""

from __future__ import annotations

from datetime import datetime

import pytest

from oee.contracts.period_analytics import PeriodAnalytics

pytestmark = pytest.mark.golden

NOW = datetime(2026, 12, 1, 9, 0)
PP = 1e-4  # ±0,01 p. b. ako podiel


def test_period_header(month: PeriodAnalytics) -> None:
    p = month.period
    assert (p.type, str(p.from_), str(p.to), p.line) == ("month", "2026-11-01", "2026-11-30", "L01")
    assert (p.shifts_completed, p.shifts_excluded_incomplete) == (21, 0)


def test_month_totals(month: PeriodAnalytics) -> None:
    t = month.totals
    # TASK §12.1
    assert (t.planned_min, t.target_pcs, t.oee_goal_pcs) == pytest.approx((9240, 9240, 7854))
    assert (t.downtime_min, t.downtime_events) == (pytest.approx(410), 33)
    assert (t.produced, t.rejects, t.good) == (8251, 119, 8132)
    assert t.speed_loss_pcs == pytest.approx(579)
    assert t.production_vs_target == pytest.approx(0.893, abs=1e-3)
    assert t.deviation_from_target_pcs == pytest.approx(-1108)
    w = month.waterfall_pcs
    assert (w.target, w.technical_losses, w.speed_loss, w.quality_loss, w.good) == pytest.approx(
        (9240, 410, 579, 119, 8132)
    )


def test_month_kpi(month: PeriodAnalytics) -> None:
    k = month.kpi
    # TASK §12.1: A 95.56 · P 93.44 · Q 98.56 · OEE 88.01 % (+3.01 p. b.) · FPQ 96.67 %
    assert k.availability == pytest.approx(0.9556, abs=PP)
    assert k.performance == pytest.approx(0.9344, abs=PP)
    assert k.quality == pytest.approx(0.9856, abs=PP)
    assert k.oee == pytest.approx(0.8801, abs=PP)
    assert k.oee_gap_pp == pytest.approx(3.01, abs=0.01)
    assert k.oee_status == "goal_met"
    assert k.first_pass_quality == pytest.approx(0.9667, abs=PP)


def test_shift_series(month: PeriodAnalytics) -> None:
    # TASK §12.1: 17 / 21 zmien splnilo cieľ; 4 pod cieľom = stredy
    series = month.shift_series
    assert len(series) == 21
    assert sum(s.status == "goal_met" for s in series) == 17
    assert {s.date.weekday() for s in series if s.status == "below_goal"} == {2}
    assert series[0].shift_id == "L01-20261102-M"
    assert series[0].oee == pytest.approx(0.8727, abs=PP)  # TASK §10.3


WEEKS = [  # TASK §12.2: týždeň, od, do, zmeny, partial, A, P, Q, OEE
    (45, "2026-11-02", "2026-11-06", 5, False, 0.9491, 0.9387, 0.9842, 0.8768),
    (46, "2026-11-09", "2026-11-13", 5, False, 0.9582, 0.9307, 0.9867, 0.8800),
    (47, "2026-11-16", "2026-11-20", 5, False, 0.9668, 0.9342, 0.9849, 0.8895),
    (48, "2026-11-23", "2026-11-27", 5, False, 0.9455, 0.9327, 0.9876, 0.8709),
    (49, "2026-11-30", "2026-11-30", 1, True, 0.9705, 0.9415, 0.9801, 0.8955),
]


def test_weeks(month: PeriodAnalytics) -> None:
    assert len(month.weekly) == 5
    for row, (wk, start, end, shifts, partial, a, p, q, oee) in zip(month.weekly, WEEKS, strict=True):
        assert (row.iso_week, str(row.from_), str(row.to), row.shifts, row.partial) == (
            wk,
            start,
            end,
            shifts,
            partial,
        )
        assert (row.availability, row.performance, row.quality, row.oee) == pytest.approx(
            (a, p, q, oee), abs=PP
        )


def test_unattributed_speed_loss_by_hour_of_shift(month: PeriodAnalytics) -> None:
    u = month.unattributed_speed_loss
    # TASK §12.1, §12.4: 579 ks (52.3 % všetkých strát); po hodinách zmeny
    assert u.pcs == pytest.approx(579)
    assert u.share_of_all_losses == pytest.approx(0.523, abs=1e-3)
    assert [h.hour_no for h in u.by_hour_of_shift] == list(range(1, 9))
    assert [h.pcs for h in u.by_hour_of_shift] == pytest.approx([115, 69, 62, 56, 80, 62, 66, 69])
    perf = [h.performance for h in u.by_hour_of_shift]
    assert perf == pytest.approx([0.885, 0.944, 0.946, 0.950, 0.869, 0.950, 0.947, 0.944], abs=5e-4)


def test_issue_and_defect_stats(month: PeriodAnalytics) -> None:
    # TASK §12.4: technické straty podľa typu
    assert [(s.code, s.category, s.events, s.total_min, s.avg_min) for s in month.issue_stats] == [
        ("ST-038", "Camera malfunction", 4, pytest.approx(100), pytest.approx(25.0)),
        ("ST-016", "Camera malfunction", 7, pytest.approx(70), pytest.approx(10.0)),
        ("ST-046", "Leak test issue", 7, pytest.approx(70), pytest.approx(10.0)),
        ("ST-001", "Material shortage", 7, pytest.approx(60), pytest.approx(8.57, abs=0.01)),
        ("ST-047", "Leak test issue", 4, pytest.approx(60), pytest.approx(15.0)),
        ("ST-017", "Tool issue", 4, pytest.approx(50), pytest.approx(12.5)),
    ]
    # TASK §12.4: zmätky podľa typu (kusy / záznamy)
    assert [(d.code, d.qty, d.records) for d in month.defect_stats] == [
        ("Q-031", 38, 35),
        ("Q-020", 28, 26),
        ("Q-026", 28, 26),
        ("Q-030", 25, 25),
    ]


def test_output_passes_contract_round_trip(month: PeriodAnalytics) -> None:
    assert PeriodAnalytics.model_validate(month.model_dump(mode="json")) == month

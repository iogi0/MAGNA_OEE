"""P0-13 (golden): rebríček problémov za november 2026 (TASK §12.5)."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from oee.contracts.period_analytics import PeriodAnalytics

pytestmark = pytest.mark.golden

NOW = datetime(2026, 12, 1, 9, 0)

EXPECTED = [  # TASK §12.5: rank, kód, druh, kusy, podiel zaznam., podiel všetkých, KPI, p. b., trend, trieda
    (1, "ST-038", "downtime", 100, 0.189, 0.090, "availability", 1.08, "stable", "A"),
    (2, "ST-016", "downtime", 70, 0.132, 0.063, "availability", 0.76, "up", "A"),
    (3, "ST-046", "downtime", 70, 0.132, 0.063, "availability", 0.76, "stable", "A"),
    (4, "ST-001", "downtime", 60, 0.113, 0.054, "availability", 0.65, "down", "A"),
    (5, "ST-047", "downtime", 60, 0.113, 0.054, "availability", 0.65, "stable", "A"),
    (6, "ST-017", "downtime", 50, 0.095, 0.045, "availability", 0.54, "down", "A"),
    (7, "Q-031", "quality", 38, 0.072, 0.034, "quality", 0.41, "up", "A"),
    (8, "Q-020", "quality", 28, 0.053, 0.025, "quality", 0.30, "down", "B"),
    (9, "Q-026", "quality", 28, 0.053, 0.025, "quality", 0.30, "down", "B"),
    (10, "Q-030", "quality", 25, 0.047, 0.023, "quality", 0.27, "up", "C"),
]


def test_ranking_order_classes_and_trends(month: PeriodAnalytics) -> None:
    rows = month.problem_ranking
    assert len(rows) == 10
    for row, (rank, code, kind, lost, rec, all_, kpi, pp, trend, cls) in zip(rows, EXPECTED, strict=True):
        assert (row.rank, row.code, row.kind, row.class_, row.trend) == (rank, code, kind, cls, trend), code
        assert row.lost_pcs == pytest.approx(lost)
        assert row.share_of_recorded == pytest.approx(rec, abs=5e-4)
        assert row.share_of_all_losses == pytest.approx(all_, abs=5e-4)
        assert (row.kpi_impact.kpi, row.kpi_impact.pp) == (kpi, pytest.approx(pp, abs=5e-3))


def test_trend_details(month: PeriodAnalytics) -> None:
    rows = {r.code: r for r in month.problem_ranking}
    # TASK §12.5: W47–48 vs W45–46 (týždeň 49 je neúplný)
    assert rows["ST-046"].trend_change == pytest.approx((37 - 33) / 33)
    assert rows["ST-001"].trend_change == pytest.approx((25 - 35) / 35)
    assert rows["ST-017"].trend_change == pytest.approx(-1.0)
    assert rows["Q-031"].trend_change == pytest.approx((20 - 15) / 15)
    assert rows["ST-038"].trend_change == pytest.approx(0.0)


def test_tie_break_details(month: PeriodAnalytics) -> None:
    rows = {r.code: r for r in month.problem_ranking}
    # TASK §12.5: ST-016 pred ST-046 (posledný výskyt 30.11 > 27.11); ST-001 pred ST-047 (frekvencia 7 > 4)
    assert (rows["ST-016"].last_occurrence, rows["ST-046"].last_occurrence) == (
        date(2026, 11, 30),
        date(2026, 11, 27),
    )
    assert (rows["ST-001"].events, rows["ST-047"].events) == (7, 4)
    assert rows["ST-038"].category == "Camera malfunction"
    assert rows["ST-038"].name == "Camera light module interrupted operation"
    assert rows["ST-038"].recurring is False  # odznak určujú Patterns (P1)
    assert len(rows["ST-038"].evidence) == 4

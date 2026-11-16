"""P0-04: kaskáda strát C → D → S → R → G a 4 KPI (TASK §3.3–3.4, §12.7, PLANNING D12)."""

from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml

from oee.domain.kpi import Cascade, sum_cascades

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
SLIDES: list[dict[str, Any]] = yaml.safe_load((FIXTURES / "slides.yaml").read_text(encoding="utf-8"))


def pct1(x: float | None) -> float:
    """Percentá zaokrúhlené na 0,1 ako na slajdoch (ROUND_HALF_UP, nie bankárske)."""
    assert x is not None
    return float(Decimal(repr(x * 100)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def make(case: dict[str, Any]) -> Cascade:
    return Cascade.from_minutes(
        planned_min=case["planned_min"],
        downtime_min=case["downtime_min"],
        produced=case["produced"],
        rejects=case["rejects"],
        ideal_cycle_s=case["ideal_cycle_s"],
    )


# --- slajdy 11 a 12 -----------------------------------------------------------------------------


@pytest.mark.parametrize("case", SLIDES, ids=[c["name"] for c in SLIDES])
def test_slide_cases(case: dict[str, Any]) -> None:
    c = make(case)
    exp = case["expected"]
    assert c.target == pytest.approx(exp["target"])
    assert c.run_min == pytest.approx(exp["run_min"])
    assert c.good == exp["good"]
    assert pct1(c.availability) == exp["availability_pct"]
    assert pct1(c.performance) == exp["performance_pct"]
    assert pct1(c.quality) == exp["quality_pct"]
    assert pct1(c.oee) == exp["oee_pct"]
    gap = c.goal_gap_pp(case["target_oee"])
    assert gap is not None
    assert float(Decimal(repr(gap)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)) == exp["goal_gap_pp"]


def test_slide_11_cascade_in_pieces() -> None:
    c = make(SLIDES[0])
    assert c.technical_loss == pytest.approx(45)  # D
    assert c.possible_in_run == pytest.approx(395)
    assert c.speed_loss == pytest.approx(42)  # S = 395 − 353
    assert c.quality_loss == 4  # R
    assert c.deviation == pytest.approx(-91)  # G − C = −(D + S + R)


def test_oee_equals_a_times_p_times_q() -> None:
    c = make(SLIDES[0])
    assert c.availability is not None and c.performance is not None and c.quality is not None
    assert c.oee == pytest.approx(c.availability * c.performance * c.quality)


# --- iný takt -----------------------------------------------------------------------------------


def test_other_cycle_converts_minutes_to_pieces() -> None:
    # 50 ks/h → takt 72 s: 440 min = 366,67 ks; 30 min prestoja = 25 ks
    c = Cascade.from_minutes(planned_min=440, downtime_min=30, produced=300, rejects=5, ideal_cycle_s=72)
    assert c.target == pytest.approx(366.6667, abs=1e-4)
    assert c.technical_loss == pytest.approx(25)
    assert c.availability == pytest.approx(410 / 440)  # = Run / Plan
    assert c.performance == pytest.approx(300 * 72 / (410 * 60))  # = ideal time / run time
    assert c.oee == pytest.approx(295 / (440 * 60 / 72))


# --- identita C − D − S − R = G -----------------------------------------------------------------

IDENTITY_CASES = [
    (440, 45, 353, 4, 60),
    (440, 0, 440, 0, 60),
    (440, 30, 300, 5, 72),  # target 366,67
    (325, 12.5, 200, 3, 80),
    (60, 60, 0, 0, 60),  # Run = 0
    (50, 10, 0, 0, 60),  # Produced = 0
    (60, 0, 61, 0, 60),  # záporná S (Produced > možné)
    (480, 7.3333, 411, 17, 63.7),
]


@pytest.mark.parametrize(("planned", "down", "produced", "rejects", "cycle"), IDENTITY_CASES)
def test_identity_holds(planned: float, down: float, produced: int, rejects: int, cycle: float) -> None:
    c = Cascade.from_minutes(
        planned_min=planned, downtime_min=down, produced=produced, rejects=rejects, ideal_cycle_s=cycle
    )
    assert math.isclose(
        c.target - c.technical_loss - c.speed_loss - c.quality_loss, c.good, rel_tol=0, abs_tol=1e-9
    )
    assert math.isclose(c.deviation, -(c.technical_loss + c.speed_loss + c.quality_loss), abs_tol=1e-9)


# --- agregácia cez súčty ------------------------------------------------------------------------

HOURS_SLIDE_11 = [  # slajd 11: výstup po hodinách 48, 57, 40, 20, 25, 52, 55, 56 (Σ 353)
    (50, 0, 48, 0),
    (60, 0, 57, 1),
    (60, 15, 40, 0),  # leak test
    (60, 30, 20, 1),  # kamera
    (30, 0, 25, 0),  # prestávka
    (60, 0, 52, 1),
    (60, 0, 55, 0),
    (60, 0, 56, 1),
]


def test_shift_is_sum_of_hours() -> None:
    hours = [
        Cascade.from_minutes(planned_min=p, downtime_min=d, produced=q, rejects=r, ideal_cycle_s=60)
        for p, d, q, r in HOURS_SLIDE_11
    ]
    shift = sum_cascades(hours)
    assert shift == make(SLIDES[0])
    assert pct1(shift.oee) == 79.3
    mean_of_hour_oee = sum(h.oee or 0 for h in hours) / len(hours)
    assert not math.isclose(shift.oee or 0, mean_of_hour_oee, abs_tol=1e-3)  # nikdy priemer percent


def test_period_with_different_cycles_uses_sums() -> None:
    a = Cascade.from_minutes(planned_min=440, downtime_min=40, produced=380, rejects=4, ideal_cycle_s=60)
    b = Cascade.from_minutes(planned_min=325, downtime_min=20, produced=210, rejects=6, ideal_cycle_s=80)
    period = a + b
    assert period.target == pytest.approx(440 + 243.75)
    assert period.produced == 590
    assert period.good == 580
    assert period.oee == pytest.approx(580 / 683.75)
    assert period.planned_min == 765
    assert period.downtime_min == 60
    # A × P × Q = OEE platí presne aj pri rôznom takte (D12)
    assert period.availability is not None and period.performance is not None and period.quality is not None
    assert period.oee == pytest.approx(period.availability * period.performance * period.quality)
    assert math.isclose(
        period.target - period.technical_loss - period.speed_loss - period.quality_loss,
        period.good,
        abs_tol=1e-9,
    )


def test_sum_of_nothing_is_empty_cascade() -> None:
    empty = sum_cascades([])
    assert empty.target == 0
    assert empty.oee is None
    assert empty.availability is None


# --- hraničné prípady ---------------------------------------------------------------------------


def test_run_zero_has_no_performance_and_zero_oee() -> None:
    c = Cascade.from_minutes(planned_min=60, downtime_min=60, produced=0, rejects=0, ideal_cycle_s=60)
    assert c.availability == 0
    assert c.performance is None
    assert c.quality is None
    assert c.oee == 0
    assert c.speed_loss == 0


def test_produced_zero_has_no_quality_and_zero_oee() -> None:
    c = Cascade.from_minutes(planned_min=50, downtime_min=10, produced=0, rejects=0, ideal_cycle_s=60)
    assert c.quality is None
    assert c.performance == 0
    assert c.oee == 0
    assert c.speed_loss == pytest.approx(40)


def test_zero_planned_time_has_no_kpis() -> None:
    c = Cascade.from_minutes(planned_min=0, downtime_min=0, produced=0, rejects=0, ideal_cycle_s=60)
    assert (c.availability, c.performance, c.quality, c.oee) == (None, None, None, None)
    assert c.goal_gap_pp(0.85) is None


def test_negative_speed_loss_is_reported_not_hidden() -> None:
    c = Cascade.from_minutes(planned_min=60, downtime_min=0, produced=61, rejects=0, ideal_cycle_s=60)
    assert c.speed_loss == pytest.approx(-1)
    assert c.performance == pytest.approx(61 / 60)


@pytest.mark.parametrize("cycle", [0, -60, float("nan")])
def test_invalid_cycle_rejected(cycle: float) -> None:
    with pytest.raises(ValueError, match="cycle"):
        Cascade.from_minutes(planned_min=60, downtime_min=0, produced=0, rejects=0, ideal_cycle_s=cycle)


def test_downtime_over_planned_keeps_identity() -> None:
    # count_downtime to nedovolí (strop); keby áno, kaskáda neskryje rozpor, iba ho ukáže
    c = Cascade.from_minutes(planned_min=60, downtime_min=70, produced=0, rejects=0, ideal_cycle_s=60)
    assert c.availability is not None and c.availability < 0
    assert c.performance is None
    assert math.isclose(c.target - c.technical_loss - c.speed_loss - c.quality_loss, c.good, abs_tol=1e-9)


def test_rejects_without_production_give_negative_good() -> None:
    c = Cascade.from_minutes(planned_min=60, downtime_min=0, produced=0, rejects=2, ideal_cycle_s=60)
    assert c.good == -2  # rozpor zachytí validácia V10
    assert c.quality is None
    assert c.oee == pytest.approx(-2 / 60)

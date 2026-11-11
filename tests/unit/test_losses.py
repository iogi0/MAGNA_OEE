"""Straty v kusoch: Pareto, príznaky hodín a udalostí, stav cieľa OEE (TASK §6.5, §6.6, §7C, §7E)."""

from __future__ import annotations

import math

import pytest

from oee.domain.kpi import Cascade
from oee.domain.losses import (
    UNATTRIBUTED,
    UNSPECIFIED,
    event_flags,
    goal_status,
    hour_flags,
    loss_pareto,
)


def cascade(planned: float, down: float, produced: int, rejects: int, cycle: float = 60) -> Cascade:
    return Cascade.from_minutes(
        planned_min=planned, downtime_min=down, produced=produced, rejects=rejects, ideal_cycle_s=cycle
    )


# --- stav cieľa OEE -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("oee", "goal", "expected"),
    [(0.7818, 0.85, "below_goal"), (0.85, 0.85, "goal_met"), (0.9, 0.8, "goal_met"), (None, 0.85, None)],
)
def test_goal_status(oee: float | None, goal: float, expected: str | None) -> None:
    assert goal_status(oee, goal) == expected


# --- príznaky hodiny (§7C) a udalosti (§6.6) ----------------------------------------------------


def test_hour_flags_below_goal_and_downtime_threshold() -> None:
    assert hour_flags(cascade(60, 13, 44, 1), goal=0.85) == ("below_goal", "downtime_ge_5_min")
    assert hour_flags(cascade(60, 5, 54, 0), goal=0.8) == ("downtime_ge_5_min",)  # ≥ 5 min
    assert hour_flags(cascade(60, 4.9, 54, 0), goal=0.8) == ()
    assert hour_flags(cascade(60, 0, 54, 0), goal=0.9) == ()  # OEE 0,9 = cieľ


def test_event_flags_use_whole_stop_duration() -> None:
    assert event_flags(stop_duration_min=13, is_continuation=False) == ("over_5_min",)
    assert event_flags(stop_duration_min=5, is_continuation=False) == ()  # > 5 min
    assert event_flags(stop_duration_min=8, is_continuation=True) == (
        "over_5_min",
        "continuation",
    )  # 4 + 4 min


# --- Pareto (§7E): Σ = C − G -------------------------------------------------------------------


def test_pareto_shift_25_11_shape() -> None:
    total = cascade(440, 48, 350, 6)  # TASK §12.3
    buckets = loss_pareto(
        total,
        stop_pcs={"ST-038": 25, "ST-046": 23},
        defect_qty={"Q-030": 3, "Q-020": 2, "Q-031": 1},
        stop_category={"ST-038": "Camera malfunction", "ST-046": "Leak test issue"},
        defect_category={
            "Q-030": "Camera malfunction",
            "Q-020": "Pressing issue",
            "Q-031": "Leak test issue",
        },
    )
    assert [(b.bucket, b.kind, b.pcs) for b in buckets] == [
        (UNATTRIBUTED, None, pytest.approx(42)),
        ("ST-038", "downtime", 25),
        ("ST-046", "downtime", 23),
        ("Q-030", "quality", 3),
        ("Q-020", "quality", 2),
        ("Q-031", "quality", 1),
    ]
    assert buckets[0].share_of_losses == pytest.approx(0.4375)
    assert buckets[1].category == "Camera malfunction"
    assert buckets[0].category is None
    assert math.isclose(sum(b.pcs for b in buckets), total.target - total.good, abs_tol=1e-9)


def test_pareto_unspecified_defect_and_zero_buckets_dropped() -> None:
    total = cascade(60, 0, 55, 2)
    buckets = loss_pareto(total, stop_pcs={"ST-038": 0.0}, defect_qty={None: 2})
    assert [(b.bucket, b.kind) for b in buckets] == [(UNATTRIBUTED, None), (UNSPECIFIED, "quality")]


def test_pareto_negative_speed_loss_kept_so_sum_holds() -> None:
    total = cascade(60, 0, 61, 0)  # S = −1, C − G = −1
    buckets = loss_pareto(total, stop_pcs={}, defect_qty={})
    assert [(b.bucket, b.pcs) for b in buckets] == [(UNATTRIBUTED, pytest.approx(-1))]
    assert buckets[0].share_of_losses is None  # nekladné straty → podiel nedefinovaný


def test_pareto_tie_break_by_code() -> None:
    total = cascade(60, 10, 50, 0)
    buckets = loss_pareto(total, stop_pcs={"ST-046": 5, "ST-016": 5}, defect_qty={})
    assert [b.bucket for b in buckets] == ["ST-016", "ST-046"]


def test_pareto_of_empty_shift_is_empty() -> None:
    from oee.domain.kpi import EMPTY_CASCADE

    assert loss_pareto(EMPTY_CASCADE, stop_pcs={}, defect_qty={}) == []

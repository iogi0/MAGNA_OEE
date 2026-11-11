"""Pravidlá obdobia (TASK §3.3, §8.2–8.4, PLANNING D8): cieľ OEE obdobia, FPQ, úplný týždeň."""

from __future__ import annotations

from datetime import date

import pytest

from oee.domain.period import first_pass_quality, is_week_complete, period_goal

MON, TUE, WED = date(2026, 12, 7), date(2026, 12, 8), date(2026, 12, 9)


def test_period_goal_is_target_weighted() -> None:
    # D8: Σ (target × cieľ) / Σ target
    assert period_goal([(440, 0.85), (243.75, 0.8)]) == pytest.approx((440 * 0.85 + 243.75 * 0.8) / 683.75)
    assert period_goal([(440, 0.85)] * 21) == pytest.approx(0.85)


def test_period_goal_of_nothing_is_none() -> None:
    assert period_goal([]) is None
    assert period_goal([(0, 0.85)]) is None


def test_first_pass_quality() -> None:
    # TASK §3.3, §12.1: (Good − retesty) / Produced = (8132 − 156) / 8251
    assert first_pass_quality(good=8132, produced=8251, retests=[156]) == pytest.approx(0.9667, abs=1e-4)


@pytest.mark.parametrize("retests", [[], [3, None], [None]])
def test_first_pass_quality_needs_retests_everywhere(retests: list[int | None]) -> None:
    assert first_pass_quality(good=100, produced=110, retests=retests) is None


def test_first_pass_quality_without_production() -> None:
    assert first_pass_quality(good=0, produced=0, retests=[0]) is None


def test_week_complete_when_every_working_day_has_completed_shift() -> None:
    assert is_week_complete(done={MON, TUE}, working_days={0, 1}, start=MON, end=TUE)


def test_week_partial_when_working_day_has_no_shift() -> None:
    assert not is_week_complete(done={MON, WED}, working_days={0, 1, 2}, start=MON, end=WED)


def test_week_partial_when_working_day_is_outside_period() -> None:
    # TASK §12.2: týždeň 49 (30.11) — ostatné pracovné dni sú mimo obdobia
    assert not is_week_complete(
        done={date(2026, 11, 30)},
        working_days={0, 1, 2, 3, 4},
        start=date(2026, 11, 1),
        end=date(2026, 11, 30),
    )


def test_week_with_no_shifts_is_not_complete() -> None:
    with pytest.raises(ValueError, match="shift"):
        is_week_complete(done=set(), working_days={0}, start=MON, end=MON)

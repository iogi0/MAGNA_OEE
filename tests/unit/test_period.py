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


# --- Top-10 podľa frekvencie (D15) a straty podľa kategórie (TASK §8.3) -----------------------------

STARTING = (
    "ST-038",
    "ST-016",
    "ST-046",
    "ST-047",
    "ST-001",
    "ST-017",
    "ST-020",
    "ST-026",
    "ST-032",
    "ST-040",
)


def test_top_by_frequency_orders_by_events_then_measure_then_code_and_fills_with_starting_list() -> None:
    from oee.domain.period import TopItem, top_by_frequency

    counts = {  # november 2026 (TASK §12.4): výskyty, minúty
        "ST-038": (4, 100.0),
        "ST-016": (7, 70.0),
        "ST-046": (7, 70.0),
        "ST-001": (7, 60.0),
        "ST-047": (4, 60.0),
        "ST-017": (4, 50.0),
    }
    top = top_by_frequency(counts, STARTING, size=10)
    assert [t.code for t in top] == [
        "ST-016", "ST-046", "ST-001", "ST-038", "ST-047", "ST-017",  # podľa dát
        "ST-020", "ST-026", "ST-032", "ST-040",  # doplnené zo štartovacieho zoznamu s nulami
    ]  # fmt: skip
    assert top[0] == TopItem("ST-016", 7, 70.0)
    assert top[-1] == TopItem("ST-040", 0, 0.0)


def test_top_by_frequency_without_data_is_starting_list_with_zeros() -> None:
    from oee.domain.period import top_by_frequency

    top = top_by_frequency({}, STARTING, size=10)
    assert [t.code for t in top] == list(STARTING)
    assert all((t.events, t.measure) == (0, 0.0) for t in top)


def test_top_by_frequency_new_frequent_code_pushes_out_starting_codes() -> None:
    from oee.domain.period import top_by_frequency

    counts = {f"ST-{n:03d}": (70 - n, 1.0) for n in range(50, 61)}  # 11 nových kódov, výskyty 20 … 10
    top = top_by_frequency(counts, STARTING, size=10)
    assert [t.code for t in top] == [f"ST-{n:03d}" for n in range(50, 60)]  # 11. kód a štart. zoznam vypadnú


def test_losses_by_category_sums_without_double_counting() -> None:
    from oee.domain.period import CategoryTotal, losses_by_category

    rows = [  # (kategória, udalosti, minúty, kusy)
        ("Camera malfunction", 4, 100.0, 100.0),
        ("Camera malfunction", 7, 70.0, 70.0),
        ("Leak test issue", 7, 70.0, 70.0),
        ("Leak test issue", 4, 60.0, 60.0),
        ("Material shortage", 7, 60.0, 60.0),
    ]
    totals = losses_by_category(rows)
    assert totals == [
        CategoryTotal("Camera malfunction", 11, 170.0, 170.0),
        CategoryTotal("Leak test issue", 11, 130.0, 130.0),
        CategoryTotal("Material shortage", 7, 60.0, 60.0),
    ]
    assert sum(t.minutes for t in totals) == sum(r[2] for r in rows)

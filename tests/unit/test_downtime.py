"""P0-03: evidencia prestojov (TASK §3.4 pravidlá 2–4).

- prekrývajúce sa udalosti = jedna zastávka (počíta sa zjednotenie intervalov, nie súčet);
- pokračovanie cez hranicu hodiny: minúty v každej hodine raz, vo frekvencii jedna udalosť;
- minúty počas AM a prestávky nie sú plánovaný čas a nepočítajú sa;
- bez času začiatku: Σ trvaní v hodine ≤ plánované minúty hodiny.
"""

from __future__ import annotations

from datetime import date, datetime, time

import pytest

from oee.domain.downtime import DowntimeEvent, count_downtime
from oee.domain.shift_model import Allowance, ShiftModelConfig, ShiftPlan, build_shift_plan

DAY = date(2026, 11, 25)


def plan_example() -> ShiftPlan:
    """06:00–14:00, AM 10 min v 1. hod. (06:00–06:10), prestávka 30 min v 5. hod. (10:00–10:30)."""
    cfg = ShiftModelConfig(
        rate_per_hour=60,
        start=time(6, 0),
        duration_min=480,
        break_=Allowance(minutes=30, hour_no=5),
        am=Allowance(minutes=10, hour_no=1),
        target_oee=0.85,
        working_days=frozenset({0, 1, 2, 3, 4}),
    )
    return build_shift_plan(cfg, DAY)


def at(hh: int, mm: int, day: int = 25) -> datetime:
    return datetime(2026, 11, day, hh, mm)


def ev(
    event_id: str,
    hour_no: int,
    duration_min: float,
    start: datetime | None = None,
    continues: str | None = None,
) -> DowntimeEvent:
    return DowntimeEvent(
        event_id=event_id,
        hour_no=hour_no,
        duration_min=duration_min,
        start=start,
        continues_event_id=continues,
    )


def counted(summary: object) -> dict[str, float]:
    return {s.event_id: s.counted_min for s in summary.segments}  # type: ignore[attr-defined]


# --- základ -------------------------------------------------------------------------------------


def test_no_events_gives_zero_for_every_hour() -> None:
    summary = count_downtime(plan_example(), [])
    assert [h.downtime_min for h in summary.hours] == [0] * 8
    assert [h.hour_no for h in summary.hours] == list(range(1, 9))
    assert summary.total_min == 0
    assert summary.event_count == 0
    assert summary.segments == ()


def test_single_timed_event_counts_its_duration() -> None:
    summary = count_downtime(plan_example(), [ev("a", 4, 25, at(9, 8))])
    assert counted(summary) == {"a": pytest.approx(25)}
    assert summary.hours[3].downtime_min == pytest.approx(25)
    assert summary.total_min == pytest.approx(25)
    assert summary.event_count == 1


def test_fractional_minutes_are_kept() -> None:
    summary = count_downtime(plan_example(), [ev("a", 2, 12.5, at(7, 10))])
    assert summary.total_min == pytest.approx(12.5)


# --- pravidlo 2: prekryv = jedna zastávka -------------------------------------------------------


def test_overlapping_events_count_union_once() -> None:
    events = [ev("a", 2, 20, at(7, 10)), ev("b", 2, 20, at(7, 20))]  # 07:10–07:30 a 07:20–07:40
    summary = count_downtime(plan_example(), events)
    assert summary.hours[1].downtime_min == pytest.approx(30)  # zjednotenie 07:10–07:40
    assert counted(summary) == {"a": pytest.approx(20), "b": pytest.approx(10)}  # prekryv patrí skoršej


def test_event_inside_another_adds_nothing() -> None:
    events = [ev("outer", 2, 30, at(7, 0)), ev("inner", 2, 10, at(7, 5))]
    summary = count_downtime(plan_example(), events)
    assert summary.total_min == pytest.approx(30)
    assert counted(summary)["inner"] == pytest.approx(0)


def test_overlap_attribution_does_not_depend_on_input_order() -> None:
    events = [ev("b", 2, 20, at(7, 20)), ev("a", 2, 20, at(7, 10))]
    assert counted(count_downtime(plan_example(), events)) == {"a": pytest.approx(20), "b": pytest.approx(10)}


def test_touching_events_are_not_an_overlap() -> None:
    events = [ev("a", 2, 10, at(7, 0)), ev("b", 2, 10, at(7, 10))]
    assert count_downtime(plan_example(), events).total_min == pytest.approx(20)


def test_untimed_events_capped_by_planned_minutes() -> None:
    events = [ev("a", 2, 40), ev("b", 2, 30)]  # hodina 2: 60 plánovaných minút
    summary = count_downtime(plan_example(), events)
    assert summary.hours[1].downtime_min == pytest.approx(60)
    assert counted(summary) == {"a": pytest.approx(40), "b": pytest.approx(20)}


def test_untimed_event_capped_in_hour_with_allowance() -> None:
    summary = count_downtime(plan_example(), [ev("a", 1, 55)])  # hodina 1: 50 plánovaných minút
    assert summary.hours[0].downtime_min == pytest.approx(50)


def test_timed_and_untimed_share_planned_minutes() -> None:
    events = [ev("u", 2, 40), ev("t", 2, 30, at(7, 0))]
    summary = count_downtime(plan_example(), events)
    assert summary.hours[1].downtime_min == pytest.approx(60)
    assert counted(summary) == {"t": pytest.approx(30), "u": pytest.approx(30)}


# --- pravidlo 4: AM a prestávka -----------------------------------------------------------------


def test_minutes_in_break_are_not_counted() -> None:
    summary = count_downtime(plan_example(), [ev("a", 5, 20, at(10, 20))])  # prestávka 10:00–10:30
    assert summary.hours[4].downtime_min == pytest.approx(10)


def test_event_fully_in_break_counts_zero_but_is_an_event() -> None:
    summary = count_downtime(plan_example(), [ev("a", 5, 30, at(10, 0))])
    assert summary.total_min == pytest.approx(0)
    assert summary.event_count == 1


def test_minutes_in_am_are_not_counted() -> None:
    summary = count_downtime(plan_example(), [ev("a", 1, 10, at(6, 5))])  # AM 06:00–06:10
    assert summary.hours[0].downtime_min == pytest.approx(5)


def test_allowance_with_offset_in_other_config() -> None:
    cfg = ShiftModelConfig(
        rate_per_hour=45,
        start=time(14, 0),
        duration_min=360,
        break_=Allowance(minutes=20, hour_no=3, offset_min=10),  # 16:10–16:30
        am=Allowance(minutes=15, hour_no=1),
        target_oee=0.8,
        working_days=frozenset({0}),
    )
    plan = build_shift_plan(cfg, DAY)
    summary = count_downtime(plan, [ev("a", 3, 40, at(16, 0))])  # 16:00–16:40
    assert summary.hours[2].downtime_min == pytest.approx(20)
    assert len(summary.hours) == 6


def test_timed_event_is_clipped_to_its_slot() -> None:
    summary = count_downtime(plan_example(), [ev("a", 2, 30, at(7, 50))])  # 07:50–08:20, slot do 08:00
    assert summary.hours[1].downtime_min == pytest.approx(10)
    assert summary.hours[2].downtime_min == 0


# --- pravidlo 3: pokračovanie cez hranicu hodiny ------------------------------------------------


def test_continuation_counts_minutes_per_hour_but_one_event() -> None:
    events = [ev("a", 3, 15, at(8, 45)), ev("a2", 4, 10, at(9, 0), continues="a")]
    summary = count_downtime(plan_example(), events)
    assert summary.hours[2].downtime_min == pytest.approx(15)
    assert summary.hours[3].downtime_min == pytest.approx(10)
    assert summary.total_min == pytest.approx(25)
    assert summary.event_count == 1
    assert {s.root_id for s in summary.segments} == {"a"}


def test_chain_of_continuations_is_one_event() -> None:
    events = [
        ev("c", 5, 30, at(10, 30), continues="b"),
        ev("a", 3, 20, at(8, 40)),
        ev("b", 4, 60, at(9, 0), continues="a"),
    ]
    summary = count_downtime(plan_example(), events)
    assert summary.event_count == 1
    assert summary.total_min == pytest.approx(110)
    assert {s.event_id: s.root_id for s in summary.segments} == {"a": "a", "b": "a", "c": "a"}


def test_continuation_of_unknown_event_counts_as_own_event() -> None:
    summary = count_downtime(plan_example(), [ev("x", 4, 10, at(9, 0), continues="deleted")])
    assert summary.event_count == 1
    assert summary.segments[0].root_id == "x"


def test_continuation_cycle_does_not_hang() -> None:
    events = [ev("a", 3, 5, at(8, 0), continues="b"), ev("b", 4, 5, at(9, 0), continues="a")]
    summary = count_downtime(plan_example(), events)
    assert summary.total_min == pytest.approx(10)
    assert summary.event_count == 1


def test_untimed_continuation() -> None:
    events = [ev("a", 3, 15), ev("a2", 4, 10, continues="a"), ev("b", 6, 5)]
    summary = count_downtime(plan_example(), events)
    assert summary.event_count == 2
    assert summary.total_min == pytest.approx(30)


# --- ostatné ------------------------------------------------------------------------------------


def test_night_shift_event_after_midnight() -> None:
    cfg = ShiftModelConfig(
        rate_per_hour=60,
        start=time(22, 0),
        duration_min=480,
        break_=Allowance(minutes=30, hour_no=5),  # 02:00–02:30 nasledujúceho dňa
        am=Allowance(minutes=10, hour_no=1),
        target_oee=0.85,
        working_days=frozenset({0}),
    )
    plan = build_shift_plan(cfg, DAY)
    events = [ev("a", 3, 15, at(0, 30, day=26)), ev("b", 5, 40, at(2, 10, day=26))]
    summary = count_downtime(plan, events)
    assert summary.hours[2].downtime_min == pytest.approx(15)
    assert summary.hours[4].downtime_min == pytest.approx(20)  # 02:10–02:50, z toho 02:10–02:30 prestávka


def test_hour_totals_never_exceed_planned_minutes() -> None:
    events = [ev("a", 1, 60, at(6, 0)), ev("b", 1, 30)]
    summary = count_downtime(plan_example(), events)
    assert summary.hours[0].downtime_min == pytest.approx(50)
    assert summary.hours[0].planned_min == 50


def test_non_positive_duration_counts_zero() -> None:
    summary = count_downtime(plan_example(), [ev("a", 2, 0), ev("b", 2, -5, at(7, 0))])
    assert summary.total_min == 0


@pytest.mark.parametrize("hour_no", [0, 9])
def test_hour_outside_shift_is_rejected(hour_no: int) -> None:
    with pytest.raises(ValueError, match="hour"):
        count_downtime(plan_example(), [ev("a", hour_no, 5)])


def test_duplicate_event_ids_are_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        count_downtime(plan_example(), [ev("a", 2, 5), ev("a", 3, 5)])


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
@pytest.mark.parametrize("timed", [True, False])
def test_non_finite_duration_counts_zero(bad: float, timed: bool) -> None:
    start = at(7, 0) if timed else None
    summary = count_downtime(plan_example(), [ev("a", 2, bad, start), ev("b", 2, 10)])
    assert counted(summary) == {"a": 0, "b": pytest.approx(10)}


def test_overflow_into_next_hour_is_not_double_counted() -> None:
    events = [ev("a", 2, 30, at(7, 50)), ev("b", 3, 15, at(8, 0))]  # „a" by siahalo do 08:20
    summary = count_downtime(plan_example(), events)
    assert summary.hours[1].downtime_min == pytest.approx(10)
    assert summary.hours[2].downtime_min == pytest.approx(15)


def test_continuation_in_same_hour_as_root() -> None:
    events = [ev("a", 2, 10, at(7, 0)), ev("a2", 2, 10, at(7, 30), continues="a")]
    summary = count_downtime(plan_example(), events)
    assert summary.total_min == pytest.approx(20)
    assert summary.event_count == 1

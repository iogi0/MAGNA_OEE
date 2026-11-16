"""P0-02: model zmeny a target (TASK §3.1–3.2, PLANNING D8, D10).

Čísla 60 ks/h, 480 / 30 / 10 min, 85 % sú iba príklad z prezentácie — testy pokrývajú aj iné konfigurácie.
"""

from __future__ import annotations

import math
from dataclasses import replace
from datetime import date, datetime, time

import pytest

from oee.domain.shift_model import (
    Allowance,
    ShiftModelConfig,
    ShiftModelError,
    build_shift_plan,
    config_from_snapshot,
    config_to_snapshot,
    validate_shift_model,
)

MON_FRI = frozenset({0, 1, 2, 3, 4})
DAY = date(2026, 11, 25)


def example_config() -> ShiftModelConfig:
    """Príklad z prezentácie (TASK §3.1): 06:00, 480 min, prestávka 30 min v 5. hod., AM 10 min v 1. hod."""
    return ShiftModelConfig(
        rate_per_hour=60,
        start=time(6, 0),
        duration_min=480,
        break_=Allowance(minutes=30, hour_no=5),
        am=Allowance(minutes=10, hour_no=1),
        target_oee=0.85,
        working_days=MON_FRI,
    )


def six_hour_config() -> ShiftModelConfig:
    return ShiftModelConfig(
        rate_per_hour=45,
        start=time(14, 0),
        duration_min=360,
        break_=Allowance(minutes=20, hour_no=3, offset_min=10),
        am=Allowance(minutes=15, hour_no=1),
        target_oee=0.8,
        working_days=frozenset({0, 2, 4}),
    )


# --- príklad z prezentácie ---------------------------------------------------------------------


def test_example_planned_time_and_target() -> None:
    plan = build_shift_plan(example_config(), DAY)
    assert plan.planned_min == 440
    assert math.isclose(plan.target, 440)
    assert math.isclose(plan.ideal_cycle_s, 60)
    assert plan.target_oee == 0.85


def test_example_hourly_targets() -> None:
    plan = build_shift_plan(example_config(), DAY)
    assert [s.planned_min for s in plan.slots] == [50, 60, 60, 60, 30, 60, 60, 60]
    assert [s.target for s in plan.slots] == pytest.approx([50, 60, 60, 60, 30, 60, 60, 60])


def test_example_slot_times_and_allowances() -> None:
    plan = build_shift_plan(example_config(), DAY)
    assert [s.hour_no for s in plan.slots] == list(range(1, 9))
    assert plan.slots[0].start == datetime(2026, 11, 25, 6, 0)
    assert plan.slots[0].end == datetime(2026, 11, 25, 7, 0)
    assert plan.slots[-1].end == datetime(2026, 11, 25, 14, 0)
    assert (plan.slots[0].am_min, plan.slots[0].break_min) == (10, 0)
    assert (plan.slots[4].am_min, plan.slots[4].break_min) == (0, 30)
    assert plan.start == datetime(2026, 11, 25, 6, 0)
    assert plan.end == datetime(2026, 11, 25, 14, 0)
    assert plan.shift_date == DAY


def test_allowance_windows_follow_hour_and_offset() -> None:
    plan = build_shift_plan(six_hour_config(), DAY)
    assert plan.slots[0].allowance_windows == (
        (datetime(2026, 11, 25, 14, 0), datetime(2026, 11, 25, 14, 15)),
    )
    assert plan.slots[1].allowance_windows == ()
    assert plan.slots[2].allowance_windows == (
        (datetime(2026, 11, 25, 16, 10), datetime(2026, 11, 25, 16, 30)),
    )


def test_break_and_am_in_same_hour_give_sorted_windows() -> None:
    cfg = replace(
        example_config(),
        break_=Allowance(minutes=20, hour_no=2, offset_min=30),
        am=Allowance(minutes=10, hour_no=2),
    )
    plan = build_shift_plan(cfg, DAY)
    assert plan.slots[1].allowance_windows == (
        (datetime(2026, 11, 25, 7, 0), datetime(2026, 11, 25, 7, 10)),
        (datetime(2026, 11, 25, 7, 30), datetime(2026, 11, 25, 7, 50)),
    )
    assert plan.slots[1].planned_min == 30


def test_zero_minute_allowance_has_no_window() -> None:
    cfg = replace(example_config(), am=Allowance(minutes=0, hour_no=1))
    assert build_shift_plan(cfg, DAY).slots[0].allowance_windows == ()


# --- iné konfigurácie ---------------------------------------------------------------------------


def test_other_rate_same_time() -> None:
    plan = build_shift_plan(replace(example_config(), rate_per_hour=50), DAY)
    assert plan.planned_min == 440
    assert plan.target == pytest.approx(366.6667, abs=1e-4)
    assert math.isclose(plan.ideal_cycle_s, 72)
    assert math.isclose(sum(s.target for s in plan.slots), plan.target, abs_tol=1e-9)


def test_six_hour_shift() -> None:
    plan = build_shift_plan(six_hour_config(), DAY)
    assert len(plan.slots) == 6
    assert plan.planned_min == 325
    assert plan.target == pytest.approx(243.75)
    assert [s.planned_min for s in plan.slots] == [45, 60, 40, 60, 60, 60]
    assert math.isclose(plan.ideal_cycle_s, 80)
    assert plan.end == datetime(2026, 11, 25, 20, 0)


def test_night_shift_crosses_midnight() -> None:
    cfg = replace(example_config(), start=time(22, 0))
    plan = build_shift_plan(cfg, DAY)
    assert plan.shift_date == DAY
    assert [s.start.hour for s in plan.slots] == [22, 23, 0, 1, 2, 3, 4, 5]
    assert plan.slots[1].end == datetime(2026, 11, 26, 0, 0)
    assert plan.slots[2].start == datetime(2026, 11, 26, 0, 0)
    assert plan.end == datetime(2026, 11, 26, 6, 0)


def test_zero_minute_allowances_give_full_hours() -> None:
    cfg = replace(
        example_config(),
        duration_min=120,
        break_=Allowance(minutes=0, hour_no=1),
        am=Allowance(minutes=0, hour_no=1),
    )
    plan = build_shift_plan(cfg, DAY)
    assert [s.planned_min for s in plan.slots] == [60, 60]
    assert math.isclose(plan.target, 120)


def test_fractional_rate() -> None:
    plan = build_shift_plan(replace(example_config(), rate_per_hour=37.5), DAY)
    assert math.isclose(plan.ideal_cycle_s, 96)
    assert math.isclose(plan.target, 37.5 * 440 / 60)


# --- validácia ----------------------------------------------------------------------------------


@pytest.mark.parametrize("cfg", [example_config(), six_hour_config()], ids=["example", "six_hour"])
def test_valid_configs_have_no_issues(cfg: ShiftModelConfig) -> None:
    assert validate_shift_model(cfg) == []


def issue_fields(cfg: ShiftModelConfig) -> set[str]:
    return {i.field for i in validate_shift_model(cfg)}


@pytest.mark.parametrize("rate", [0, -60, float("nan"), float("inf")])
def test_rate_must_be_positive(rate: float) -> None:
    assert "rate_per_hour" in issue_fields(replace(example_config(), rate_per_hour=rate))


@pytest.mark.parametrize("duration", [450, 0, -60, 30])
def test_duration_must_be_whole_positive_hours(duration: int) -> None:
    assert "duration_min" in issue_fields(replace(example_config(), duration_min=duration))


def test_allowances_must_be_shorter_than_shift() -> None:
    cfg = replace(
        example_config(),
        duration_min=60,
        break_=Allowance(minutes=40, hour_no=1),
        am=Allowance(minutes=20, hour_no=1, offset_min=40),
    )
    fields = issue_fields(cfg)
    assert "duration_min" in fields  # prestávka + AM ≥ dĺžka zmeny
    assert "slots" in fields  # hodina s plánovaným časom 0 (D10)


def test_hour_with_zero_planned_time_rejected() -> None:
    cfg = replace(
        example_config(),
        break_=Allowance(minutes=30, hour_no=1, offset_min=30),
        am=Allowance(minutes=30, hour_no=1),
    )
    issues = validate_shift_model(cfg)
    assert [i.field for i in issues] == ["slots"]
    assert "1" in issues[0].message


def test_break_and_am_in_same_hour_must_not_overlap() -> None:
    cfg = replace(
        example_config(),
        break_=Allowance(minutes=20, hour_no=1, offset_min=5),
        am=Allowance(minutes=10, hour_no=1),
    )
    assert "break_" in issue_fields(cfg)


@pytest.mark.parametrize(
    ("field", "allowance"),
    [
        ("break_", Allowance(minutes=30, hour_no=5, offset_min=40)),  # presahuje svoju hodinu
        ("break_", Allowance(minutes=30, hour_no=9)),  # hodina mimo zmeny (8 h)
        ("break_", Allowance(minutes=30, hour_no=0)),
        ("break_", Allowance(minutes=-5, hour_no=5)),
        ("break_", Allowance(minutes=30, hour_no=5, offset_min=-1)),
        ("am", Allowance(minutes=70, hour_no=1)),
        ("am", Allowance(minutes=10, hour_no=1, offset_min=55)),
    ],
)
def test_allowance_must_fit_its_hour(field: str, allowance: Allowance) -> None:
    cfg = replace(example_config(), **{field: allowance})
    assert field in issue_fields(cfg)


@pytest.mark.parametrize("goal", [0, -0.1, 1.01, 85])
def test_target_oee_must_be_in_unit_interval(goal: float) -> None:
    assert "target_oee" in issue_fields(replace(example_config(), target_oee=goal))


def test_target_oee_of_one_is_allowed() -> None:
    assert validate_shift_model(replace(example_config(), target_oee=1.0)) == []


@pytest.mark.parametrize("days", [frozenset(), frozenset({7}), frozenset({-1, 0})])
def test_working_days_must_be_valid_weekdays(days: frozenset[int]) -> None:
    assert "working_days" in issue_fields(replace(example_config(), working_days=days))


def test_build_rejects_invalid_config_with_all_issues() -> None:
    cfg = replace(example_config(), rate_per_hour=0, target_oee=2)
    with pytest.raises(ShiftModelError) as exc:
        build_shift_plan(cfg, DAY)
    assert {i.field for i in exc.value.issues} == {"rate_per_hour", "target_oee"}
    assert isinstance(exc.value, ValueError)


# --- snapshot (JSON) ----------------------------------------------------------------------------


@pytest.mark.parametrize("cfg", [example_config(), six_hour_config()], ids=["example", "six_hour"])
def test_snapshot_round_trip(cfg: ShiftModelConfig) -> None:
    snap = config_to_snapshot(cfg)
    import json

    assert json.loads(json.dumps(snap)) == snap  # čisté JSON hodnoty
    assert config_from_snapshot(snap) == cfg


def test_snapshot_shape() -> None:
    snap = config_to_snapshot(six_hour_config())
    assert snap == {
        "rate_per_hour": 45,
        "start": "14:00",
        "duration_min": 360,
        "break": {"minutes": 20, "hour_no": 3, "offset_min": 10},
        "am": {"minutes": 15, "hour_no": 1, "offset_min": 0},
        "target_oee": 0.8,
        "working_days": [0, 2, 4],
    }


def test_snapshot_from_invalid_data_raises() -> None:
    snap = config_to_snapshot(example_config())
    del snap["am"]
    with pytest.raises(ShiftModelError):
        config_from_snapshot(snap)
    bad = config_to_snapshot(example_config()) | {"rate_per_hour": 0}
    with pytest.raises(ShiftModelError):
        config_from_snapshot(bad)


def test_goal_good_pcs_is_target_times_oee_goal() -> None:
    plan = build_shift_plan(six_hour_config(), DAY)
    assert plan.goal_good_pcs == pytest.approx(195)  # 243,75 × 80 %
    assert build_shift_plan(example_config(), DAY).goal_good_pcs == pytest.approx(
        374
    )  # TASK §3.2: 440 × 85 %

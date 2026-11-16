"""P0-05: validácia hodinového hlásenia V1–V12, V14 (TASK §5.5, PLANNING D10)."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, time

import pytest

from oee.domain.shift_model import Allowance, ShiftModelConfig, ShiftPlan, build_shift_plan
from oee.domain.validation import (
    ActiveCodes,
    HourInput,
    IssueInput,
    RejectLine,
    ValidationMessage,
    has_errors,
    validate_hour,
)

DAY = date(2026, 11, 25)
CODES = ActiveCodes(
    stop_codes=frozenset({"ST-038", "ST-016", "ST-046"}),
    defect_codes=frozenset({"Q-030", "Q-031"}),
    other_stop_code="ST-048",
    other_defect_code="Q-034",
)


def make_plan(rate: float = 60, start: time = time(6, 0)) -> ShiftPlan:
    """8 h; AM 10 min v 1. hod., prestávka 30 min v 5. hod. (pri 60 ks/h targety 50/60/60/60/30/60/60/60)."""
    cfg = ShiftModelConfig(
        rate_per_hour=rate,
        start=start,
        duration_min=480,
        break_=Allowance(minutes=30, hour_no=5),
        am=Allowance(minutes=10, hour_no=1),
        target_oee=0.85,
        working_days=frozenset({0, 1, 2, 3, 4}),
    )
    return build_shift_plan(cfg, DAY)


PLAN = make_plan()


def at(hh: int, mm: int) -> datetime:
    return datetime(2026, 11, 25, hh, mm)


def issue(
    key: str = "i1",
    code: str = "ST-038",
    duration: float = 10,
    start: datetime | None = None,
    continues: str | None = None,
    comment: str | None = None,
    client_key: str | None = "ck",
) -> IssueInput:
    return IssueInput(
        key=key,
        client_key=None if client_key is None else f"{client_key}-{key}",
        code=code,
        duration_min=duration,
        start=start,
        continues_key=continues,
        comment=comment,
    )


def hour(
    hour_no: int = 2,
    produced: int | None = 50,
    rejects: int | None = 0,
    by_defect: tuple[RejectLine, ...] = (),
    issues: tuple[IssueInput, ...] = (),
) -> HourInput:
    return HourInput(
        hour_no=hour_no, produced=produced, rejects=rejects, rejects_by_defect=by_defect, issues=issues
    )


def run(h: HourInput, other: tuple[IssueInput, ...] = (), plan: ShiftPlan = PLAN) -> list[ValidationMessage]:
    return validate_hour(plan, h, other, CODES)


def rules(msgs: list[ValidationMessage], level: str | None = None) -> set[str]:
    return {m.rule for m in msgs if level is None or m.level == level}


# --- platné hodiny ------------------------------------------------------------------------------


def test_clean_hour_without_problems_has_no_messages() -> None:
    assert run(hour(produced=58)) == []


def test_valid_hour_with_issue_and_rejects() -> None:
    h = hour(
        hour_no=4,
        produced=31,
        rejects=2,
        by_defect=(RejectLine("Q-030", 1), RejectLine("Q-031", 1)),
        issues=(issue(duration=25, start=at(9, 8)),),
    )
    msgs = run(h)
    assert msgs == []
    assert not has_errors(msgs)


# --- V1 / V2 / V3 -------------------------------------------------------------------------------


@pytest.mark.parametrize("produced", [None, -1])
def test_v1_produced_required_and_non_negative(produced: int | None) -> None:
    msgs = run(hour(produced=produced))
    assert rules(msgs, "error") >= {"V1"}
    assert any(m.field == "produced" for m in msgs)


def test_v2_produced_over_hourly_target_plus_one_is_error() -> None:
    assert "V2" not in rules(run(hour(hour_no=1, produced=51)))  # target hodiny 1 = 50, tolerancia +1
    assert "V2" in rules(run(hour(hour_no=1, produced=52)), "error")


def test_v2_uses_configured_rate() -> None:
    plan = make_plan(rate=45)  # hodina 2: target 45
    assert "V2" not in rules(run(hour(produced=46), plan=plan))
    assert "V2" in rules(run(hour(produced=47), plan=plan))


def test_v3_produced_over_possible_in_run_is_warning() -> None:
    issues = (issue(duration=20, start=at(7, 0)),)  # možné v chode = 40
    assert "V3" not in rules(run(hour(produced=41, issues=issues)))
    msgs = run(hour(produced=42, issues=issues))
    assert "V3" in rules(msgs, "warning")
    assert not has_errors(msgs)


# --- V4 / V5 ------------------------------------------------------------------------------------


@pytest.mark.parametrize("duration", [0, -3, float("nan")])
def test_v4_duration_must_be_positive(duration: float) -> None:
    msgs = run(hour(issues=(issue(duration=duration),)))
    assert "V4" in rules(msgs, "error")
    assert any(m.field == "issues[0].duration_min" for m in msgs)


def test_v4_duration_must_not_exceed_planned_minutes_of_hour() -> None:
    assert "V4" not in rules(run(hour(hour_no=1, produced=0, issues=(issue(duration=50),))))
    assert "V4" in rules(run(hour(hour_no=1, produced=0, issues=(issue(duration=51),))), "error")


def test_v5_sum_of_untimed_minutes_over_planned_is_error() -> None:
    issues = (issue("a", duration=40), issue("b", code="ST-016", duration=30))
    assert "V5" in rules(run(hour(produced=0, issues=issues)), "error")


def test_v5_timed_union_is_used_not_sum() -> None:
    # dve udalosti po 40 min sa prekrývajú: zjednotenie 07:00–07:50 = 50 ≤ 60 → V5 nie (V7 áno)
    issues = (
        issue("a", duration=40, start=at(7, 0)),
        issue("b", code="ST-016", duration=40, start=at(7, 10)),
    )
    msgs = run(hour(produced=0, issues=issues))
    assert "V5" not in rules(msgs)
    assert "V7" in rules(msgs, "error")


def test_v5_timed_plus_untimed() -> None:
    issues = (issue("a", duration=40, start=at(7, 0)), issue("b", code="ST-016", duration=25))
    assert "V5" in rules(run(hour(produced=0, issues=issues)), "error")


# --- V6 -----------------------------------------------------------------------------------------


@pytest.mark.parametrize("start", [at(6, 59), at(8, 0)])
def test_v6_start_outside_slot_is_error(start: datetime) -> None:
    msgs = run(hour(issues=(issue(duration=5, start=start),)))
    assert "V6" in rules(msgs, "error")
    assert any(m.field == "issues[0].start_time" for m in msgs)


def test_v6_start_in_break_is_warning() -> None:
    msgs = run(hour(hour_no=5, produced=10, issues=(issue(duration=20, start=at(10, 10)),)))
    assert "V6" in rules(msgs, "warning")
    assert not has_errors(msgs)


def test_v6_interval_past_end_of_hour_without_continuation_is_warning() -> None:
    msgs = run(hour(produced=40, issues=(issue("a", duration=20, start=at(7, 50)),)))
    assert "V6" in rules(msgs, "warning")


def test_v6_interval_past_end_with_continuation_is_ok() -> None:
    cont = issue("b", duration=10, start=at(8, 0), continues="a")
    msgs = run(hour(produced=40, issues=(issue("a", duration=10, start=at(7, 50)),)), other=(cont,))
    assert "V6" not in rules(msgs)
    msgs = run(hour(produced=40, issues=(issue("a", duration=20, start=at(7, 50)),)), other=(cont,))
    assert "V6" not in rules(msgs, "warning")  # pokračovanie existuje
    assert "V7" not in rules(msgs)  # 07:50–08:10 vs 08:00–08:10: vlastné pokračovanie nie je prekryv


# --- V7 -----------------------------------------------------------------------------------------


def test_v7_overlap_within_hour_is_error() -> None:
    issues = (
        issue("a", duration=20, start=at(7, 10)),
        issue("b", code="ST-016", duration=10, start=at(7, 20)),
    )
    msgs = run(hour(produced=30, issues=issues))
    assert "V7" in rules(msgs, "error")
    assert any(m.field == "issues[1].start_time" for m in msgs if m.rule == "V7")


def test_v7_touching_intervals_are_ok() -> None:
    issues = (
        issue("a", duration=10, start=at(7, 10)),
        issue("b", code="ST-016", duration=10, start=at(7, 20)),
    )
    assert "V7" not in rules(run(hour(produced=30, issues=issues)))


def test_v7_overlap_across_hours_is_error() -> None:
    other = (issue("x", duration=30, start=at(6, 50)),)  # hodina 1 siaha do 07:20
    msgs = run(hour(produced=30, issues=(issue("a", duration=10, start=at(7, 10)),)), other=other)
    assert "V7" in rules(msgs, "error")


def test_v7_untimed_events_are_not_checked_for_overlap() -> None:
    issues = (issue("a", duration=10), issue("b", code="ST-016", duration=10))
    assert "V7" not in rules(run(hour(produced=30, issues=issues)))


# --- V8 -----------------------------------------------------------------------------------------


def test_v8_possible_duplicate_is_warning() -> None:
    issues = (issue("a", duration=10), issue("b", duration=10))
    msgs = run(hour(produced=30, issues=issues))
    assert "V8" in rules(msgs, "warning")
    assert not has_errors(msgs)


@pytest.mark.parametrize(
    "second",
    [
        issue("b", code="ST-016", duration=10),  # iný kód
        issue("b", duration=12),  # iné trvanie
        issue("b", duration=10, start=at(7, 30)),  # má čas
    ],
)
def test_v8_not_a_duplicate(second: IssueInput) -> None:
    assert "V8" not in rules(run(hour(produced=30, issues=(issue("a", duration=10), second))))


# --- V9 -----------------------------------------------------------------------------------------


def test_v9_client_key_required() -> None:
    msgs = run(hour(produced=30, issues=(issue(client_key=None),)))
    assert "V9" in rules(msgs, "error")


def test_v9_duplicate_client_key_in_hour_is_error() -> None:
    a = issue("a")
    b = replace(issue("b", code="ST-016", duration=7), client_key=a.client_key)
    assert "V9" in rules(run(hour(produced=30, issues=(a, b))), "error")


# --- V10 ----------------------------------------------------------------------------------------


@pytest.mark.parametrize("rejects", [None, -1, 51])
def test_v10_rejects_required_non_negative_and_not_over_produced(rejects: int | None) -> None:
    msgs = run(hour(produced=50, rejects=rejects))
    assert "V10" in rules(msgs, "error")
    assert any(m.field == "rejects" for m in msgs)


def test_v10_rejects_equal_to_produced_is_ok() -> None:
    assert "V10" not in rules(run(hour(produced=5, rejects=5)))


def test_v10_breakdown_must_sum_to_rejects() -> None:
    msgs = run(hour(produced=50, rejects=3, by_defect=(RejectLine("Q-030", 1),)))
    assert "V10" in rules(msgs, "error")
    assert any(m.field == "rejects_by_defect" for m in msgs)


def test_v10_breakdown_quantities_must_be_positive() -> None:
    msgs = run(hour(produced=50, rejects=0, by_defect=(RejectLine("Q-030", 0),)))
    assert any(m.rule == "V10" and m.field == "rejects_by_defect[0].qty" for m in msgs)


def test_v10_rejects_without_breakdown_is_ok() -> None:
    assert run(hour(produced=50, rejects=3)) == []


# --- V11 ----------------------------------------------------------------------------------------


def test_v11_inactive_stop_code_is_error() -> None:
    msgs = run(hour(produced=30, issues=(issue(code="ST-099"),)))
    assert "V11" in rules(msgs, "error")
    assert any(m.field == "issues[0].code" for m in msgs)


def test_v11_missing_stop_code_is_error() -> None:
    assert "V11" in rules(run(hour(produced=30, issues=(issue(code=""),))), "error")


@pytest.mark.parametrize("comment", [None, "", "   "])
def test_v11_other_without_comment_is_error(comment: str | None) -> None:
    msgs = run(hour(produced=30, issues=(issue(code="ST-048", comment=comment),)))
    assert "V11" in rules(msgs, "error")
    assert any(m.field == "issues[0].comment" for m in msgs)


def test_v11_other_with_comment_is_ok() -> None:
    assert run(hour(produced=30, issues=(issue(code="ST-048", comment="conveyor jam"),))) == []


def test_v11_inactive_defect_code_is_error() -> None:
    msgs = run(hour(produced=30, rejects=1, by_defect=(RejectLine("Q-099", 1),)))
    assert any(m.rule == "V11" and m.field == "rejects_by_defect[0].code" for m in msgs)


def test_v11_other_defect_needs_comment() -> None:
    assert "V11" in rules(run(hour(produced=30, rejects=1, by_defect=(RejectLine("Q-034", 1),))))
    assert run(hour(produced=30, rejects=1, by_defect=(RejectLine("Q-034", 1, "scratch"),))) == []


def test_v11_defect_code_is_not_a_stop_code() -> None:
    assert "V11" in rules(run(hour(produced=30, issues=(issue(code="Q-030"),))))


# --- V12 ----------------------------------------------------------------------------------------


def test_v12_no_production_and_no_problem_is_warning() -> None:
    msgs = run(hour(produced=0))
    assert rules(msgs) == {"V12"}
    assert not has_errors(msgs)


def test_v12_not_raised_when_problem_reported() -> None:
    assert "V12" not in rules(run(hour(produced=0, issues=(issue(duration=60),))))


# --- V14 ----------------------------------------------------------------------------------------


@pytest.mark.parametrize("hour_no", [0, 9])
def test_v14_hour_must_belong_to_shift(hour_no: int) -> None:
    msgs = run(hour(hour_no=hour_no))
    assert [(m.rule, m.level, m.field) for m in msgs] == [("V14", "error", "hour_no")]


# --- ostatné ------------------------------------------------------------------------------------


def test_night_shift_slot_after_midnight() -> None:
    plan = make_plan(start=time(22, 0))
    ok = issue(duration=10, start=datetime(2026, 11, 26, 0, 30))  # hodina 3 = 00:00–01:00 (26.11.)
    assert run(hour(hour_no=3, produced=40, issues=(ok,)), plan=plan) == []
    wrong_day = issue(duration=10, start=datetime(2026, 11, 25, 0, 30))
    assert "V6" in rules(run(hour(hour_no=3, produced=40, issues=(wrong_day,)), plan=plan), "error")


def test_messages_are_sorted_errors_first_and_have_text() -> None:
    msgs = run(hour(produced=0, rejects=-1))
    assert msgs[0].level == "error"
    assert all(m.message for m in msgs)


def test_v7_continuation_link_does_not_hide_unrelated_overlap() -> None:
    cont = issue("b", duration=10, start=at(8, 0), continues="a")
    other = issue("c", code="ST-016", duration=15, start=at(7, 55))
    h = hour(produced=40, issues=(issue("a", duration=20, start=at(7, 50)), other))
    assert "V7" in rules(run(h, other=(cont,)), "error")


# --- iná konfigurácia zmeny (D8) ----------------------------------------------------------------


def six_hour_plan() -> ShiftPlan:
    """6 h od 14:00, 45 ks/h; AM 15 min v 1. hod., prestávka 20 min v 3. hod. (16:10–16:30)."""
    cfg = ShiftModelConfig(
        rate_per_hour=45,
        start=time(14, 0),
        duration_min=360,
        break_=Allowance(minutes=20, hour_no=3, offset_min=10),
        am=Allowance(minutes=15, hour_no=1),
        target_oee=0.8,
        working_days=frozenset({0, 2, 4}),
    )
    return build_shift_plan(cfg, DAY)


def test_other_config_hour_range() -> None:
    plan = six_hour_plan()
    assert run(hour(hour_no=6, produced=40), plan=plan) == []
    assert [m.rule for m in run(hour(hour_no=7, produced=40), plan=plan)] == ["V14"]


def test_other_config_planned_minutes_and_target() -> None:
    plan = six_hour_plan()  # hodina 3: 40 plánovaných minút, target 30 ks
    assert "V4" in rules(run(hour(hour_no=3, produced=0, issues=(issue(duration=41),)), plan=plan))
    assert "V4" not in rules(run(hour(hour_no=3, produced=0, issues=(issue(duration=40),)), plan=plan))
    assert "V2" in rules(run(hour(hour_no=3, produced=32), plan=plan))
    assert "V2" not in rules(run(hour(hour_no=3, produced=31), plan=plan))


def test_other_config_break_with_offset() -> None:
    plan = six_hour_plan()
    in_break = issue(duration=10, start=datetime(2026, 11, 25, 16, 15))
    before_break = issue(duration=5, start=datetime(2026, 11, 25, 16, 0))
    assert "V6" in rules(run(hour(hour_no=3, produced=20, issues=(in_break,)), plan=plan), "warning")
    assert run(hour(hour_no=3, produced=20, issues=(before_break,)), plan=plan) == []

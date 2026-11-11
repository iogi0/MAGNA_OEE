"""P0-11: rebríček problémov (TASK §8.4, PLANNING D10) — syntetické prípady pre každé pravidlo.

Golden §12.5 na celom datasete sa overuje v P0-13.
"""

from __future__ import annotations

from datetime import date

import pytest

from oee.domain.ranking import ProblemStats, RankingSettings, WeekInfo, rank_problems

W = [WeekInfo(key=k, complete=True, shifts=5) for k in ("W1", "W2", "W3", "W4")]


def p(
    code: str,
    lost: float,
    *,
    kind: str = "downtime",
    freq: int = 1,
    last: date | None = date(2026, 11, 20),
    weekly: dict[str, tuple[float, int]] | None = None,
) -> ProblemStats:
    return ProblemStats(
        code=code,
        kind=kind,  # type: ignore[arg-type]
        lost_pcs=lost,
        frequency=freq,
        last_occurrence=last,
        weekly=weekly or {},
    )


def rank(problems: list[ProblemStats], weeks: list[WeekInfo] = W, **kw: object) -> dict[str, object]:
    out = rank_problems(
        problems, weeks, period_target=kw.pop("target", 1000), all_losses=kw.pop("all_losses", 200), **kw
    )  # type: ignore[arg-type]
    return {r.code: r for r in out}


def codes(problems: list[ProblemStats], weeks: list[WeekInfo] = W, **kw: object) -> list[str]:
    return [r.code for r in rank_problems(problems, weeks, period_target=1000, all_losses=200, **kw)]  # type: ignore[arg-type]


# --- ABC (Pareto 80 / 95 %) ---------------------------------------------------------------------


def test_abc_uses_cumulative_share_before_item() -> None:
    # podiely 50, 25, 10, 10, 5 % → kumulatívne pred položkou 0, 50, 75, 85, 95 → A A A B C
    problems = [p("ST-001", 50), p("ST-002", 25), p("ST-003", 10), p("ST-004", 10, freq=0), p("ST-005", 5)]
    r = rank(problems)
    assert [r[c].abc_class for c in ("ST-001", "ST-002", "ST-003", "ST-004", "ST-005")] == [
        "A",
        "A",
        "A",
        "B",
        "C",
    ]
    assert [r[c].rank for c in ("ST-001", "ST-002", "ST-003", "ST-004", "ST-005")] == [1, 2, 3, 4, 5]


def test_shares_and_kpi_impact() -> None:
    r = rank([p("ST-038", 100), p("Q-031", 38, kind="quality")], target=9240, all_losses=1108)
    st = r["ST-038"]
    assert st.share_of_recorded == pytest.approx(100 / 138)
    assert st.share_of_all_losses == pytest.approx(100 / 1108)
    assert st.kpi_impact_pp == pytest.approx(100 / 9240 * 100)  # TASK §6.5: lost / C × 100
    assert st.kpi == "availability"
    assert r["Q-031"].kpi == "quality"


def test_downtime_and_quality_compete_in_one_ranking() -> None:
    assert codes([p("ST-001", 20), p("Q-031", 38, kind="quality")]) == ["Q-031", "ST-001"]


# --- tie-break (§8.4, §12.5) --------------------------------------------------------------------


def test_tie_break_frequency() -> None:
    # ST-001 pred ST-047: rovnaký vplyv, frekvencia 7 > 4
    assert codes([p("ST-047", 60, freq=4), p("ST-001", 60, freq=7)]) == ["ST-001", "ST-047"]


def test_tie_break_last_occurrence() -> None:
    # ST-016 pred ST-046: rovnaký vplyv aj frekvencia, posledný výskyt 30.11 > 27.11
    problems = [
        p("ST-046", 70, freq=7, last=date(2026, 11, 27)),
        p("ST-016", 70, freq=7, last=date(2026, 11, 30)),
    ]
    assert codes(problems) == ["ST-016", "ST-046"]


def test_tie_break_code() -> None:
    # Q-020 pred Q-026: úplná zhoda → kód
    problems = [p("Q-026", 28, kind="quality", freq=26), p("Q-020", 28, kind="quality", freq=26)]
    assert codes(problems) == ["Q-020", "Q-026"]


def test_missing_last_occurrence_sorts_after_known() -> None:
    assert codes([p("ST-002", 10, last=None), p("ST-003", 10)]) == ["ST-003", "ST-002"]


# --- trend --------------------------------------------------------------------------------------


def weekly(*pairs: tuple[float, int]) -> dict[str, tuple[float, int]]:
    return {f"W{i}": v for i, v in enumerate(pairs, start=1)}


@pytest.mark.parametrize(
    ("series", "trend", "change"),
    [
        (weekly((25, 1), (25, 1), (25, 1), (25, 1)), "stable", 0.0),  # ST-038: 50 vs 50
        (weekly((6, 1), (0, 0), (25, 2), (26, 2)), "up", (51 - 6) / 6),  # ST-016: 51 vs 6
        (weekly((15, 1), (18, 2), (17, 1), (20, 1)), "stable", (37 - 33) / 33),  # ST-046: +12 %
        (weekly((20, 2), (15, 2), (15, 1), (10, 1)), "down", (25 - 35) / 35),  # ST-001: −29 %
        (weekly((25, 2), (25, 2), (0, 0), (0, 0)), "down", -1.0),  # ST-017: 0 vs 50
        (weekly((0, 0), (0, 0), (5, 2), (5, 2)), "up", None),  # staršia polovica 0 → ↑, zmena nedefinovaná
    ],
    ids=["stable", "up", "plus12", "minus29", "vanished", "from_zero"],
)
def test_trend(series: dict[str, tuple[float, int]], trend: str, change: float | None) -> None:
    r = rank([p("ST-001", 1, weekly=series)])["ST-001"]
    assert r.trend == trend
    if change is None:
        assert r.trend_change is None
    else:
        assert r.trend_change == pytest.approx(change)


def test_trend_thresholds_are_inclusive() -> None:
    assert (
        rank([p("ST-001", 1, weekly=weekly((10, 1), (10, 1), (12, 1), (12, 1)))])["ST-001"].trend == "up"
    )  # +20 %
    assert (
        rank([p("ST-001", 1, weekly=weekly((10, 1), (10, 1), (8, 1), (8, 1)))])["ST-001"].trend == "down"
    )  # −20 %


def test_trend_compares_per_shift() -> None:
    weeks = [
        WeekInfo("W1", True, 5),
        WeekInfo("W2", True, 5),
        WeekInfo("W3", True, 2),
        WeekInfo("W4", True, 2),
    ]
    # staršie: 20 / 10 zmien = 2,0; novšie: 8 / 4 zmeny = 2,0 → stable (súčty by ukázali pokles)
    r = rank([p("ST-001", 1, weekly=weekly((10, 2), (10, 2), (4, 1), (4, 1)))], weeks=weeks)["ST-001"]
    assert r.trend == "stable"


def test_incomplete_weeks_are_ignored() -> None:
    weeks = [*W, WeekInfo("W5", complete=False, shifts=1)]  # týždeň 49 (partial) sa do trendu nepočíta
    series = {**weekly((25, 1), (25, 1), (25, 1), (25, 1)), "W5": (100, 5)}
    assert rank([p("ST-001", 1, weekly=series)], weeks=weeks)["ST-001"].trend == "stable"


def test_trend_na_with_fewer_than_two_complete_weeks() -> None:
    weeks = [WeekInfo("W1", True, 5), WeekInfo("W2", False, 3)]
    r = rank([p("ST-001", 1, weekly={"W1": (10, 5), "W2": (50, 5)})], weeks=weeks)["ST-001"]
    assert (r.trend, r.trend_change) == ("n/a", None)


def test_trend_na_with_fewer_than_three_events_in_both_halves() -> None:
    # D10: < 3 udalosti spolu v oboch polovičkách
    r = rank([p("ST-001", 1, weekly=weekly((0, 0), (0, 0), (10, 1), (10, 1)))])["ST-001"]
    assert r.trend == "n/a"


def test_odd_number_of_weeks_skips_middle_week() -> None:
    weeks = W[:3]  # W1, W2, W3 → staršia W1, novšia W3, W2 vynechaný (D10)
    r = rank([p("ST-001", 1, weekly=weekly((10, 2), (100, 9), (10, 2)))], weeks=weeks)["ST-001"]
    assert (r.trend, r.trend_change) == ("stable", 0.0)


def test_quality_trend_counts_records_as_events() -> None:
    # D10: pri zmätkoch sa počítajú záznamy (frekvencia), nie kusy
    r = rank([p("Q-031", 1, kind="quality", weekly=weekly((5, 1), (5, 0), (10, 1), (10, 0)))])["Q-031"]
    assert r.trend == "n/a"  # 2 záznamy < 3, hoci kusov je 30


# --- eskalácia ----------------------------------------------------------------------------------


def test_escalation_up_trend_and_share_at_least_5_percent() -> None:
    rising = weekly((1, 1), (1, 1), (5, 1), (5, 1))
    problems = [p("ST-001", 80), p("ST-002", 12), p("ST-003", 6, weekly=rising), p("ST-004", 2)]
    # podiely 80, 12, 6, 2 % → kumulatívne 0, 80, 92, 98 → A, B, B, C; ST-003 ↑ a 6 % ≥ 5 % → A
    r = rank(problems)
    assert (r["ST-003"].base_class, r["ST-003"].abc_class, r["ST-003"].escalated) == ("B", "A", True)
    assert codes(problems) == ["ST-001", "ST-003", "ST-002", "ST-004"]  # trieda má prednosť pred kusmi


def test_no_escalation_below_5_percent_share() -> None:
    # Q-030 v §12.5: ↑, ale podiel 4,7 % < 5 % → bez eskalácie, zostáva C
    rising = weekly((4, 1), (6, 1), (7, 1), (7, 1))
    problems = [p("ST-001", 90), p("ST-002", 5.3), p("Q-030", 4.7, kind="quality", weekly=rising)]
    r = rank(problems)
    assert r["Q-030"].trend == "up"
    assert (r["Q-030"].abc_class, r["Q-030"].escalated) == ("C", False)


def test_class_a_cannot_escalate_further() -> None:
    rising = weekly((1, 1), (1, 1), (5, 1), (5, 1))
    r = rank([p("ST-001", 100, weekly=rising)])["ST-001"]
    assert (r.abc_class, r.escalated) == ("A", False)


def test_settings_change_thresholds() -> None:
    problems = [p("ST-001", 70), p("ST-002", 30)]
    assert rank(problems)["ST-002"].abc_class == "A"
    strict = RankingSettings(class_a_share=0.6, class_b_share=0.7)  # 70 % pred ST-002 → C
    assert rank(problems, settings=strict)["ST-002"].abc_class == "C"


# --- okrajové prípady ---------------------------------------------------------------------------


def test_empty_input() -> None:
    assert rank_problems([], W, period_target=1000, all_losses=0) == []


def test_zero_impact_and_zero_losses_do_not_divide_by_zero() -> None:
    r = rank([p("ST-001", 0)], target=0, all_losses=0)["ST-001"]
    assert (r.share_of_recorded, r.share_of_all_losses, r.kpi_impact_pp) == (None, None, None)
    assert r.abc_class == "A"


def test_escalation_from_c_to_b() -> None:
    rising = weekly((1, 1), (1, 1), (5, 1), (5, 1))
    problems = [p("ST-001", 95), p("ST-003", 5, weekly=rising)]  # pred ST-003 = 95 % → C, ↑ a 5 % ≥ 5 % → B
    r = rank(problems)["ST-003"]
    assert (r.base_class, r.abc_class, r.escalated) == ("C", "B", True)


def test_single_complete_week_never_compares_with_itself() -> None:
    weeks = [WeekInfo("W1", True, 5)]
    r = rank(
        [p("ST-001", 1, weekly={"W1": (10, 5)})], weeks=weeks, settings=RankingSettings(min_complete_weeks=1)
    )
    assert r["ST-001"].trend == "n/a"

"""P0-13 (golden): Problem Links za november 2026 (TASK §12.8)."""

from __future__ import annotations

from datetime import datetime

import pytest

from oee.contracts.period_analytics import PeriodAnalytics

pytestmark = pytest.mark.golden

NOW = datetime(2026, 12, 1, 9, 0)

EXPECTED = {  # TASK §12.8: typ, support, Q v okne, výroba v okne, miera v okne, základná, lift, extra, istota
    ("ST-038", "Q-030"): ("same_process", 4, 3, 228, 0.0132, 0.0027, 4.8, 2.4, "low"),
    ("ST-016", "Q-031"): ("cross_process", 7, 6, 582, 0.0103, 0.0042, 2.47, 3.6, "medium"),
    ("ST-047", "Q-030"): ("cross_process", 4, 3, 400, 0.0075, 0.0028, 2.68, 1.9, "low"),
    ("ST-017", "Q-031"): ("cross_process", 4, 3, 264, 0.0114, 0.0044, 2.59, 1.8, "low"),
    ("ST-046", "Q-020"): ("cross_process", 7, 4, 602, 0.0066, 0.0031, 2.12, 2.1, "low"),
}


def test_exactly_five_links(month: PeriodAnalytics) -> None:
    assert {(link.cause, link.effect) for link in month.problem_links} == set(
        EXPECTED
    )  # poradie TASK nepredpisuje


@pytest.mark.parametrize("pair", list(EXPECTED), ids=[f"{c}-{e}" for c, e in EXPECTED])
def test_link_values(month: PeriodAnalytics, pair: tuple[str, str]) -> None:
    link = next(x for x in month.problem_links if (x.cause, x.effect) == pair)
    link_type, support, q_in, produced_in, rate, base, lift, extra, confidence = EXPECTED[pair]
    assert (link.link_type, link.support, link.q_in_window, link.produced_in_window) == (
        link_type,
        support,
        q_in,
        produced_in,
    )
    assert link.rate_in_window == pytest.approx(rate, abs=5e-5)
    assert link.base_rate == pytest.approx(base, abs=5e-5)
    assert link.lift == pytest.approx(lift, abs=0.01 if lift < 4 else 0.05)  # §12.8 uvádza 4,8 na 1 miesto
    assert link.extra_rejects == pytest.approx(extra, abs=0.05)
    assert link.confidence == confidence
    assert link.window == "same_hour+next_hour"


def test_same_process_link_details(month: PeriodAnalytics) -> None:
    link = next(x for x in month.problem_links if (x.cause, x.effect) == ("ST-038", "Q-030"))
    assert link.process == "Camera"
    assert link.combined_impact_pcs == pytest.approx(100 + link.extra_rejects)  # §8.6: lost pcs ST + extra Q
    assert len(link.evidence) == 4


def test_leak_test_pair_below_lift_threshold_is_not_a_link(month: PeriodAnalytics) -> None:
    # TASK §12.8: ST-046 → Q-031 (same_process, lift 1,93 < 2,0) nie je väzba
    assert ("ST-046", "Q-031") not in {(x.cause, x.effect) for x in month.problem_links}

"""P0-12: Problem Links — väzby prestoj → zmätok (TASK §8.6, PLANNING D10). Syntetické prípady.

Golden §12.8 na celom datasete sa overuje v P0-13.
"""

from __future__ import annotations

import pytest

from oee.domain.correlation import HourObs, LinkSettings, StopEvent, find_problem_links

STOPS = frozenset({"ST-038", "ST-046"})
DEFECTS = frozenset({"Q-030", "Q-031"})
SAME = {("ST-038", "Q-030"): "Camera", ("ST-046", "Q-031"): "Leak test"}


def shift_hours(
    shift: str, produced: int = 50, n: int = 8, defects: dict[int, dict[str, int]] | None = None
) -> list[HourObs]:
    defects = defects or {}
    return [
        HourObs(shift_id=shift, hour_no=h, produced=produced, defects=defects.get(h, {}))
        for h in range(1, n + 1)
    ]


def ev(code: str, shift: str, *hours: int, event_id: str | None = None) -> StopEvent:
    return StopEvent(
        event_id=event_id or f"{code}-{shift}-{hours[0]}", code=code, shift_id=shift, hour_nos=hours
    )


def run(hours: list[HourObs], events: list[StopEvent], **kw: object) -> dict[tuple[str, str], object]:
    results = find_problem_links(
        hours,
        events,
        stop_codes=kw.pop("stop_codes", STOPS),  # type: ignore[arg-type]
        defect_codes=kw.pop("defect_codes", DEFECTS),  # type: ignore[arg-type]
        same_process=kw.pop("same_process", SAME),  # type: ignore[arg-type]
        stop_lost_pcs=kw.pop("stop_lost_pcs", {"ST-038": 100.0, "ST-046": 70.0}),  # type: ignore[arg-type]
        **kw,  # type: ignore[arg-type]
    )
    return {(r.cause, r.effect): r for r in results}


def camera_dataset() -> tuple[list[HourObs], list[StopEvent]]:
    """4 zmeny po 8 h × 50 ks; ST-038 v 4. hod. každej zmeny.

    Q-030: 1 ks v okne zmien A, B, C a 1 ks mimo okien (zmena D, hod. 8).
    """
    hours: list[HourObs] = []
    for shift, d in (
        ("A", {4: {"Q-030": 1}}),
        ("B", {5: {"Q-030": 1}}),
        ("C", {4: {"Q-030": 1}}),
        ("D", {8: {"Q-030": 1}}),
    ):
        hours += shift_hours(shift, defects=d)
    events = [ev("ST-038", s, 4) for s in "ABCD"]
    return hours, events


# --- výpočet štatistík --------------------------------------------------------------------------


def test_window_rates_lift_and_extra() -> None:
    hours, events = camera_dataset()
    r = run(hours, events)[("ST-038", "Q-030")]
    # okná: hodiny 4 a 5 v 4 zmenách = 8 h × 50 = 400 ks; mimo: 24 h × 50 = 1200 ks
    assert (r.support, r.q_in_window, r.produced_in_window) == (4, 3, 400)
    assert r.rate_in_window == pytest.approx(3 / 400)
    assert r.base_rate == pytest.approx(1 / 1200)
    assert r.lift == pytest.approx((3 / 400) / (1 / 1200))  # 9
    assert r.extra_rejects == pytest.approx(3 - 400 / 1200)
    assert r.combined_impact_pcs == pytest.approx(100 + 3 - 400 / 1200)
    assert (r.link_type, r.process) == ("same_process", "Camera")
    assert r.status == "link" and r.is_link


def test_next_hour_must_be_in_same_shift() -> None:
    # ST-038 v poslednej hodine zmeny A: okno = iba hodina 8 (nie hodina 1 zmeny B)
    hours = shift_hours("A", defects={8: {"Q-030": 1}}) + shift_hours("B", defects={1: {"Q-030": 5}})
    r = run(hours, [ev("ST-038", "A", 8)])[("ST-038", "Q-030")]
    assert (r.q_in_window, r.produced_in_window) == (1, 50)


def test_overlapping_windows_count_hour_once() -> None:
    # udalosti v hod. 3 a 4 → okná {3, 4} ∪ {4, 5} = {3, 4, 5}
    hours = shift_hours("A", defects={4: {"Q-030": 2}, 1: {"Q-030": 1}})
    r = run(hours, [ev("ST-038", "A", 3), ev("ST-038", "A", 4)])[("ST-038", "Q-030")]
    assert (r.support, r.q_in_window, r.produced_in_window) == (2, 2, 150)


def test_continuation_window_covers_all_segments_and_next_hour() -> None:
    # D10: udalosť cez hodiny 3–4 → okno {3, 4, 5}; support = 1
    hours = shift_hours("A", defects={5: {"Q-030": 1}})
    r = run(hours, [ev("ST-038", "A", 3, 4)])[("ST-038", "Q-030")]
    assert (r.support, r.q_in_window, r.produced_in_window) == (1, 1, 150)


def test_cross_process_pair() -> None:
    hours, events = camera_dataset()
    hours = [
        HourObs(h.shift_id, h.hour_no, h.produced, {"Q-031": sum(h.defects.values())} if h.defects else {})
        for h in hours
    ]
    r = run(hours, events)[("ST-038", "Q-031")]
    assert (r.link_type, r.process) == ("cross_process", None)


# --- prahy --------------------------------------------------------------------------------------


def test_support_below_threshold_is_not_a_link() -> None:
    hours, events = camera_dataset()
    r = run(hours, events[:2])[("ST-038", "Q-030")]  # support 2 < 3
    assert r.status == "below_threshold" and not r.is_link


def test_q_in_window_below_threshold() -> None:
    hours, events = camera_dataset()
    hours = [
        h if (h.shift_id, h.hour_no) != ("C", 4) else HourObs("C", 4, 50, {}) for h in hours
    ]  # Q v okne = 2
    assert run(hours, events)[("ST-038", "Q-030")].status == "below_threshold"


def test_lift_below_two_is_not_a_link() -> None:
    # ako ST-046 → Q-031 v §12.8 (lift 1,93 < 2): okno 3/400, mimo 5/1200 → lift 1,8
    hours, events = camera_dataset()
    extra = {("D", 1): 1, ("D", 2): 1, ("D", 3): 1, ("D", 6): 1}
    hours = [
        HourObs(
            h.shift_id,
            h.hour_no,
            h.produced,
            {"Q-030": h.defects.get("Q-030", 0) + extra.get((h.shift_id, h.hour_no), 0)},
        )
        for h in hours
    ]
    r = run(hours, events)[("ST-038", "Q-030")]
    assert r.lift == pytest.approx(1.8)
    assert r.status == "below_threshold"


def test_custom_settings() -> None:
    hours, events = camera_dataset()
    r = run(hours, events[:2], settings=LinkSettings(min_support=2))[("ST-038", "Q-030")]
    assert r.status == "below_threshold"  # Q v okne 2 < 3
    r = run(hours, events[:2], settings=LinkSettings(min_support=2, min_q_in_window=2))[("ST-038", "Q-030")]
    assert r.is_link


# --- istota -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("window_q", "n_shifts", "confidence"),
    [
        ({4: 1}, 4, "low"),  # extra = 4 − 400 × 4/1200 = 2,67
        ({4: 2, 5: 2}, 4, "medium"),  # extra = 16 − 400 × 4/1200 = 14,7, ale support 4 < 5
        ({4: 2, 5: 2}, 6, "high"),  # extra ≥ 10 a support ≥ 5
    ],
)
def test_confidence(window_q: dict[int, int], n_shifts: int, confidence: str) -> None:
    hours: list[HourObs] = []
    events: list[StopEvent] = []
    for i in range(n_shifts):
        s = f"S{i}"
        defects = {h: {"Q-030": q} for h, q in window_q.items()} | {8: {"Q-030": 1}}
        hours += shift_hours(s, defects=defects)
        events.append(ev("ST-038", s, 4))
    r = run(hours, events)[("ST-038", "Q-030")]
    assert r.is_link
    assert r.confidence == confidence


# --- nedostatok dát (D10) — bez delenia nulou ---------------------------------------------------


def test_zero_base_rate_is_insufficient_data() -> None:
    hours = shift_hours("A", defects={4: {"Q-030": 3}}) + shift_hours("B", defects={4: {"Q-030": 3}})
    events = [ev("ST-038", "A", 4), ev("ST-038", "B", 4), ev("ST-038", "A", 6)]
    r = run(hours, events)[("ST-038", "Q-030")]
    assert r.base_rate == 0
    assert (r.lift, r.status, r.is_link) == (None, "insufficient_data", False)


def test_no_production_outside_windows_is_insufficient_data() -> None:
    hours = shift_hours("A", n=2, defects={1: {"Q-030": 3}})
    r = run(hours, [ev("ST-038", "A", 1)])[("ST-038", "Q-030")]
    assert (r.base_rate, r.lift, r.status) == (None, None, "insufficient_data")


def test_no_production_in_window_is_insufficient_data() -> None:
    hours = [
        HourObs("A", 1, 0, {}),
        HourObs("A", 2, 0, {}),
        *[HourObs("A", h, 50, {"Q-030": 1}) for h in range(3, 9)],
    ]
    r = run(hours, [ev("ST-038", "A", 1)])[("ST-038", "Q-030")]
    assert (r.rate_in_window, r.lift, r.status) == (None, None, "insufficient_data")


# --- rozsah párov -------------------------------------------------------------------------------


def test_only_active_codes_and_stops_with_events() -> None:
    hours, events = camera_dataset()
    events.append(ev("ST-999", "A", 2))  # neaktívny kód
    results = run(hours, events)
    assert set(results) == {("ST-038", "Q-030"), ("ST-038", "Q-031")}  # ST-046 nemá udalosť


def test_links_sorted_first_then_by_lift() -> None:
    hours, events = camera_dataset()
    ordered = find_problem_links(
        hours,
        events,
        stop_codes=STOPS,
        defect_codes=DEFECTS,
        same_process=SAME,
        stop_lost_pcs={},
    )
    assert [r.status for r in ordered][0] == "link"
    assert ordered[0].combined_impact_pcs == pytest.approx(
        ordered[0].extra_rejects
    )  # neznáme kusy prestoja = 0


def test_empty_input() -> None:
    assert (
        find_problem_links(
            [], [], stop_codes=STOPS, defect_codes=DEFECTS, same_process=SAME, stop_lost_pcs={}
        )
        == []
    )


# --- doplnky z revízie --------------------------------------------------------------------------


def test_insufficient_data_has_no_extra_or_confidence_signal() -> None:
    hours = shift_hours("A", defects={4: {"Q-030": 30}}) + shift_hours("B", defects={4: {"Q-030": 30}})
    events = [ev("ST-038", "A", 4), ev("ST-038", "B", 4), ev("ST-038", "A", 6)]
    r = run(hours, events)[("ST-038", "Q-030")]
    assert r.status == "insufficient_data"
    assert (r.extra_rejects, r.confidence) == (0.0, "low")
    assert r.combined_impact_pcs == pytest.approx(100.0)


def test_stop_event_needs_hours() -> None:
    with pytest.raises(ValueError, match="hour"):
        StopEvent(event_id="x", code="ST-038", shift_id="A", hour_nos=())


def test_duplicate_hour_is_rejected() -> None:
    hours = [*shift_hours("A"), HourObs("A", 1, 50, {})]
    with pytest.raises(ValueError, match="duplicate"):
        run(hours, [ev("ST-038", "A", 2)])


def test_lift_exactly_at_threshold_is_a_link() -> None:
    hours = shift_hours("A", n=4, defects={1: {"Q-030": 3}}) + shift_hours(
        "B", n=4, defects={3: {"Q-030": 3}}
    )
    events = [ev("ST-038", "A", 1), ev("ST-038", "A", 2), ev("ST-038", "A", 3)]
    r = run(hours, events)[("ST-038", "Q-030")]
    # okno = A1..A4 (200 ks, 3 Q), mimo = B (200 ks, 3 Q) → lift 1,0
    assert r.lift == pytest.approx(1.0)
    r2 = run(hours, events, settings=LinkSettings(min_lift=1.0))[("ST-038", "Q-030")]
    assert r2.is_link  # hranica je inkluzívna


def test_same_process_links_before_cross_process() -> None:
    hours, events = camera_dataset()
    hours = [
        HourObs(h.shift_id, h.hour_no, h.produced, {**h.defects, "Q-031": 2 * sum(h.defects.values())})
        for h in hours
    ]
    ordered = find_problem_links(
        hours, events, stop_codes=STOPS, defect_codes=DEFECTS, same_process=SAME, stop_lost_pcs={}
    )
    links = [(r.cause, r.effect, r.link_type) for r in ordered if r.is_link]
    assert links == [("ST-038", "Q-030", "same_process"), ("ST-038", "Q-031", "cross_process")]

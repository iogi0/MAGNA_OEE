"""Problem Links — štatistika väzieb „prestoj ST → zmätok Q" (TASK §8.6, PLANNING D10).

Kód počíta čísla; AI iba vysvetľuje. Korelácia ≠ dokázaná príčina.

- Okno udalosti = jej hodiny (aj pokračovania) + nasledujúca hodina **tej istej zmeny**.
  Okná toho istého kódu ST sa zjednocujú — každá hodina sa započíta raz.
- support = počet udalostí ST; Q v okne / výroba v okne; základná miera = Q / výroba v hodinách mimo okien.
- lift = miera v okne / základná miera; extra = Q v okne − základná miera × výroba v okne.
- Väzba: support ≥ 3, Q v okne ≥ 3 ks, lift ≥ 2,0 (`LinkSettings`).
- Istota: high (extra ≥ 10 a support ≥ 5), medium (extra ≥ 3), inak low.
- Žiadna výroba v okne alebo mimo okien, alebo základná miera 0 → lift `None`, extra 0, istota low,
  `insufficient_data` (D10).
- Súhrnný vplyv = stratené kusy ST + extra zmätky Q (do skóre rebríčka sa nepripočítava).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass, field
from typing import Literal

from oee.domain.kpi import EPS, ratio

HourKey = tuple[str, int]
LinkType = Literal["same_process", "cross_process"]
Confidence = Literal["high", "medium", "low"]
LinkStatus = Literal["link", "below_threshold", "insufficient_data"]
WINDOW = "same_hour+next_hour"


@dataclass(frozen=True)
class LinkSettings:
    min_support: int = 3
    min_q_in_window: int = 3
    min_lift: float = 2.0
    high_extra: float = 10.0
    high_support: int = 5
    medium_extra: float = 3.0


@dataclass(frozen=True)
class HourObs:
    shift_id: str
    hour_no: int
    produced: int
    defects: Mapping[str, int] = field(default_factory=dict)
    """Kód zmätku → kusy v tejto hodine."""


@dataclass(frozen=True)
class StopEvent:
    """Udalosť prestoja (koreň); `hour_nos` = hodiny všetkých jej segmentov v zmene."""

    event_id: str
    code: str
    shift_id: str
    hour_nos: tuple[int, ...]
    """Hodiny koreňa aj pokračovaní — všetky v tej istej zmene."""

    def __post_init__(self) -> None:
        if not self.hour_nos:
            raise ValueError(f"stop event {self.event_id!r} has no hour")


@dataclass(frozen=True)
class PairResult:
    cause: str
    effect: str
    support: int
    q_in_window: int
    produced_in_window: int
    rate_in_window: float | None
    base_rate: float | None
    lift: float | None
    extra_rejects: float
    link_type: LinkType
    process: str | None
    confidence: Confidence
    combined_impact_pcs: float
    status: LinkStatus
    evidence: tuple[str, ...]
    window: str = WINDOW

    @property
    def is_link(self) -> bool:
        return self.status == "link"


def _windows(events: Sequence[StopEvent], observed: Set[HourKey]) -> dict[str, set[HourKey]]:
    by_code: dict[str, set[HourKey]] = defaultdict(set)
    for e in events:
        hours = {*e.hour_nos, max(e.hour_nos) + 1}  # + nasledujúca hodina tej istej zmeny
        by_code[e.code] |= {(e.shift_id, h) for h in hours if (e.shift_id, h) in observed}
    return by_code


def _confidence(extra: float, support: int, s: LinkSettings) -> Confidence:
    if extra >= s.high_extra - EPS and support >= s.high_support:
        return "high"
    if extra >= s.medium_extra - EPS:
        return "medium"
    return "low"


def find_problem_links(
    hours: Sequence[HourObs],
    events: Sequence[StopEvent],
    *,
    stop_codes: Set[str],
    defect_codes: Set[str],
    same_process: Mapping[tuple[str, str], str],
    stop_lost_pcs: Mapping[str, float],
    settings: LinkSettings | None = None,
) -> list[PairResult]:
    """Štatistika pre každý pár (aktívny ST s aspoň jednou udalosťou) × (aktívny Q).

    Poradie: väzby, potom ostatné; v skupine same_process pred cross_process, potom lift ↓, kód.
    """
    s = settings or LinkSettings()
    by_key = {(h.shift_id, h.hour_no): h for h in hours}
    if len(by_key) != len(hours):
        raise ValueError("duplicate (shift_id, hour_no) in hours")
    stop_events = [e for e in events if e.code in stop_codes]
    windows = _windows(stop_events, set(by_key))
    support: dict[str, list[str]] = defaultdict(list)
    for e in stop_events:
        support[e.code].append(e.event_id)
    total_produced = sum(h.produced for h in hours)
    total_q = {q: sum(h.defects.get(q, 0) for h in hours) for q in defect_codes}

    results: list[PairResult] = []
    for stop in sorted(support):
        window = windows[stop]
        produced_in = sum(by_key[k].produced for k in window)
        produced_out = total_produced - produced_in
        for defect in sorted(defect_codes):
            q_in = sum(by_key[k].defects.get(defect, 0) for k in window)
            rate_in = ratio(q_in, produced_in)
            base = ratio(total_q[defect] - q_in, produced_out)
            lift = ratio(rate_in, base) if rate_in is not None and base is not None else None
            n = len(support[stop])
            extra = 0.0 if lift is None else q_in - (base or 0.0) * produced_in
            if lift is None:
                status: LinkStatus = "insufficient_data"
            elif n >= s.min_support and q_in >= s.min_q_in_window and lift >= s.min_lift - EPS:
                status = "link"
            else:
                status = "below_threshold"
            process = same_process.get((stop, defect))
            results.append(
                PairResult(
                    cause=stop,
                    effect=defect,
                    support=n,
                    q_in_window=q_in,
                    produced_in_window=produced_in,
                    rate_in_window=rate_in,
                    base_rate=base,
                    lift=lift,
                    extra_rejects=extra,
                    link_type="same_process" if process else "cross_process",
                    process=process,
                    confidence=_confidence(extra, n, s),
                    combined_impact_pcs=stop_lost_pcs.get(stop, 0.0) + extra,
                    status=status,
                    evidence=tuple(support[stop]),
                )
            )
    results.sort(
        key=lambda r: (not r.is_link, r.link_type != "same_process", -(r.lift or 0.0), r.cause, r.effect)
    )
    return results

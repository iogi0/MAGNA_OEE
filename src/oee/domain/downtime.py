"""Evidencia prestojov — koľko minút udalostí sa započíta do strát D (TASK §3.4 pravidlá 2–4).

Pravidlá:
- **Prekryv = jedna zastávka.** Udalosti s časom začiatku sa v hodine zjednocujú (počíta sa zjednotenie
  intervalov, nie súčet). Prekryté minúty patria udalosti, ktorá začala skôr (pri rovnakom začiatku tej,
  ktorá je vo vstupe skôr), takže súčet minút udalostí = zjednotenie.
- **AM a prestávka nie sú plánovaný čas** — ich okná (`HourSlot.allowance_windows`) sa z intervalov odčítajú.
- **Interval sa oreže na svoj slot.** Čas za koncom hodiny patrí segmentu-pokračovaniu v ďalšej hodine.
- **Bez času začiatku:** udalosti v poradí vstupu zaberajú zvyšok plánovaných minút hodiny; spolu s časovanými
  udalosťami nikdy neprekročia plánované minúty hodiny.
- **Pokračovanie** (`continues_event_id`): minúty sa počítajú v každej hodine raz, vo frekvencii sa počíta iba
  koreňová udalosť. Odkaz na neznámu udalosť (napr. zmazanú) = samostatná udalosť; cyklus nespôsobí pád.

Počet nahlásených udalostí sa prekryvom nemení (prekryv zachytí validácia V7, TASK §5.5).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from oee.domain.shift_model import HourSlot, ShiftPlan

Interval = tuple[datetime, datetime]


@dataclass(frozen=True)
class DowntimeEvent:
    """Nahlásená udalosť (segment) prestoja v jednej hodine zmeny."""

    event_id: str
    hour_no: int
    duration_min: float
    start: datetime | None = None
    continues_event_id: str | None = None


@dataclass(frozen=True)
class CountedSegment:
    event_id: str
    root_id: str
    hour_no: int
    counted_min: float


@dataclass(frozen=True)
class HourDowntime:
    hour_no: int
    planned_min: int
    downtime_min: float


@dataclass(frozen=True)
class DowntimeSummary:
    segments: tuple[CountedSegment, ...]
    """Segmenty v poradí vstupu."""
    hours: tuple[HourDowntime, ...]
    """Všetky hodiny zmeny v poradí (aj bez udalostí)."""
    total_min: float
    event_count: int
    """Počet udalostí vo frekvencii — pokračovania sa nepočítajú."""


# --- intervaly ----------------------------------------------------------------------------------


def _reported_min(event: DowntimeEvent) -> float:
    """Nahlásené trvanie; nekladné alebo nekonečné/NaN = 0 (chybu hlási validácia V4)."""
    d = event.duration_min
    return d if math.isfinite(d) and d > 0 else 0.0


def _minutes(delta: timedelta) -> float:
    return delta.total_seconds() / 60


def _add(merged: list[Interval], new: Interval) -> list[Interval]:
    """Pridá interval do zoradeného zoznamu disjunktných intervalov a zlúči ich."""
    result: list[Interval] = []
    for cur in sorted([*merged, new]):
        if result and cur[0] <= result[-1][1]:
            result[-1] = (result[-1][0], max(result[-1][1], cur[1]))
        else:
            result.append(cur)
    return result


def _uncovered_min(interval: Interval, covered: list[Interval]) -> float:
    start, end = interval
    if end <= start:
        return 0.0
    overlap = sum(
        _minutes(min(end, c_end) - max(start, c_start))
        for c_start, c_end in covered
        if c_start < end and start < c_end
    )
    return _minutes(end - start) - overlap


# --- koreň pokračovaní --------------------------------------------------------------------------


def _root_ids(events: Sequence[DowntimeEvent]) -> dict[str, str]:
    parent = {e.event_id: e.continues_event_id for e in events}
    roots: dict[str, str] = {}
    for event in events:
        path = [event.event_id]
        nxt = parent[event.event_id]
        while nxt is not None and nxt in parent and nxt not in path:
            path.append(nxt)
            nxt = parent[nxt]
        if nxt is not None and nxt in path:  # cyklus: deterministický koreň = najmenšie id v cykle
            roots[event.event_id] = min(path[path.index(nxt) :])
        else:
            roots[event.event_id] = path[-1]
    return roots


# --- výpočet ------------------------------------------------------------------------------------


def _count_hour(slot: HourSlot, events: list[tuple[int, DowntimeEvent]]) -> dict[int, float]:
    """Započítané minúty udalostí jednej hodiny podľa indexu vo vstupe."""
    counted: dict[int, float] = {}
    covered: list[Interval] = []
    for window in slot.allowance_windows:
        covered = _add(covered, window)

    timed = sorted(((i, e) for i, e in events if e.start is not None), key=lambda p: (p[1].start, p[0]))
    timed_total = 0.0
    for i, e in timed:
        assert e.start is not None
        start = max(e.start, slot.start)
        end = min(e.start + timedelta(minutes=_reported_min(e)), slot.end)
        if end <= start:
            counted[i] = 0.0
            continue
        counted[i] = _uncovered_min((start, end), covered)
        timed_total += counted[i]
        covered = _add(covered, (start, end))

    remaining = max(slot.planned_min - timed_total, 0.0)
    for i, e in events:
        if e.start is None:
            counted[i] = min(_reported_min(e), remaining)
            remaining -= counted[i]
    return counted


def count_downtime(plan: ShiftPlan, events: Sequence[DowntimeEvent]) -> DowntimeSummary:
    """Započítané minúty prestojov zmeny podľa segmentov a hodín.

    Raises:
        ValueError: udalosť má hodinu mimo zmeny alebo sa `event_id` opakuje (chyba volajúceho).
    """
    slots = {s.hour_no: s for s in plan.slots}
    seen: set[str] = set()
    for e in events:
        if e.hour_no not in slots:
            raise ValueError(f"event {e.event_id!r}: hour {e.hour_no} is outside the shift (1–{len(slots)})")
        if e.event_id in seen:
            raise ValueError(f"duplicate event_id {e.event_id!r}")
        seen.add(e.event_id)

    by_hour: dict[int, list[tuple[int, DowntimeEvent]]] = {}
    for i, e in enumerate(events):
        by_hour.setdefault(e.hour_no, []).append((i, e))

    counted: dict[int, float] = {}
    hours: list[HourDowntime] = []
    for slot in plan.slots:
        hour_counted = _count_hour(slot, by_hour.get(slot.hour_no, []))
        counted.update(hour_counted)
        hours.append(HourDowntime(slot.hour_no, slot.planned_min, sum(hour_counted.values())))

    roots = _root_ids(events)
    segments = tuple(
        CountedSegment(e.event_id, roots[e.event_id], e.hour_no, counted[i]) for i, e in enumerate(events)
    )
    return DowntimeSummary(
        segments=segments,
        hours=tuple(hours),
        total_min=sum(h.downtime_min for h in hours),
        event_count=len(set(roots.values())),
    )

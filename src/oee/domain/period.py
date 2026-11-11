"""Pravidlá obdobia (TASK §3.3, §8.2–8.4, PLANNING D8).

- Cieľ OEE obdobia = Σ (target × cieľ) / Σ target — zmeny môžu mať rôzne snapshoty modelu.
- First-pass quality = (Good − retesty) / Produced, iba ak sú retesty zadané pre všetky hodiny.
- Úplný týždeň = každý pracovný deň (zo snapshotov) v tom ISO týždni leží v období a má dokončenú zmenu.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence, Set
from dataclasses import dataclass
from datetime import date, timedelta

from oee.domain.kpi import ratio


def period_goal(target_and_goal: Iterable[tuple[float, float]]) -> float | None:
    pairs = list(target_and_goal)
    return ratio(sum(t * g for t, g in pairs), sum(t for t, _ in pairs))


def first_pass_quality(*, good: int, produced: int, retests: Iterable[int | None]) -> float | None:
    values = list(retests)
    if not values or any(r is None for r in values):
        return None
    return ratio(good - sum(r or 0 for r in values), produced)


def is_week_complete(*, done: Set[date], working_days: Set[int], start: date, end: date) -> bool:
    """`done` = dni s dokončenou zmenou v jednom ISO týždni; `working_days` = 0 (Po) … 6 (Ne)."""
    if not done:
        raise ValueError("a week needs at least one completed shift")
    first = min(done)
    monday = first - timedelta(days=first.weekday())
    required = [monday + timedelta(days=d) for d in sorted(working_days)]
    return all(start <= d <= end and d in done for d in required)


# --- Top-10 podľa frekvencie (PLANNING D15) --------------------------------------------------------


@dataclass(frozen=True)
class TopItem:
    code: str
    events: int
    """Počet výskytov (udalosti prestoja / záznamy zmätkov)."""
    measure: float
    """Druhé kritérium: minúty prestoja alebo kusy zmätkov."""


def top_by_frequency(
    counts: Mapping[str, tuple[int, float]], starting: Sequence[str], *, size: int
) -> list[TopItem]:
    """Najčastejšie kódy obdobia: výskyty ↓, potom `measure` ↓, potom kód.

    Ak je kódov s výskytom menej ako `size`, doplnia sa kódy štartovacieho zoznamu (TASK §5.4) s nulami
    v jeho poradí — bez dát je Top-10 štartovací zoznam s nulovými hodnotami.
    """
    ranked = sorted(
        (TopItem(code, events, measure) for code, (events, measure) in counts.items() if events > 0),
        key=lambda t: (-t.events, -t.measure, t.code),
    )[:size]
    present = {t.code for t in ranked}
    fill = [TopItem(code, 0, 0.0) for code in starting if code not in present]
    return ranked + fill[: size - len(ranked)]


# --- straty podľa kategórie (TASK §8.3) ------------------------------------------------------------


@dataclass(frozen=True)
class CategoryTotal:
    category: str
    events: int
    minutes: float
    pcs: float


def losses_by_category(rows: Iterable[tuple[str, int, float, float]]) -> list[CategoryTotal]:
    """Súčty (kategória, udalosti, minúty, kusy) po kategóriách; poradie: kusy ↓, potom názov."""
    acc: dict[str, list[float]] = {}
    for category, events, minutes, pcs in rows:
        total = acc.setdefault(category, [0, 0.0, 0.0])
        total[0] += events
        total[1] += minutes
        total[2] += pcs
    order = sorted(acc, key=lambda c: (-acc[c][2], c))
    return [CategoryTotal(c, int(acc[c][0]), acc[c][1], acc[c][2]) for c in order]

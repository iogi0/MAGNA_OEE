"""Pravidlá obdobia (TASK §3.3, §8.2–8.4, PLANNING D8).

- Cieľ OEE obdobia = Σ (target × cieľ) / Σ target — zmeny môžu mať rôzne snapshoty modelu.
- First-pass quality = (Good − retesty) / Produced, iba ak sú retesty zadané pre všetky hodiny.
- Úplný týždeň = každý pracovný deň (zo snapshotov) v tom ISO týždni leží v období a má dokončenú zmenu.
"""

from __future__ import annotations

from collections.abc import Iterable, Set
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

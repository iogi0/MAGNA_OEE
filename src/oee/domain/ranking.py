"""Rebríček problémov (TASK §8.4, PLANNING D10).

Hodnotí sa **jediná metrika vplyvu = stratené kusy kaskády** (prestoj: započítané min × 60 / takt;
zmätok: kusy). Prestoje a zmätky sú v jednom rebríčku.

Poradie:
1. trieda ABC podľa kumulatívneho podielu **pred** položkou (A < 80 %, B < 95 %, inak C);
2. eskalácia: trend `up` a podiel na vplyve zaznamenaných problémov ≥ 5 % → o triedu vyššie;
3. v triede: kusy ↓ → frekvencia ↓ → novší posledný výskyt → kód ↑.

Trend: kusy na zmenu v novšej vs staršej polovici **úplných** týždňov (nepárny počet → stredný sa vynechá);
`up` ≥ +20 %, `down` ≤ −20 %, inak `stable`; `n/a` pri < 2 úplných týždňoch alebo < 3 udalostiach
(pri zmätkoch záznamoch) spolu v oboch polovičkách. Trend `n/a` rebríček neovplyvní.
Všetky prahy sú nastavenia (`RankingSettings`).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from oee.domain.kpi import EPS, ratio

Kind = Literal["downtime", "quality"]
AbcClass = Literal["A", "B", "C"]
Trend = Literal["up", "down", "stable", "n/a"]
_CLASSES: tuple[AbcClass, ...] = ("A", "B", "C")


@dataclass(frozen=True)
class RankingSettings:
    class_a_share: float = 0.80
    class_b_share: float = 0.95
    trend_change: float = 0.20
    escalation_share: float = 0.05
    min_trend_events: int = 3
    min_complete_weeks: int = 2


@dataclass(frozen=True)
class WeekInfo:
    key: str
    complete: bool
    """Každý pracovný deň zo snapshotov má dokončenú zmenu (určuje P0-13)."""
    shifts: int


@dataclass(frozen=True)
class ProblemStats:
    code: str
    kind: Kind
    lost_pcs: float
    frequency: int
    """Počet udalostí (prestoj) alebo záznamov (zmätok)."""
    last_occurrence: date | None
    weekly: Mapping[str, tuple[float, int]] = field(default_factory=dict)
    """Týždeň → (stratené kusy, frekvencia)."""


@dataclass(frozen=True)
class RankedProblem:
    rank: int
    code: str
    kind: Kind
    abc_class: AbcClass
    base_class: AbcClass
    escalated: bool
    lost_pcs: float
    frequency: int
    last_occurrence: date | None
    share_of_recorded: float | None
    share_of_all_losses: float | None
    kpi: Literal["availability", "quality"]
    kpi_impact_pp: float | None
    trend: Trend
    trend_change: float | None


def _trend(
    problem: ProblemStats, weeks: Sequence[WeekInfo], s: RankingSettings
) -> tuple[Trend, float | None]:
    complete = [w for w in weeks if w.complete]
    if len(complete) < s.min_complete_weeks:
        return "n/a", None
    half = len(complete) // 2
    if half == 0:
        return "n/a", None
    older, newer = complete[:half], complete[-half:]

    def per_shift(part: Sequence[WeekInfo]) -> tuple[float, int, int]:
        lost = sum(problem.weekly.get(w.key, (0.0, 0))[0] for w in part)
        events = sum(problem.weekly.get(w.key, (0.0, 0))[1] for w in part)
        return lost, events, sum(w.shifts for w in part)

    old_lost, old_events, old_shifts = per_shift(older)
    new_lost, new_events, new_shifts = per_shift(newer)
    if old_events + new_events < s.min_trend_events or old_shifts == 0 or new_shifts == 0:
        return "n/a", None
    old_rate, new_rate = old_lost / old_shifts, new_lost / new_shifts
    if old_rate <= EPS:
        return ("up", None) if new_rate > EPS else ("stable", 0.0)
    change = (new_rate - old_rate) / old_rate
    if change >= s.trend_change - EPS:
        return "up", change
    if change <= -s.trend_change + EPS:
        return "down", change
    return "stable", change


def _tie_key(p: ProblemStats) -> tuple[float, int, int, str]:
    last = -p.last_occurrence.toordinal() if p.last_occurrence else 1
    return (-p.lost_pcs, -p.frequency, last, p.code)


def rank_problems(
    problems: Sequence[ProblemStats],
    weeks: Sequence[WeekInfo],
    *,
    period_target: float,
    all_losses: float,
    settings: RankingSettings | None = None,
) -> list[RankedProblem]:
    """Zoradený rebríček. `period_target` = C obdobia, `all_losses` = C − G obdobia (vrátane speed loss).

    `weeks` musia byť zoradené chronologicky (staršie → novšie).
    """
    s = settings or RankingSettings()
    recorded = sum(p.lost_pcs for p in problems)
    rows: list[tuple[int, tuple[float, int, int, str], RankedProblem]] = []
    cumulative = 0.0
    for p in sorted(problems, key=_tie_key):
        share = ratio(p.lost_pcs, recorded)
        before = cumulative
        cumulative += share or 0.0
        base: AbcClass = (
            "A" if before < s.class_a_share - EPS else "B" if before < s.class_b_share - EPS else "C"
        )
        trend, change = _trend(p, weeks, s)
        escalate = trend == "up" and share is not None and share >= s.escalation_share - EPS and base != "A"
        final = _CLASSES[_CLASSES.index(base) - 1] if escalate else base
        impact = ratio(p.lost_pcs, period_target)
        row = RankedProblem(
            rank=0,
            code=p.code,
            kind=p.kind,
            abc_class=final,
            base_class=base,
            escalated=escalate,
            lost_pcs=p.lost_pcs,
            frequency=p.frequency,
            last_occurrence=p.last_occurrence,
            share_of_recorded=share,
            share_of_all_losses=ratio(p.lost_pcs, all_losses),
            kpi="availability" if p.kind == "downtime" else "quality",
            kpi_impact_pp=None if impact is None else impact * 100,
            trend=trend,
            trend_change=change,
        )
        rows.append((_CLASSES.index(final), _tie_key(p), row))
    rows.sort(key=lambda r: (r[0], r[1]))
    return [RankedProblem(**{**vars(r), "rank": i}) for i, (_, _, r) in enumerate(rows, start=1)]

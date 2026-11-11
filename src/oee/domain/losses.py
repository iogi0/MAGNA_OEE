"""Straty v kusoch, príznaky a stav cieľa (TASK §6.5, §6.6, §7C, §7E).

- Pareto zjednotených vedier v kusoch kaskády: kódy prestojov (D), `unattributed_speed_loss` (S),
  kódy zmätkov a `unspecified_defect` (R). Σ vedier = C − G (aj pri zápornej S, ktorá sa preto neskrýva).
- Príznak hodiny `downtime_ge_5_min` (§7C: ≥ 5 min); príznak udalosti `over_5_min` podľa trvania
  celej zastávky (koreň + pokračovania, §6.6: > 5 min).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from oee.domain.kpi import EPS, Cascade, ratio

HOUR_DOWNTIME_FLAG_MIN = 5  # TASK §7C: hodina s prestojom ≥ 5 min
EVENT_FLAG_MIN = 5  # TASK §6.6: každá zastávka > 5 min
UNATTRIBUTED = "unattributed_speed_loss"
UNSPECIFIED = "unspecified_defect"

GoalStatus = Literal["goal_met", "below_goal"]
BucketKind = Literal["downtime", "quality"]


@dataclass(frozen=True)
class LossBucket:
    bucket: str
    kind: BucketKind | None
    """None = nepriradená strata rýchlosti."""
    pcs: float
    share_of_losses: float | None
    category: str | None = None


def goal_status(oee: float | None, target_oee: float) -> GoalStatus | None:
    if oee is None:
        return None
    return "goal_met" if oee >= target_oee else "below_goal"


def hour_flags(cascade: Cascade, *, goal: float) -> tuple[str, ...]:
    flags: list[str] = []
    if goal_status(cascade.oee, goal) == "below_goal":
        flags.append("below_goal")
    if cascade.downtime_min >= HOUR_DOWNTIME_FLAG_MIN:
        flags.append("downtime_ge_5_min")
    return tuple(flags)


def event_flags(*, stop_duration_min: float, is_continuation: bool) -> tuple[str, ...]:
    flags: list[str] = []
    if stop_duration_min > EVENT_FLAG_MIN:
        flags.append("over_5_min")
    if is_continuation:
        flags.append("continuation")
    return tuple(flags)


def loss_pareto(
    total: Cascade,
    *,
    stop_pcs: Mapping[str, float],
    defect_qty: Mapping[str | None, int],
    stop_category: Mapping[str, str] | None = None,
    defect_category: Mapping[str, str] | None = None,
) -> list[LossBucket]:
    """Vedrá strát zoradené podľa kusov ↓, potom kódu. `defect_qty[None]` = zmätky bez rozpisu."""
    stop_category = stop_category or {}
    defect_category = defect_category or {}
    losses = total.target - total.good
    items: list[tuple[str, BucketKind | None, float, str | None]] = [
        (code, "downtime", pcs, stop_category.get(code)) for code, pcs in stop_pcs.items() if pcs > EPS
    ]
    if abs(total.speed_loss) > EPS:
        items.append((UNATTRIBUTED, None, total.speed_loss, None))
    items += [
        (code or UNSPECIFIED, "quality", float(qty), defect_category.get(code) if code else None)
        for code, qty in defect_qty.items()
        if qty > 0
    ]
    items.sort(key=lambda b: (-b[2], b[0]))
    return [LossBucket(name, kind, pcs, ratio(pcs, losses), category) for name, kind, pcs, category in items]


def group_by_category(buckets: Sequence[LossBucket]) -> list[LossBucket]:
    """Pareto podľa kategórie (prepínač „typ / kategória", TASK §7E): súčet kusov a podielov.

    Vedro bez kategórie (nepriradená strata rýchlosti, zmätky bez rozpisu) zostane samostatné.
    Kategória môže obsahovať prestoje aj zmätky, preto má `kind` None. Poradie: kusy ↓, potom názov.
    """
    pcs: dict[str, float] = {}
    share: dict[str, float | None] = {}
    category: dict[str, str | None] = {}
    kind: dict[str, BucketKind | None] = {}
    for b in buckets:
        key = b.category or b.bucket
        if key not in pcs:
            pcs[key], share[key], category[key] = 0.0, 0.0, b.category
            kind[key] = None if b.category else b.kind
        pcs[key] += b.pcs
        previous = share[key]
        share[key] = None if previous is None or b.share_of_losses is None else previous + b.share_of_losses
    order = sorted(pcs, key=lambda k: (-pcs[k], k))
    return [LossBucket(k, kind[k], pcs[k], share[k], category[k]) for k in order]

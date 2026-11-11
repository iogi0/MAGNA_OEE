"""Kaskáda strát a 4 KPI (TASK §3.3–3.4, PLANNING D12).

Každý kus targetu padne do práve jedného vedra:

    C  target               = planned_min × 60 / ideal_cycle_s
    D  technical losses     = downtime_min × 60 / ideal_cycle_s        → Availability
       possible in run time = C − D
    S  speed loss           = (C − D) − Produced   (zvyšok)            → Performance
    R  quality loss         = Rejects                                  → Quality
    G  good                 = Produced − Rejects

Identita C − D − S − R = G platí presne pre hodinu, zmenu aj obdobie.

KPI sa počítajú v kusoch (D12):

    A = (C − D) / C      P = Produced / (C − D)      Q = G / Produced      OEE = G / C = A × P × Q

Pri jednom takte je to presne `Run / Plan` a `ideal time / run time` z TASK §3.3; pri období zo zmien
s rôznym taktom (rôzne snapshoty, D8) iba táto forma zachová A × P × Q = OEE.

**Agregácia iba cez súčty primárnych veličín** (`+`, `sum_cascades`) — nikdy priemer percent.
Zaokrúhľuje sa až pri prezentácii.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass, fields

SECONDS_PER_MINUTE = 60
EPS = 1e-9
"""Pod touto hodnotou je menovateľ (kusy, minúty) prakticky nulový."""


def ratio(numerator: float, denominator: float) -> float | None:
    """Podiel; None, ak menovateľ nie je kladný (nedefinované)."""
    return numerator / denominator if denominator > EPS else None


@dataclass(frozen=True)
class Cascade:
    """Primárne (sčítateľné) veličiny kaskády; všetko ostatné je odvodené."""

    planned_min: float
    downtime_min: float
    target: float
    """C — target v kusoch."""
    technical_loss: float
    """D — strata prestojmi v kusoch."""
    produced: int
    rejects: int

    @classmethod
    def from_minutes(
        cls, *, planned_min: float, downtime_min: float, produced: int, rejects: int, ideal_cycle_s: float
    ) -> Cascade:
        """Kaskáda jednej hodiny / zmeny s jedným taktom (minúty → kusy cez `ideal_cycle_s`)."""
        if not (math.isfinite(ideal_cycle_s) and ideal_cycle_s > 0):
            raise ValueError(f"ideal cycle must be a positive number of seconds, got {ideal_cycle_s!r}")
        pcs_per_min = SECONDS_PER_MINUTE / ideal_cycle_s
        return cls(
            planned_min=planned_min,
            downtime_min=downtime_min,
            target=planned_min * pcs_per_min,
            technical_loss=downtime_min * pcs_per_min,
            produced=produced,
            rejects=rejects,
        )

    def __add__(self, other: Cascade) -> Cascade:
        return Cascade(*(getattr(self, f.name) + getattr(other, f.name) for f in fields(self)))

    # --- kaskáda (kusy) ---

    @property
    def run_min(self) -> float:
        return self.planned_min - self.downtime_min

    @property
    def possible_in_run(self) -> float:
        return self.target - self.technical_loss

    @property
    def speed_loss(self) -> float:
        """S — zvyšok; záporná hodnota = rozpor v dátach (validácia V3)."""
        return self.possible_in_run - self.produced

    @property
    def quality_loss(self) -> int:
        return self.rejects

    @property
    def good(self) -> int:
        return self.produced - self.rejects

    @property
    def deviation(self) -> float:
        """Good − Target = −(D + S + R)."""
        return self.good - self.target

    # --- KPI (podiely 0–1; None = nedefinované) ---

    @property
    def availability(self) -> float | None:
        return ratio(self.possible_in_run, self.target)

    @property
    def performance(self) -> float | None:
        return ratio(self.produced, self.possible_in_run)

    @property
    def quality(self) -> float | None:
        return ratio(self.good, self.produced)

    @property
    def oee(self) -> float | None:
        """Kanonický OEE = G / C (definovaný aj pri Run = 0 alebo Produced = 0)."""
        return ratio(self.good, self.target)

    def goal_gap_pp(self, target_oee: float) -> float | None:
        """Odchýlka OEE od cieľa v percentuálnych bodoch."""
        oee = self.oee
        return None if oee is None else (oee - target_oee) * 100


EMPTY_CASCADE = Cascade(planned_min=0, downtime_min=0, target=0, technical_loss=0, produced=0, rejects=0)


def sum_cascades(items: Iterable[Cascade]) -> Cascade:
    """Kaskáda obdobia = súčet primárnych veličín."""
    total = EMPTY_CASCADE
    for item in items:
        total = total + item
    return total

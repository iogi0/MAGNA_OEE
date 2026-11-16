"""Úroveň problémov stanice pre Line X-Ray (TASK §2 mapovanie, §7 straty po staniciach).

Čistá logika: z počtu záznamov prestoja a ich minút určí úroveň. Platí najvyššia splnená úroveň;
úroveň je splnená, keď počet záznamov ≥ prahu ALEBO minúty ≥ prahu (prah minút 0 = neplatí samostatne).
Prahy sú nastavenie (`catalog/stations.yaml`), nie pevné čísla v kóde.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Level = Literal["none", "low", "elevated", "high"]
LEVELS: tuple[Level, ...] = ("none", "low", "elevated", "high")


@dataclass(frozen=True)
class Threshold:
    events: int
    minutes: float


@dataclass(frozen=True)
class LevelThresholds:
    low: Threshold
    elevated: Threshold
    high: Threshold


def _meets(events: int, minutes: float, t: Threshold) -> bool:
    return (t.events > 0 and events >= t.events) or (t.minutes > 0 and minutes >= t.minutes)


def station_level(events: int, minutes: float, thresholds: LevelThresholds) -> Level:
    """Najvyššia úroveň, ktorú stanica spĺňa; bez záznamov vždy `none`."""
    if events <= 0:
        return "none"
    for name, t in (("high", thresholds.high), ("elevated", thresholds.elevated), ("low", thresholds.low)):
        if _meets(events, minutes, t):
            return name  # type: ignore[return-value]
    return "low"

"""Fakty pre lokálne AI a fallback šablóny (TASK §7.F, §8.6, §13.1, ARCHITECTURE §8).

Fakty sú jediný vstup AI: všetky čísla počíta kód (CLAUDE.md bod 1), AI ich iba formuluje a validátor overí,
že text neobsahuje iné čísla ani kódy. Podiely sú v percentách v plnej presnosti (zaokrúhľuje až text);
výstup je JSON-kompatibilný slovník (kľúč cache = `facts_hash`).
"""

from __future__ import annotations

from typing import Any

from oee.contracts.period_analytics import ProblemLink
from oee.contracts.shift_analytics import IssueRow, ShiftAnalytics

PERCENT = 100

Facts = dict[str, Any]


def _pct(share: float | None) -> float | None:
    return None if share is None else share * PERCENT


def _longest(issues: tuple[IssueRow, ...]) -> Facts | None:
    """Najdlhšia udalosť zmeny (pri zhode skoršia hodina)."""
    if not issues:
        return None
    top = max(issues, key=lambda i: (i.duration_min, -i.hour_no))
    return {
        "code": top.issue_type,
        "name": top.name,
        "category": top.category,
        "minutes": top.duration_min,
        "start": top.start_time.strftime("%H:%M") if top.start_time else None,
        "hour_no": top.hour_no,
    }


def shift_summary_facts(a: ShiftAnalytics) -> Facts:
    """Fakty Shift Summary (§7.F) — všetko zo `ShiftAnalytics`."""
    t, w, k = a.target_vs_actual, a.waterfall_pcs, a.kpi
    return {
        "shift_id": a.shift.shift_id,
        "date": a.shift.date.isoformat(),
        "weekday": a.shift.weekday,
        "line": a.shift.line,
        "provisional": a.shift.provisional,
        "hours_submitted": a.shift.hours_submitted,
        "hours_total": a.shift.hours_total,
        "oee_pct": _pct(k.oee),
        "goal_pct": _pct(a.model.target_oee),
        "gap_pp": k.oee_gap_pp,
        "oee_status": k.oee_status,
        "target_pcs": t.target_pcs,
        "produced_pcs": t.produced_pcs,
        "production_vs_target_pct": _pct(t.production_vs_target),
        "good_pcs": t.good_pcs,
        "shortfall_pcs": -t.deviation_from_target_pcs,
        "downtime_pcs": w.technical_losses,
        "downtime_min": a.technical_losses.total_min,
        "downtime_events": a.technical_losses.events,
        "speed_loss_pcs": w.speed_loss,
        "rejects_pcs": t.rejects_pcs,
        "reject_rate_pct": _pct(a.quality.reject_rate),
        "longest": _longest(a.issues),
    }


def link_facts(link: ProblemLink, *, cause_name: str, effect_name: str) -> Facts:
    """Fakty vysvetlenia väzby §8.6 (korelácia, nie dokázaná príčina)."""
    return {
        "cause": link.cause,
        "cause_name": cause_name,
        "effect": link.effect,
        "effect_name": effect_name,
        "window": link.window,
        "support": link.support,
        "q_in_window": link.q_in_window,
        "produced_in_window": link.produced_in_window,
        "rate_in_window_pct": _pct(link.rate_in_window),
        "base_rate_pct": _pct(link.base_rate),
        "lift": link.lift,
        "extra_rejects": link.extra_rejects,
        "link_type": link.link_type,
        "process": link.process,
        "confidence": link.confidence,
        "cause_lost_pcs": link.combined_impact_pcs - link.extra_rejects,
        "combined_impact_pcs": link.combined_impact_pcs,
    }

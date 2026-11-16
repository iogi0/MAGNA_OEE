"""Production History (TASK §8.1–8.3, PLANNING D15) nad hotovou analytikou.

- Shift History: jeden riadok na zmenu z `build_shift` (stav dát + stav voči cieľu OEE).
- Týždeň (ISO) a mesiac: `build_period` + Top-10 najčastejších problémov (`domain.period.top_by_frequency`).
Žiadne KPI sa tu nepočítajú — iba výber období, poradie a zobrazenie hotových čísel.
"""

from __future__ import annotations

import calendar
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from oee.catalog.loader import Catalog
from oee.contracts.period_analytics import PeriodAnalytics, RankingRow
from oee.contracts.shift_analytics import ShiftAnalytics
from oee.domain.kpi import ratio
from oee.domain.period import CategoryTotal, TopItem, losses_by_category, top_by_frequency
from oee.persistence.models import Shift
from oee.services.analytics import build_shift
from oee.services.codebook import list_codes
from oee.services.reporting import effective_status
from oee.services.shift_view import status_label

TOP_SIZE = 10  # D15: Top-10 najčastejších ST a Q
WEEK_PATTERN = re.compile(r"^(\d{4})-W(\d{2})$")
MONTH_PATTERN = re.compile(r"^(\d{4})-(\d{2})$")


class PeriodError(ValueError):
    """Neplatné obdobie (formát týždňa / mesiaca, začiatok po konci)."""


@dataclass(frozen=True)
class HistoryRow:
    analytics: ShiftAnalytics
    status: str
    """Stav dát (completed / in_progress n/N — provisional / incomplete / edited)."""


@dataclass(frozen=True)
class TopRow:
    rank: int
    code: str
    name: str
    category: str
    events: int
    measure: float
    max_events: int
    """Najväčší počet výskytov v rebríčku — maximum pre ukazovateľ (0 → prázdny ukazovateľ)."""


# --- obdobia -------------------------------------------------------------------------------------


def parse_week(value: str) -> tuple[date, date]:
    """„2026-W48" → pondelok – nedeľa ISO týždňa."""
    m = WEEK_PATTERN.match(value)
    if not m:
        raise PeriodError("week must look like 2026-W48")
    try:
        start = date.fromisocalendar(int(m.group(1)), int(m.group(2)), 1)
    except ValueError as exc:
        raise PeriodError(f"invalid ISO week {value}") from exc
    return start, start + timedelta(days=6)


def parse_month(value: str) -> tuple[date, date]:
    """„2026-11" → prvý – posledný deň mesiaca."""
    m = MONTH_PATTERN.match(value)
    if not m or not 1 <= int(m.group(2)) <= 12:
        raise PeriodError("month must look like 2026-11")
    year, month = int(m.group(1)), int(m.group(2))
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def week_key(day: date) -> str:
    iso = day.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def month_key(day: date) -> str:
    return f"{day:%Y-%m}"


def latest_shift_date(session: Session, *, line: str) -> date | None:
    return session.scalar(
        select(Shift.date).where(Shift.line_id == line).order_by(Shift.date.desc()).limit(1)
    )


# --- Shift History (§8.1) ------------------------------------------------------------------------


def shift_history(
    session: Session,
    start: date,
    end: date,
    *,
    line: str,
    catalog: Catalog,
    now: datetime,
    now_local: datetime,
) -> list[HistoryRow]:
    """Zmeny linky v dňoch `start`–`end` (vrátane) v poradí dátumu, každá s analytikou zmeny."""
    if start > end:
        raise PeriodError("start must not be after end")
    shifts = session.scalars(
        select(Shift)
        .where(Shift.line_id == line, Shift.date >= start, Shift.date <= end)
        .order_by(Shift.date, Shift.shift_id)
    ).all()
    rows = []
    for shift in shifts:
        analytics = build_shift(session, shift.shift_id, catalog=catalog, now=now)
        rows.append(
            HistoryRow(analytics, status_label(analytics, effective_status(shift, now_local=now_local)))
        )
    return rows


# --- Top-10 (D15) a straty podľa kategórie (§8.3) -------------------------------------------------


def _top_rows(items: Sequence[TopItem], names: dict[str, tuple[str, str]]) -> list[TopRow]:
    max_events = max((t.events for t in items), default=0)
    return [
        TopRow(i, t.code, *names.get(t.code, (t.code, "")), t.events, t.measure, max_events)
        for i, t in enumerate(items, start=1)
    ]


def top10(session: Session, period: PeriodAnalytics, catalog: Catalog) -> tuple[list[TopRow], list[TopRow]]:
    """Top-10 najčastejších prestojov a zmätkov obdobia (D15); bez dát štartovací zoznam s nulami."""
    stops, defects = list_codes(session)
    names = {c.code: (c.name_en, catalog.categories.get(c.category, c.category)) for c in [*stops, *defects]}
    stop_items = top_by_frequency(
        {s.code: (s.events, s.total_min) for s in period.issue_stats}, catalog.top10_stop, size=TOP_SIZE
    )
    defect_items = top_by_frequency(
        {d.code: (d.records, float(d.qty)) for d in period.defect_stats}, catalog.top10_defect, size=TOP_SIZE
    )
    return _top_rows(stop_items, names), _top_rows(defect_items, names)


def category_losses(period: PeriodAnalytics) -> list[CategoryTotal]:
    """Technické straty obdobia podľa kategórie (súčty z `issue_stats`)."""
    return losses_by_category((s.category, s.events, s.total_min, s.lost_pcs) for s in period.issue_stats)


def series_payload(period: PeriodAnalytics) -> dict[str, object]:
    """Dáta grafov obdobia (OEE po zmenách s cieľom, trend A/P/Q po týždňoch) — priamo z `PeriodAnalytics`."""
    return {
        "goal": ratio(
            period.totals.oee_goal_pcs, period.totals.target_pcs
        ),  # cieľ obdobia = Σ cieľ / Σ target
        "shifts": [
            {"label": f"{s.date:%d.%m.}", "shift_id": s.shift_id, "oee": s.oee, "status": s.status}
            for s in period.shift_series
        ],
        "weeks": [
            {
                "label": f"W{w.iso_week}" + (" (partial)" if w.partial else ""),
                "oee": w.oee,
                "availability": w.availability,
                "performance": w.performance,
                "quality": w.quality,
            }
            for w in period.weekly
        ],
    }


def neighbour_periods(kind: str, start: date, end: date) -> tuple[str, str]:
    """Kľúče predchádzajúceho a nasledujúceho týždňa / mesiaca (navigácia ‹ ›)."""
    if kind == "week":
        return week_key(start - timedelta(days=7)), week_key(start + timedelta(days=7))
    return month_key(start - timedelta(days=1)), month_key(end + timedelta(days=1))


# --- Problem Ranking a Problem Links (§8.4, §8.6) -----------------------------------------------

TREND_ARROWS = {"up": "↑", "down": "↓", "stable": "→", "n/a": "—"}


@dataclass(frozen=True)
class LinkedItem:
    code: str
    """Druhá strana väzby (pri prestoji zmätok, pri zmätku prestoj)."""
    combined_impact_pcs: float
    confidence: str


@dataclass(frozen=True)
class RankingView:
    row: RankingRow
    linked: tuple[LinkedItem, ...]
    """Väzby §8.6 — iba informácia, neovplyvňujú poradie ani triedu rebríčka."""


def ranking_view(period: PeriodAnalytics) -> list[RankingView]:
    out = []
    for row in period.problem_ranking:
        if row.kind == "downtime":
            linked = [
                LinkedItem(x.effect, x.combined_impact_pcs, x.confidence)
                for x in period.problem_links
                if x.cause == row.code
            ]
        else:
            linked = [
                LinkedItem(x.cause, x.combined_impact_pcs, x.confidence)
                for x in period.problem_links
                if x.effect == row.code
            ]
        out.append(RankingView(row, tuple(linked)))
    return out


def linked_defects_by_stop(period: PeriodAnalytics) -> dict[str, list[str]]:
    """Kód prestoja → zmätky, s ktorými má v období väzbu (odznak „linked defect" v udalostiach zmeny)."""
    linked: dict[str, list[str]] = {}
    for link in period.problem_links:
        linked.setdefault(link.cause, []).append(link.effect)
    return linked

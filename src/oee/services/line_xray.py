"""Line X-Ray: problémy po staniciach linky a intervaly prestojov po hodinách (TASK §2, §7).

- Stanica sa určí z kategórie kódu cez `catalog/stations.yaml` (predpoklad, nie fakt — TASK §2).
  Kategória na viacerých staniciach = záznam „assumed" na každej z nich.
- Záznam prestoja = koreňová udalosť (pokračovanie do ďalšej hodiny sa nepočíta druhýkrát, jeho minúty áno).
- Zmätky sa priradia rovnako podľa kategórie kódu zmätku.
- Nič sa nepočíta z KPI — iba počty a minúty zaznamenaných udalostí.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from oee.catalog.loader import Catalog, StationMap
from oee.domain.shift_model import build_shift_plan, config_from_snapshot
from oee.domain.stations import Level, station_level
from oee.persistence.models import DefectType, HourlyReportRow, IssueEvent, IssueType, QualityRecord, Shift


@dataclass
class CodeStat:
    code: str
    name: str
    events: int = 0
    minutes: float = 0.0
    qty: int = 0


@dataclass
class StationStat:
    no: int | None
    name: str
    kind: str
    events: int = 0
    minutes: float = 0.0
    assumed_events: int = 0
    defects: int = 0
    stops: dict[str, CodeStat] = field(default_factory=dict)
    rejects: dict[str, CodeStat] = field(default_factory=dict)
    level: Level = "none"

    @property
    def top_stops(self) -> list[CodeStat]:
        return sorted(self.stops.values(), key=lambda c: (-c.minutes, -c.events, c.code))

    @property
    def top_rejects(self) -> list[CodeStat]:
        return sorted(self.rejects.values(), key=lambda c: (-c.qty, c.code))


@dataclass(frozen=True)
class Segment:
    left: float
    width: float
    code: str
    start: datetime
    minutes: float
    timed: bool


@dataclass(frozen=True)
class HourStrip:
    hour_no: int
    start: datetime
    end: datetime
    reported: bool
    segments: tuple[Segment, ...]


@dataclass(frozen=True)
class LineXray:
    stations: tuple[StationStat, ...]
    off_line: tuple[StationStat, ...]
    hours: tuple[HourStrip, ...]
    """Iba pre jednu zmenu; za obdobie prázdne."""
    shifts: int
    total_events: int
    total_minutes: float


def _category(code: str, catalog: Catalog, db_categories: dict[str, str]) -> str:
    if code in catalog.top10_categories or code in catalog.codes:
        return catalog.category_of(code)
    return db_categories.get(code, "other")


def build_line_xray(
    session: Session,
    *,
    line: str,
    catalog: Catalog,
    stations: StationMap,
    shift_id: str | None = None,
    start: date | None = None,
    end: date | None = None,
) -> LineXray:
    """Problémy po staniciach za jednu zmenu (`shift_id`) alebo za dni `start`–`end` (vrátane)."""
    shift_q = select(Shift.shift_id).where(Shift.line_id == line)
    if shift_id is not None:
        shift_q = shift_q.where(Shift.shift_id == shift_id)
    if start is not None:
        shift_q = shift_q.where(Shift.date >= start)
    if end is not None:
        shift_q = shift_q.where(Shift.date <= end)
    shift_ids = list(session.scalars(shift_q))
    hours = list(session.scalars(select(HourlyReportRow).where(HourlyReportRow.shift_id.in_(shift_ids))))
    hour_ids = [h.hour_id for h in hours]
    events = list(
        session.scalars(
            select(IssueEvent).where(IssueEvent.hour_id.in_(hour_ids), IssueEvent.deleted_at.is_(None))
        )
    )
    quality = list(session.scalars(select(QualityRecord).where(QualityRecord.hour_id.in_(hour_ids))))

    names: dict[str, str] = {}
    db_categories: dict[str, str] = {}
    for model in (IssueType, DefectType):
        for code, name, category in session.execute(select(model.code, model.name_en, model.category)):
            names[code], db_categories[code] = name, category

    station_stats = {s.no: StationStat(s.no, s.name, s.kind) for s in stations.stations}
    off_stats: dict[str, StationStat] = {
        name: StationStat(None, name, "off") for name, _ in stations.off_line
    }
    fallback = stations.off_line[-1][0] if stations.off_line else None
    if fallback is None:
        off_stats["Unassigned"] = StationStat(None, "Unassigned", "off")
        fallback = "Unassigned"

    def targets(code: str) -> tuple[list[StationStat], bool]:
        category = _category(code, catalog, db_categories)
        nos = stations.stations_for(category)
        if nos:
            return [station_stats[n] for n in nos], len(nos) > 1
        return [off_stats[stations.off_line_for(category) or fallback]], False

    for e in events:
        code = e.issue_type_code
        group, assumed = targets(code)
        root = e.continues_issue_id is None
        for st in group:
            cs = st.stops.setdefault(code, CodeStat(code, e.free_text_name or names.get(code, code)))
            cs.minutes += e.duration_min
            st.minutes += e.duration_min
            if root:
                cs.events += 1
                st.events += 1
                st.assumed_events += int(assumed)
    for q in quality:
        code = q.defect_type_code or "unspecified"
        group, _ = targets(code) if q.defect_type_code else ([off_stats[fallback]], False)
        for st in group:
            cs = st.rejects.setdefault(code, CodeStat(code, names.get(code, "Unspecified defect")))
            cs.qty += q.qty
            st.defects += q.qty

    for st in [*station_stats.values(), *off_stats.values()]:
        st.level = station_level(st.events, st.minutes, stations.levels)

    strips: tuple[HourStrip, ...] = ()
    shift = session.get(Shift, shift_id) if shift_id is not None else None
    if shift is not None:
        plan = build_shift_plan(config_from_snapshot(shift.model_snapshot), shift.date)
        slots = [(s.hour_no, s.start, s.end) for s in plan.slots]
        strips = _hour_strips(slots, hours, events)
    roots = [e for e in events if e.continues_issue_id is None]
    return LineXray(
        stations=tuple(station_stats[s.no] for s in stations.stations),
        off_line=tuple(off_stats.values()),
        hours=strips,
        shifts=len(shift_ids),
        total_events=len(roots),
        total_minutes=sum(e.duration_min for e in events),
    )


def _hour_strips(
    slots: list[tuple[int, datetime, datetime]], hours: list[HourlyReportRow], events: list[IssueEvent]
) -> tuple[HourStrip, ...]:
    """Intervaly prestojov v hodinách plánu (v %). Udalosť bez času sa kreslí od začiatku hodiny."""
    by_hour: dict[str, list[IssueEvent]] = defaultdict(list)
    for e in events:
        by_hour[e.hour_id].append(e)
    rows = {h.hour_no: h for h in hours}
    strips = []
    for hour_no, slot_start, slot_end in slots:
        h = rows.get(hour_no)
        span = (slot_end - slot_start).total_seconds() or 1.0
        segments = []
        for e in sorted(by_hour[h.hour_id] if h else [], key=lambda x: x.start_at or slot_start):
            begin = e.start_at or slot_start
            finish = min(begin + timedelta(minutes=e.duration_min), slot_end)
            left = max(0.0, (begin - slot_start).total_seconds() / span * 100)
            width = max(0.0, (finish - begin).total_seconds() / span * 100)
            segments.append(
                Segment(
                    round(left, 2),
                    round(min(width, 100 - left), 2),
                    e.issue_type_code,
                    begin,
                    e.duration_min,
                    e.start_at is not None,
                )
            )
        reported = h is not None and h.submitted_at is not None
        strips.append(HourStrip(hour_no, slot_start, slot_end, reported, tuple(segments)))
    return tuple(strips)

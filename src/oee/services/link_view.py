"""Podklady pre záložku Problem Links (TASK §8.6): matica väzieb, vybraný pár a časová os výskytov.

Nič sa tu nepočíta nanovo — väzby (lift, okno, podpora) prichádzajú z `PeriodAnalytics.problem_links`.
Časová os zobrazuje iba zaznamenané údaje: prestoj s presným začiatkom a trvaním (koreň + pokračovania)
a zmätky po hodinách okna (čas zmätku v rámci hodiny sa nezaznamenáva).
Okno = hodina(y) prestoja + nasledujúca hodina tej istej zmeny — rovnako ako `domain.correlation`.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from oee.contracts.period_analytics import ProblemLink
from oee.persistence.models import HourlyReportRow, IssueEvent, QualityRecord, Shift


@dataclass(frozen=True)
class LinkMatrix:
    causes: tuple[str, ...]
    effects: tuple[str, ...]
    cells: dict[tuple[str, str], ProblemLink]
    selected: ProblemLink | None


def link_matrix(links: Sequence[ProblemLink], cause: str | None, effect: str | None) -> LinkMatrix:
    """Riadky = prestoje, stĺpce = zmätky (iba páry, ktoré sú väzbou).

    Bez výberu = prvá väzba (najsilnejšia)."""
    cells = {(x.cause, x.effect): x for x in links}
    selected = cells.get((cause or "", effect or "")) or (links[0] if links else None)
    return LinkMatrix(
        tuple(sorted({x.cause for x in links})), tuple(sorted({x.effect for x in links})), cells, selected
    )


@dataclass(frozen=True)
class Band:
    start: datetime
    end: datetime
    qty: int


@dataclass(frozen=True)
class Occurrence:
    """Jeden výskyt prestoja (koreň) a zmätky sledovaného typu v jeho okne."""

    shift_id: str
    day: date
    window_start: datetime
    window_end: datetime
    stop_start: datetime
    stop_end: datetime
    stop_min: float
    stop_time_known: bool
    defects: tuple[Band, ...]

    def pos(self, t: datetime) -> float:
        """Poloha času v okne v % (iba prezentácia)."""
        total = (self.window_end - self.window_start).total_seconds()
        return max(0.0, min(100.0, (t - self.window_start).total_seconds() / total * 100)) if total else 0.0

    @property
    def defects_in_stop_hour(self) -> int:
        return sum(b.qty for b in self.defects if b.start < self.stop_end and b.end > self.stop_start)

    @property
    def defect_qty(self) -> int:
        return sum(b.qty for b in self.defects)


def _root(event: IssueEvent, by_id: dict[str, IssueEvent]) -> str:
    seen: set[str] = set()
    while event.continues_issue_id and event.continues_issue_id in by_id and event.issue_id not in seen:
        seen.add(event.issue_id)
        event = by_id[event.continues_issue_id]
    return event.issue_id


def link_occurrences(session: Session, link: ProblemLink) -> list[Occurrence]:
    """Výskyty prestoja `link.cause` z `link.evidence` (koreňové udalosti) zoradené podľa času."""
    roots = set(link.evidence)
    if not roots:
        return []
    root_events = list(session.scalars(select(IssueEvent).where(IssueEvent.issue_id.in_(roots))))
    root_hours = {e.issue_id: e.hour_id for e in root_events}
    shift_ids = set(
        session.scalars(
            select(HourlyReportRow.shift_id).where(HourlyReportRow.hour_id.in_(root_hours.values()))
        )
    )
    hours = {
        h.hour_id: h
        for h in session.scalars(select(HourlyReportRow).where(HourlyReportRow.shift_id.in_(shift_ids)))
    }
    events = list(
        session.scalars(
            select(IssueEvent).where(
                IssueEvent.hour_id.in_(hours),
                IssueEvent.issue_type_code == link.cause,
                IssueEvent.deleted_at.is_(None),
            )
        )
    )
    by_id = {e.issue_id: e for e in events}
    chains: dict[str, list[IssueEvent]] = defaultdict(list)
    for e in events:
        root = _root(e, by_id)
        if root in roots:
            chains[root].append(e)
    defects: dict[str, int] = dict(
        session.execute(  # type: ignore[arg-type]
            select(QualityRecord.hour_id, func.sum(QualityRecord.qty))
            .where(QualityRecord.hour_id.in_(hours), QualityRecord.defect_type_code == link.effect)
            .group_by(QualityRecord.hour_id)
        ).all()
    )
    days = dict(
        session.execute(select(Shift.shift_id, Shift.date).where(Shift.shift_id.in_(shift_ids))).all()
    )

    result: list[Occurrence] = []
    for root_id, chain in chains.items():
        chain_hours = [hours[e.hour_id] for e in chain]
        shift_id = chain_hours[0].shift_id
        hour_nos = {h.hour_no for h in chain_hours}
        window_nos = {*hour_nos, max(hour_nos) + 1}
        window = sorted(
            (h for h in hours.values() if h.shift_id == shift_id and h.hour_no in window_nos),
            key=lambda h: h.hour_no,
        )
        root_event = by_id[root_id]
        stop_min = sum(e.duration_min for e in chain)
        known = root_event.start_at is not None
        stop_start = root_event.start_at or hours[root_event.hour_id].slot_start
        result.append(
            Occurrence(
                shift_id=shift_id,
                day=days[shift_id],
                window_start=window[0].slot_start,
                window_end=window[-1].slot_end,
                stop_start=stop_start,
                stop_end=stop_start + timedelta(minutes=stop_min),
                stop_min=stop_min,
                stop_time_known=known,
                defects=tuple(
                    Band(h.slot_start, h.slot_end, int(defects[h.hour_id]))
                    for h in window
                    if defects.get(h.hour_id)
                ),
            )
        )
    return sorted(result, key=lambda o: o.stop_start)

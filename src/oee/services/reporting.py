"""Zmena a hodinové hlásenie (TASK §4.3, §5.3–5.6, ARCHITECTURE §6.1, PLANNING D8, D10).

- Zmena sa vytvorí na zadaný dátum so snapshotom **aktívneho** modelu zmeny; existujúca zmena (aj importovaná)
  sa iba otvorí. Bez aktívneho modelu sa zmena nevytvorí (`NoActiveShiftModel`).
- `save_hour` uloží celý stav hodiny v jednej transakcii: validácia V1–V12, V14 (chyby → nič sa neuloží),
  upsert výroby, udalosti podľa `issue_id` / `client_key` (aj soft-deleted → obnova), soft delete chýbajúcich,
  rozpis zmätkov, stav zmeny `open → in_progress → completed`; úprava dokončenej zmeny → `revision + 1`.
- `incomplete` sa nevypočítava plánovačom, ale pri čítaní (`effective_status`) z lokálneho času linky.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from oee.contracts.hourly_report import HourlyReport
from oee.domain.shift_model import (
    HourSlot,
    ShiftPlan,
    build_shift_plan,
    config_from_snapshot,
    config_to_snapshot,
)
from oee.domain.validation import (
    ActiveCodes,
    HourInput,
    IssueInput,
    RejectLine,
    ValidationMessage,
    has_errors,
    validate_hour,
)
from oee.persistence.models import HourlyReportRow, IssueEvent, ProductionRecord, QualityRecord, Shift
from oee.persistence.repositories import (
    QualityLine,
    active_issues_for_hours,
    find_issue_by_client_key,
    replace_hour_quality,
)
from oee.services.shift_models import get_active_model

SHIFT_CODE = "M"  # MVP: jedna zmena denne na linku (TASK §4.3, §11.8)
SOURCE = "manual"

ShiftStatus = Literal["open", "in_progress", "completed", "incomplete"]
HourStatus = Literal["submitted", "needs_attention"]


class NoActiveShiftModel(LookupError):
    """Linka nemá aktívny model zmeny — manažér ho musí najprv nastaviť v Settings (D8)."""


class ShiftNotFound(LookupError):
    pass


@dataclass(frozen=True)
class SaveResult:
    saved: bool
    hour_status: HourStatus | None
    """None, ak sa hodina pre chyby neuložila."""
    shift_status: str
    hours_submitted: int
    messages: list[ValidationMessage]


def shift_id_for(line: str, day: date) -> str:
    return f"{line}-{day:%Y%m%d}-{SHIFT_CODE}"


def hour_id_for(line: str, day: date, hour_no: int) -> str:
    return f"{line}-{day:%Y%m%d}-{hour_no:02d}"


def _plan(shift: Shift) -> ShiftPlan:
    return build_shift_plan(config_from_snapshot(shift.model_snapshot), shift.date)


# --- zmena --------------------------------------------------------------------------------------


def open_shift(session: Session, *, line: str, day: date, now: datetime) -> Shift:
    """Existujúca zmena linky v daný deň, inak nová so snapshotom aktívneho modelu (commit).

    Raises:
        NoActiveShiftModel: zmena neexistuje a linka nemá aktívny model.
    """
    existing = session.scalar(
        select(Shift).where(Shift.line_id == line, Shift.date == day, Shift.shift_code == SHIFT_CODE)
    )
    if existing is not None:
        return existing
    model = get_active_model(session, line=line)
    if model is None:
        raise NoActiveShiftModel(f"Line {line} has no active shift model — set the target in Settings first")
    shift = Shift(
        shift_id=shift_id_for(line, day),
        line_id=line,
        product_id=model.product,
        date=day,
        shift_code=SHIFT_CODE,
        model_snapshot={**config_to_snapshot(model.config), "grace_min": model.grace_min},
        status="open",
        revision=0,
        created_at=now,
        updated_at=now,
    )
    session.add(shift)
    try:
        session.commit()
    except IntegrityError:  # súbežné otvorenie tej istej zmeny — použije sa tá, ktorá vznikla skôr
        session.rollback()
        existing = session.get(Shift, shift_id_for(line, day))
        if existing is None:
            raise
        return existing
    return shift


def effective_status(shift: Shift, *, now_local: datetime, grace_min: int | None = None) -> str:
    """Stav pri čítaní: nedokončená zmena po konci + grace = `incomplete` (DB sa nemení).

    `now_local` = naivný **lokálny** čas linky (nie UTC audit, ARCHITECTURE §10.3).
    `grace_min` = None → grace zo snapshotu zmeny (zmena Settings nemení staré zmeny); inak 0.
    """
    if shift.status == "completed":
        return "completed"
    if grace_min is None:
        grace_min = int(shift.model_snapshot.get("grace_min", 0))
    if now_local > _plan(shift).end + timedelta(minutes=grace_min):
        return "incomplete"
    return shift.status


# --- hodina -------------------------------------------------------------------------------------


def _start_at(slot: HourSlot | None, value: time | None) -> datetime | None:
    """HH:MM v slote → celý dátum a čas (slot môže prechádzať cez polnoc)."""
    if value is None or slot is None:
        return None
    candidate = datetime.combine(slot.start.date(), value)
    return candidate + timedelta(days=1) if candidate < slot.start else candidate


def _as_input(e: IssueEvent) -> IssueInput:
    return IssueInput(
        key=e.issue_id,
        client_key=e.client_key,
        code=e.issue_type_code,
        duration_min=e.duration_min,
        start=e.start_at,
        continues_key=e.continues_issue_id,
        comment=e.comment,
    )


def _hour_input(report: HourlyReport, slot: HourSlot | None) -> HourInput:
    return HourInput(
        hour_no=report.hour_no,
        produced=report.produced,
        rejects=report.rejects,
        rejects_by_defect=tuple(
            RejectLine(r.defect_type_code, r.qty, r.comment) for r in report.rejects_by_defect
        ),
        issues=tuple(
            IssueInput(
                key=i.issue_id or i.client_key,
                client_key=i.client_key,
                code=i.issue_type_code,
                duration_min=i.duration_min,
                start=_start_at(slot, i.start_time),
                continues_key=i.continues_issue_id,
                comment=i.comment,
            )
            for i in report.issues
        ),
    )


def _hours_submitted(session: Session, shift_id: str) -> int:
    return int(session.scalar(select(func.count()).where(HourlyReportRow.shift_id == shift_id)) or 0)


def _upsert_issues(
    session: Session, report: HourlyReport, hour_id: str, slot: HourSlot, now: datetime
) -> None:
    kept: set[str] = set()
    for item in report.issues:
        event = session.get(IssueEvent, item.issue_id) if item.issue_id else None
        if item.issue_id and (event is None or event.hour_id != hour_id):
            raise ValueError(f"issue {item.issue_id} does not belong to hour {hour_id}")
        if event is None:
            event = find_issue_by_client_key(session, item.client_key)
            if event is not None and event.hour_id != hour_id:
                raise ValueError(f"client_key {item.client_key} belongs to another hour")
        if item.continues_issue_id and session.get(IssueEvent, item.continues_issue_id) is None:
            raise ValueError(f"continued issue {item.continues_issue_id} does not exist")
        if event is None:
            event = IssueEvent(hour_id=hour_id, client_key=item.client_key, source=SOURCE, created_at=now)
            session.add(event)
        event.issue_type_code = item.issue_type_code
        event.duration_min = item.duration_min
        event.start_at = _start_at(slot, item.start_time)
        event.continues_issue_id = item.continues_issue_id
        event.comment = item.comment
        event.deleted_at = None  # opakované odoslanie obnoví soft-deleted udalosť
        event.updated_at = now
        session.flush()
        kept.add(event.issue_id)
    for event in active_issues_for_hours(session, [hour_id]):
        if event.issue_id not in kept:
            event.deleted_at = now
            event.updated_at = now


def save_hour(
    session: Session, shift_id: str, report: HourlyReport, *, codes: ActiveCodes, now: datetime
) -> SaveResult:
    """Uloží celý stav hodiny (commit pri úspechu; pri chybách validácie sa nič nezapíše).

    `codes` = aktívne kódy (Top-10 + Other); `now` = naivný UTC čas auditu.

    Raises:
        ShiftNotFound: zmena neexistuje.
        ValueError: nekonzistentná požiadavka (iná zmena / hodina, cudzí `issue_id`, neznáme pokračovanie).
    """
    shift = session.get(Shift, shift_id)
    if shift is None:
        raise ShiftNotFound(shift_id)
    if report.shift_id != shift_id:
        raise ValueError(f"report shift_id {report.shift_id} does not match shift {shift_id}")
    hour_id = hour_id_for(shift.line_id, shift.date, report.hour_no)
    if report.hour_id != hour_id:
        raise ValueError(f"report hour_id {report.hour_id} does not match {hour_id}")

    ids = [i.issue_id for i in report.issues if i.issue_id]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate issue_id in one hour")

    plan = _plan(shift)
    slot = next((s for s in plan.slots if s.hour_no == report.hour_no), None)
    other_hours = [
        hid
        for hid in session.scalars(
            select(HourlyReportRow.hour_id).where(HourlyReportRow.shift_id == shift_id)
        )
        if hid != hour_id
    ]
    others = [_as_input(e) for e in active_issues_for_hours(session, other_hours)]
    messages = validate_hour(plan, _hour_input(report, slot), others, codes)
    if has_errors(messages) or slot is None:
        return SaveResult(False, None, shift.status, _hours_submitted(session, shift_id), messages)

    hour_status: HourStatus = "needs_attention" if messages else "submitted"
    try:
        hour = session.get(HourlyReportRow, hour_id)
        if hour is None:
            hour = HourlyReportRow(
                hour_id=hour_id,
                shift_id=shift_id,
                hour_no=slot.hour_no,
                slot_start=slot.start,
                slot_end=slot.end,
                planned_min=slot.planned_min,
                status=hour_status,
                updated_at=now,
            )
            session.add(hour)
        hour.status = hour_status
        hour.submitted_by = report.submitted_by
        hour.submitted_at = now
        hour.updated_at = now

        production = session.get(ProductionRecord, hour_id)
        if production is None:
            production = ProductionRecord(hour_id=hour_id, produced_qty=0, rejects_qty=0, source=SOURCE)
            session.add(production)
        production.produced_qty = report.produced
        production.rejects_qty = report.rejects
        production.retests = report.retests
        session.flush()

        _upsert_issues(session, report, hour_id, slot, now)
        replace_hour_quality(
            session,
            hour_id,
            [QualityLine(r.defect_type_code, r.qty, r.comment) for r in report.rejects_by_defect],
            source=SOURCE,
            now=now,
        )

        submitted = _hours_submitted(session, shift_id)
        if submitted == len(plan.slots):
            if shift.status == "completed":
                shift.revision += 1  # úprava po dokončení (TASK §5.6)
            else:
                shift.status, shift.completed_at = "completed", now
        elif shift.status != "completed":
            shift.status = "in_progress"
        shift.updated_at = now
        session.commit()
    except Exception:
        session.rollback()
        raise
    return SaveResult(True, hour_status, shift.status, submitted, messages)


# --- čítanie pre stránku Hourly Reporting (TASK §5.2) ---------------------------------------------


@dataclass(frozen=True)
class HourTile:
    hour_no: int
    hour_id: str
    start: datetime
    end: datetime
    planned_min: int
    target: float
    status: Literal["empty", "submitted", "needs_attention"]
    produced: int | None
    rejects: int | None
    problems: int


@dataclass(frozen=True)
class ShiftOverview:
    shift: Shift
    status: str
    """Stav pri čítaní (`effective_status`)."""
    tiles: tuple[HourTile, ...]

    @property
    def hours_submitted(self) -> int:
        return sum(t.status != "empty" for t in self.tiles)


@dataclass(frozen=True)
class IssueRow:
    issue_id: str
    client_key: str
    code: str
    duration_min: float
    start: time | None
    continues_issue_id: str | None
    comment: str | None


@dataclass(frozen=True)
class DefectRow:
    code: str | None
    """None = „Unspecified defect" (rozpis nebol zadaný)."""
    qty: int
    comment: str | None


@dataclass(frozen=True)
class HourState:
    """Uložený stav hodiny pre predvyplnenie formulára."""

    tile: HourTile
    issues: tuple[IssueRow, ...]
    defects: tuple[DefectRow, ...]
    previous_issues: tuple[IssueRow, ...]
    """Udalosti predchádzajúcej hodiny — kandidáti na „pokračovanie" (TASK §3.4 pravidlo 3)."""


def get_shift(session: Session, shift_id: str) -> Shift:
    shift = session.get(Shift, shift_id)
    if shift is None:
        raise ShiftNotFound(shift_id)
    return shift


def _issue_row(e: IssueEvent) -> IssueRow:
    return IssueRow(
        issue_id=e.issue_id,
        client_key=e.client_key or e.issue_id,
        code=e.issue_type_code,
        duration_min=e.duration_min,
        start=None if e.start_at is None else e.start_at.time(),
        continues_issue_id=e.continues_issue_id,
        comment=e.comment,
    )


def shift_overview(session: Session, shift_id: str, *, now_local: datetime) -> ShiftOverview:
    """Hlavička zmeny a N dlaždíc hodín (stav, Produced, Rejects, počet problémov).

    Raises:
        ShiftNotFound: zmena neexistuje.
    """
    shift = get_shift(session, shift_id)
    plan = _plan(shift)
    ids = [hour_id_for(shift.line_id, shift.date, s.hour_no) for s in plan.slots]
    rows = {
        r.hour_id: r
        for r in session.scalars(select(HourlyReportRow).where(HourlyReportRow.shift_id == shift_id))
    }
    production = {
        p.hour_id: p
        for p in session.scalars(select(ProductionRecord).where(ProductionRecord.hour_id.in_(ids)))
    }
    problems: dict[str, int] = {}
    for event in active_issues_for_hours(session, ids):
        problems[event.hour_id] = problems.get(event.hour_id, 0) + 1
    tiles = []
    for slot, hour_id in zip(plan.slots, ids, strict=True):
        row, prod = rows.get(hour_id), production.get(hour_id)
        status: Literal["empty", "submitted", "needs_attention"] = (
            "empty" if row is None else "needs_attention" if row.status == "needs_attention" else "submitted"
        )
        tiles.append(
            HourTile(
                hour_no=slot.hour_no,
                hour_id=hour_id,
                start=slot.start,
                end=slot.end,
                planned_min=slot.planned_min,
                target=slot.target,
                status=status,
                produced=None if prod is None else prod.produced_qty,
                rejects=None if prod is None else prod.rejects_qty,
                problems=problems.get(hour_id, 0),
            )
        )
    return ShiftOverview(shift, effective_status(shift, now_local=now_local), tuple(tiles))


def hour_state(overview: ShiftOverview, session: Session, hour_no: int) -> HourState:
    """Uložené dáta hodiny `hour_no` (prázdne, ak ešte nebola odoslaná).

    Raises:
        LookupError: hodina nie je súčasťou zmeny.
    """
    tile = next((t for t in overview.tiles if t.hour_no == hour_no), None)
    if tile is None:
        raise LookupError(f"hour {hour_no} is not part of shift {overview.shift.shift_id}")
    previous = next((t for t in overview.tiles if t.hour_no == hour_no - 1), None)
    defects = tuple(
        DefectRow(q.defect_type_code, q.qty, q.comment)
        for q in session.scalars(
            select(QualityRecord)
            .where(QualityRecord.hour_id == tile.hour_id)
            .order_by(QualityRecord.created_at)
        )
        if q.defect_type_code is not None  # „Unspecified" vzniká automaticky — formulár ho neukazuje
    )
    return HourState(
        tile=tile,
        issues=tuple(_issue_row(e) for e in active_issues_for_hours(session, [tile.hour_id])),
        defects=defects,
        previous_issues=()
        if previous is None
        else tuple(_issue_row(e) for e in active_issues_for_hours(session, [previous.hour_id])),
    )

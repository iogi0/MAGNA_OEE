"""Zostavenie primárnych záznamov v DB pre unit testy služieb (bez importu Excelu)."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from oee.domain.shift_model import ShiftModelConfig, build_shift_plan, config_to_snapshot
from oee.persistence.models import HourlyReportRow, IssueEvent, ProductionRecord, Shift
from oee.persistence.repositories import replace_hour_quality

AUDIT_NOW = datetime(2026, 12, 9, 18, 0)


def shift_id_for(day: date, line: str = "L01") -> str:
    return f"{line}-{day:%Y%m%d}-M"


def hour_id_for(day: date, hour_no: int, line: str = "L01") -> str:
    return f"{line}-{day:%Y%m%d}-{hour_no:02d}"


def add_shift(
    s: Session,
    config: ShiftModelConfig,
    day: date,
    hours: dict[int, tuple[int, int]],
    *,
    status: str = "in_progress",
    retests: int | None = None,
) -> str:
    """Zmena s hodinami `{hour_no: (produced, rejects)}` podľa plánu z `config`. Vráti `shift_id`."""
    plan = build_shift_plan(config, day)
    sid = shift_id_for(day)
    s.add(
        Shift(
            shift_id=sid,
            line_id="L01",
            product_id="P01",
            date=day,
            shift_code="M",
            model_snapshot=config_to_snapshot(config),
            status=status,
            revision=0,
            created_at=AUDIT_NOW,
            updated_at=AUDIT_NOW,
        )
    )
    for slot in plan.slots:
        if slot.hour_no not in hours:
            continue
        hid = hour_id_for(day, slot.hour_no)
        s.add(
            HourlyReportRow(
                hour_id=hid,
                shift_id=sid,
                hour_no=slot.hour_no,
                slot_start=slot.start,
                slot_end=slot.end,
                planned_min=slot.planned_min,
                status="submitted",
                updated_at=AUDIT_NOW,
            )
        )
        produced, rejects = hours[slot.hour_no]
        s.add(
            ProductionRecord(
                hour_id=hid, produced_qty=produced, rejects_qty=rejects, retests=retests, source="manual"
            )
        )
        s.flush()
        replace_hour_quality(
            s, hid, [], source="manual", now=AUDIT_NOW
        )  # invariant: bez rozpisu = Unspecified
    s.flush()
    return sid


def add_issue(
    s: Session,
    day: date,
    hour_no: int,
    code: str,
    minutes: float,
    start: datetime | None = None,
    **kw: object,
) -> IssueEvent:
    event = IssueEvent(
        hour_id=hour_id_for(day, hour_no),
        client_key=f"ck-{day:%Y%m%d}-{hour_no}-{code}-{minutes}",
        issue_type_code=code,
        duration_min=minutes,
        start_at=start,
        source="manual",
        created_at=AUDIT_NOW,
        updated_at=AUDIT_NOW,
        **kw,
    )
    s.add(event)
    s.flush()
    return event

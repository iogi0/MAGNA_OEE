"""Repozitáre a aplikačné invarianty naprieč tabuľkami.

SQLite CHECK nevidí iné tabuľky, preto invarianty kontroluje kód (ARCHITECTURE §10.2).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import NamedTuple

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from oee.persistence.models import IssueEvent, ProductionRecord, QualityRecord


class QualityInvariantError(ValueError):
    """Σ quality_record.qty ≠ production_record.rejects_qty."""


class QualityLine(NamedTuple):
    code: str | None
    """Kód zmätku; None = „Unspecified defect"."""
    qty: int
    comment: str | None = None
    external_ref: str | None = None
    """Prirodzený kľúč importu (`NOK_ID`)."""


def replace_hour_quality(
    session: Session,
    hour_id: str,
    breakdown: Sequence[QualityLine | tuple[str | None, int]],
    *,
    source: str,
    now: datetime,
) -> list[QualityRecord]:
    """Nahradí rozpis zmätkov hodiny.

    Bez rozpisu pri `rejects_qty > 0` vznikne jeden záznam „Unspecified" na celé množstvo (TASK §9.1),
    takže invariant Σ qty = `rejects_qty` platí vždy.

    Raises:
        QualityInvariantError: hodina nemá záznam výroby alebo súčet rozpisu ≠ `rejects_qty`.
    """
    production = session.get(ProductionRecord, hour_id)
    if production is None:
        raise QualityInvariantError(f"hour {hour_id}: production record missing")

    lines = [QualityLine(*item) for item in breakdown]
    if not lines and production.rejects_qty > 0:
        lines = [QualityLine(None, production.rejects_qty)]
    total = sum(line.qty for line in lines)
    if total != production.rejects_qty:
        raise QualityInvariantError(
            f"hour {hour_id}: breakdown sums to {total}, but rejects_qty is {production.rejects_qty}"
        )

    session.execute(delete(QualityRecord).where(QualityRecord.hour_id == hour_id))
    records = [
        QualityRecord(
            hour_id=hour_id,
            defect_type_code=line.code,
            qty=line.qty,
            comment=line.comment,
            external_ref=line.external_ref,
            source=source,
            created_at=now,
        )
        for line in lines
    ]
    session.add_all(records)
    session.flush()
    return records


def active_issues_for_hours(session: Session, hour_ids: Sequence[str]) -> list[IssueEvent]:
    """Nezmazané udalosti daných hodín v poradí vzniku."""
    stmt = (
        select(IssueEvent)
        .where(IssueEvent.hour_id.in_(hour_ids), IssueEvent.deleted_at.is_(None))
        .order_by(IssueEvent.created_at, IssueEvent.issue_id)
    )
    return list(session.scalars(stmt))


def active_issues(session: Session, hour_id: str) -> list[IssueEvent]:
    """Nezmazané udalosti hodiny v poradí vzniku."""
    return active_issues_for_hours(session, [hour_id])


def find_issue_by_client_key(session: Session, client_key: str) -> IssueEvent | None:
    """Udalosť podľa kľúča idempotencie — aj soft-deleted (opakované odoslanie ju obnoví, nie zduplikuje)."""
    return session.scalar(select(IssueEvent).where(IssueEvent.client_key == client_key))


def soft_delete_issue(session: Session, issue_id: str, now: datetime) -> None:
    event = session.get(IssueEvent, issue_id)
    if event is None:
        raise KeyError(issue_id)
    event.deleted_at = now
    event.updated_at = now
    session.flush()

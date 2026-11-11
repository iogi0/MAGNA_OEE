"""Repozitáre a aplikačné invarianty naprieč tabuľkami.

SQLite CHECK nevidí iné tabuľky, preto invarianty kontroluje kód (ARCHITECTURE §10.2).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any, NamedTuple

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from oee.persistence.models import AiOutput, IssueEvent, ProductionRecord, QualityRecord


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


# --- cache výstupu AI (ARCHITECTURE §5, §10.6) -------------------------------------------------------


class AiKey(NamedTuple):
    """Kľúč `ai_output`: zmena faktov, modelu, jazyka alebo verzie promptu = nový záznam."""

    kind: str
    subject_key: str
    facts_hash: str
    model: str
    lang: str
    prompt_version: str


def _ai_filter(key: AiKey) -> list[Any]:
    return [getattr(AiOutput, name) == value for name, value in key._asdict().items()]


def get_ai_output(session: Session, key: AiKey) -> AiOutput | None:
    return session.scalar(select(AiOutput).where(*_ai_filter(key)))


def claim_ai_output(
    session: Session, key: AiKey, *, now: datetime, stale_after: timedelta
) -> AiOutput | None:
    """Rezervuje generovanie: vloží `pending` a vráti ho; ak už záznam existuje, vráti None.

    Výnimka: `pending` starší ako `stale_after` (proces padol) sa prevezme — vráti sa ten istý riadok
    s novým `updated_at`. Hotový záznam (ok / fallback / error) sa nikdy neprevezme.
    """
    row = AiOutput(**key._asdict(), status="pending", payload=None, created_at=now, updated_at=now)
    try:
        with session.begin_nested():
            session.add(row)
    except IntegrityError:
        existing = get_ai_output(session, key)
        if existing is None or existing.status != "pending" or now - existing.updated_at <= stale_after:
            return None
        # atomické prevzatie: uspeje iba proces, ktorý videl rovnaký starý `updated_at`
        taken = session.execute(
            update(AiOutput)
            .where(
                AiOutput.id == existing.id,
                AiOutput.status == "pending",
                AiOutput.updated_at == existing.updated_at,
            )
            .values(updated_at=now)
            .execution_options(synchronize_session=False)
        )
        if taken.rowcount != 1:  # type: ignore[attr-defined]
            return None
        session.refresh(existing)
        return existing
    return row


def finish_ai_output(
    session: Session, row: AiOutput, *, status: str, payload: dict[str, Any] | None, now: datetime
) -> None:
    """Uloží výsledok rezervovaného záznamu (`ok` / `fallback` / `error`); commit robí volajúci."""
    row.status, row.payload, row.updated_at = status, payload, now
    session.flush()

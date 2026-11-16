"""Model zmeny, ktorý zadáva manažér v Settings (TASK §3.2, PLANNING D8).

Model sa verzionuje: nová verzia deaktivuje predchádzajúcu. Existujúce zmeny si držia svoj snapshot.
Bez aktívneho modelu sa nová zmena nedá vytvoriť (žiadny skrytý predvolený model).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from oee.domain.shift_model import Allowance, ShiftModelConfig, ShiftModelError, validate_shift_model
from oee.persistence.models import ShiftModelRow


@dataclass(frozen=True)
class ActiveModel:
    config: ShiftModelConfig
    version: int
    line: str
    product: str
    grace_min: int


def _to_config(row: ShiftModelRow) -> ShiftModelConfig:
    return ShiftModelConfig(
        rate_per_hour=row.line_rate_pcs_per_hour,
        start=time.fromisoformat(row.shift_start),
        duration_min=row.shift_length_min,
        break_=Allowance(row.break_min, row.break_hour_no, row.break_offset_min),
        am=Allowance(row.am_min, row.am_hour_no, row.am_offset_min),
        target_oee=row.target_oee,
        working_days=frozenset(row.working_days),
    )


def get_active_model(session: Session, *, line: str) -> ActiveModel | None:
    row = session.scalar(select(ShiftModelRow).where(ShiftModelRow.line_id == line, ShiftModelRow.active))
    if row is None:
        return None
    return ActiveModel(_to_config(row), row.version, row.line_id, row.product_id, row.grace_min)


def activate_shift_model(
    session: Session,
    config: ShiftModelConfig,
    *,
    line: str,
    product: str,
    grace_min: int,
    now: datetime,
) -> ShiftModelRow:
    """Uloží novú verziu modelu linky ako aktívnu (iba flush; commit robí volajúci — služba Settings, P0-16).

    Raises:
        ShiftModelError: model je nevalidný (nič sa neuloží).
        ValueError: `grace_min` je záporné.
    """
    issues = validate_shift_model(config)
    if issues:
        raise ShiftModelError(issues)
    if grace_min < 0:
        raise ValueError("grace_min must not be negative")
    for old in session.scalars(
        select(ShiftModelRow).where(ShiftModelRow.line_id == line, ShiftModelRow.active)
    ):
        old.active = False
    session.flush()  # čiastočný UNIQUE index: najviac jeden aktívny model na linku
    version = (
        session.scalar(select(func.max(ShiftModelRow.version)).where(ShiftModelRow.line_id == line)) or 0
    ) + 1
    row = ShiftModelRow(
        version=version,
        line_id=line,
        product_id=product,
        line_rate_pcs_per_hour=config.rate_per_hour,
        shift_start=config.start.strftime("%H:%M"),
        shift_length_min=config.duration_min,
        break_min=config.break_.minutes,
        break_hour_no=config.break_.hour_no,
        break_offset_min=config.break_.offset_min,
        am_min=config.am.minutes,
        am_hour_no=config.am.hour_no,
        am_offset_min=config.am.offset_min,
        target_oee=config.target_oee,
        working_days=sorted(config.working_days),
        grace_min=grace_min,
        active=True,
        created_at=now,
    )
    session.add(row)
    session.flush()
    return row

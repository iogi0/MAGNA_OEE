"""`hourly_report` — vstup hodiny z UI (TASK §10.1) a odpoveď servera.

Úpravy voči TASK (PLANNING D5, D10, P0-05):
- `issue_type_code` je povinný; `category_id` sa neposiela (kategória sa odvodí z kódu);
- pole `name` (voľný text) sa neposiela — pri „Other" je voľným textom povinný `comment` (V11);
- `rejects_by_defect[].comment` — komentár pre „Other" pri zmätkoch (V11);
- `produced`, `rejects`, `qty` sú celé čísla (V1, V10).

Kontrakt kontroluje iba tvar dát. Obchodné pravidlá (V1–V12, V14) overuje `domain.validation`.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import Field

from oee.contracts.common import (
    HHMM,
    Contract,
    Count,
    DefectCode,
    HourNo,
    Level,
    NonEmptyStr,
    PositiveCount,
    ShiftStatus,
    StopCode,
)


class RejectByDefect(Contract):
    defect_type_code: DefectCode
    qty: PositiveCount
    comment: str | None = None


class IssueReport(Contract):
    issue_id: str | None = None
    """None = nová udalosť; inak úprava existujúcej."""
    client_key: NonEmptyStr
    """Kľúč idempotencie (V9)."""
    issue_type_code: StopCode
    duration_min: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    start_time: HHMM | None = None
    continues_issue_id: str | None = None
    comment: str | None = None


class HourlyReport(Contract):
    """Celý stav hodiny (server porovná udalosti podľa `issue_id` / `client_key`)."""

    hour_id: NonEmptyStr
    shift_id: NonEmptyStr
    date: date
    hour_no: HourNo
    produced: Count
    rejects: Count
    rejects_by_defect: tuple[RejectByDefect, ...] = ()
    issues: tuple[IssueReport, ...] = ()
    retests: Count | None = None
    """P1 (First-pass quality)."""
    submitted_by: str | None = None


class ValidationMessageOut(Contract):
    level: Level
    rule: NonEmptyStr
    field: str
    message: NonEmptyStr


class HourlyReportResponse(Contract):
    hour_status: Literal["submitted", "needs_attention"]
    shift_status: ShiftStatus
    hours_submitted: Count
    messages: tuple[ValidationMessageOut, ...] = ()

"""`shift_analytics` — výsledok zmeny pre Shift Dashboard (TASK §10.2).

Úpravy (PLANNING D1, D8):
- `shift.hours_total` = N hodín zmeny z modelu (stav „n/N provisional"); N nie je pevne 8;
- nevyplnené hodiny provisional zmeny majú v `hourly` hodnoty `null` (nie 0) a príznak `not_submitted`;
- `ai_recommendations` je P2 (D1) — v P0 prázdny zoznam.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, Self

from pydantic import Field, JsonValue, StringConstraints, model_validator

from oee.contracts.common import (
    HHMM,
    Alert,
    Contract,
    Count,
    DataQualityIssue,
    DefectCode,
    HourNo,
    LossKind,
    Minutes,
    NonEmptyStr,
    OeeStatus,
    Ratio,
    ShiftStatus,
    StopCode,
    TextSource,
)

Weekday = Literal["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
Slot = Annotated[str, StringConstraints(pattern=r"^\d{2}:\d{2}-\d{2}:\d{2}$")]


class ShiftHeader(Contract):
    shift_id: NonEmptyStr
    date: date
    weekday: Weekday
    line: NonEmptyStr
    product: NonEmptyStr
    status: ShiftStatus
    provisional: bool
    hours_submitted: Count
    hours_total: Annotated[int, Field(strict=True, ge=1)]
    revision: Count
    computed_at: datetime

    @model_validator(mode="after")
    def _submitted_within_total(self) -> Self:
        if self.hours_submitted > self.hours_total:
            raise ValueError("hours_submitted cannot exceed hours_total")
        return self


class ShiftModelSnapshot(Contract):
    calendar_min: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    planned_min: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    ideal_cycle_s: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    target_oee: Annotated[float, Field(gt=0, le=1)]


class Kpi(Contract):
    """A, P, Q, OEE ako podiely 0–1; None = nedefinované (Run = 0, Produced = 0)."""

    availability: Ratio | None
    performance: Ratio | None
    quality: Ratio | None
    oee: Ratio | None
    oee_gap_pp: Ratio | None = None
    oee_status: OeeStatus | None = None
    first_pass_quality: Ratio | None = None


class TargetVsActual(Contract):
    target_pcs: Ratio
    produced_pcs: Count
    rejects_pcs: Count
    good_pcs: Count
    production_vs_target: Ratio | None
    good_vs_target: Ratio | None
    deviation_from_target_pcs: Ratio
    oee_goal_pcs: Ratio


class Waterfall(Contract):
    """Kaskáda v kusoch: target − technical_losses − speed_loss − quality_loss = good."""

    target: Ratio
    technical_losses: Ratio
    speed_loss: Ratio
    quality_loss: Ratio
    good: Ratio


class CategoryLoss(Contract):
    category: NonEmptyStr
    min: Minutes
    events: Count


class TechnicalLosses(Contract):
    total_min: Minutes
    events: Count
    share_of_target: Ratio | None
    by_category: tuple[CategoryLoss, ...] = ()


class SpeedDecomposition(Contract):
    """Rozklad S v sekundách — iba z rozšírených polí importu (TASK §3.4 pravidlo 6)."""

    microstops: Annotated[float, Field(ge=0)]
    retests: Annotated[float, Field(ge=0)]
    slowdown: Annotated[float, Field(ge=0)]


class SpeedLoss(Contract):
    pcs: Ratio
    decomposition_s: SpeedDecomposition | None = None


class DefectQty(Contract):
    code: DefectCode | None
    """None = „Unspecified defect" (zmätky bez rozpisu)."""
    qty: Count


class QualityBlock(Contract):
    rejects: Count
    reject_rate: Ratio | None
    by_defect: tuple[DefectQty, ...] = ()
    by_hour: tuple[Count | None, ...] = ()


class HourRow(Contract):
    """Hodina zmeny; pri nevyplnenej hodine sú namerané hodnoty None („not submitted")."""

    hour_no: HourNo
    slot: Slot
    planned_min: Minutes
    target_pcs: Ratio
    produced: Count | None
    rejects: Count | None
    downtime_min: Minutes | None
    speed_loss_pcs: Ratio | None
    availability: Ratio | None
    performance: Ratio | None
    quality: Ratio | None
    oee: Ratio | None
    flags: tuple[str, ...] = ()


class IssueRow(Contract):
    issue_id: NonEmptyStr
    hour_no: HourNo
    start_time: HHMM | None
    category: NonEmptyStr
    issue_type: StopCode
    name: NonEmptyStr
    duration_min: Minutes
    lost_pcs: Ratio
    share_of_target: Ratio | None
    flags: tuple[str, ...] = ()
    comment: str | None = None
    """Komentár operátora (pri „Other" je to voľný popis problému)."""


class ParetoBucket(Contract):
    bucket: NonEmptyStr
    """Kód problému alebo `unattributed_speed_loss`."""
    kind: LossKind | None = None
    pcs: Ratio
    share_of_losses: Ratio | None = None
    category: str | None = None
    """Kategória kódu (prepínač „typ / kategória", §7E); None pri nepriradenej strate rýchlosti."""


class ShiftSummary(Contract):
    facts: dict[str, JsonValue]
    text: str
    text_source: TextSource


class AiRecommendation(Contract):
    """P2 (PLANNING D1) — v P0 sa negeneruje."""

    problem_code: NonEmptyStr
    action: NonEmptyStr
    owner_role: NonEmptyStr
    expected_gain_pcs: Ratio
    linked_problems: tuple[str, ...] = ()
    source: Literal["local_ai", "rules"]


class ShiftAnalytics(Contract):
    shift: ShiftHeader
    model: ShiftModelSnapshot
    kpi: Kpi
    target_vs_actual: TargetVsActual
    waterfall_pcs: Waterfall
    technical_losses: TechnicalLosses
    speed_loss: SpeedLoss
    quality: QualityBlock
    hourly: tuple[HourRow, ...]
    issues: tuple[IssueRow, ...] = ()
    loss_pareto: tuple[ParetoBucket, ...] = ()
    summary: ShiftSummary | None = None
    ai_recommendations: tuple[AiRecommendation, ...] = ()
    alerts: tuple[Alert, ...] = ()
    data_quality: tuple[DataQualityIssue, ...] = ()

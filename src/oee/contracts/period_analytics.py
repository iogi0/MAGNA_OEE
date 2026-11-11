"""`period_analytics` — týždeň / mesiac / rozsah pre Production History (TASK §10.3).

Úpravy: `patterns` je P1 (v P0 prázdny zoznam); `problem_links[].process` = názov procesu pri same_process.
Trend rebríčka: `up` (zhoršuje sa), `down` (zlepšuje sa), `stable`, `n/a` (TASK §8.4).
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from oee.contracts.common import (
    Contract,
    Count,
    DataQualityIssue,
    DefectCode,
    ExplanationSource,
    HourNo,
    LossKind,
    Minutes,
    NonEmptyStr,
    OeeStatus,
    Ratio,
    StopCode,
)
from oee.contracts.shift_analytics import Kpi, Waterfall


class PeriodInfo(Contract):
    type: Literal["week", "month", "range"]
    from_: date = Field(alias="from")
    to: date
    line: NonEmptyStr
    shifts_completed: Count
    shifts_excluded_incomplete: Count

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.from_ > self.to:
            raise ValueError("period 'from' must not be after 'to'")
        return self


class Totals(Contract):
    planned_min: Minutes
    target_pcs: Ratio
    oee_goal_pcs: Ratio
    downtime_min: Minutes
    downtime_events: Count
    produced: Count
    rejects: Count
    good: Count
    speed_loss_pcs: Ratio
    production_vs_target: Ratio | None
    deviation_from_target_pcs: Ratio


class ShiftPoint(Contract):
    shift_id: NonEmptyStr
    date: date
    oee: Ratio | None
    status: OeeStatus


class WeekRow(Contract):
    iso_week: Annotated[int, Field(strict=True, ge=1, le=53)]
    from_: date = Field(alias="from")
    to: date
    shifts: Count
    partial: bool
    oee: Ratio | None
    availability: Ratio | None
    performance: Ratio | None
    quality: Ratio | None


class IssueStat(Contract):
    code: StopCode
    category: NonEmptyStr
    events: Count
    total_min: Minutes
    avg_min: Minutes
    lost_pcs: Ratio


class DefectStat(Contract):
    code: DefectCode
    records: Count
    qty: Count


class HourOfShiftSpeedLoss(Contract):
    hour_no: HourNo
    pcs: Ratio
    performance: Ratio | None


class UnattributedSpeedLoss(Contract):
    pcs: Ratio
    share_of_all_losses: Ratio | None
    by_hour_of_shift: tuple[HourOfShiftSpeedLoss, ...] = ()


class KpiImpact(Contract):
    kpi: Literal["availability", "quality"]
    pp: Ratio


class RankingRow(Contract):
    rank: Annotated[int, Field(strict=True, ge=1)]
    class_: Literal["A", "B", "C"] = Field(alias="class")
    kind: LossKind
    code: NonEmptyStr
    name: NonEmptyStr
    category: NonEmptyStr
    events: Count
    total_min: Minutes | None = None
    """Iba pri prestojoch."""
    avg_min: Minutes | None = None
    lost_pcs: Ratio
    share_of_recorded: Ratio | None
    share_of_all_losses: Ratio | None
    kpi_impact: KpiImpact
    trend: Literal["up", "down", "stable", "n/a"]
    trend_change: Ratio | None
    recurring: bool
    last_occurrence: date | None
    evidence: tuple[str, ...] = ()


class Pattern(Contract):
    """P1 (TASK §8.5) — v P0 prázdny zoznam."""

    rule: NonEmptyStr
    subject: NonEmptyStr
    support: NonEmptyStr
    fact: NonEmptyStr
    pattern: NonEmptyStr
    hypothesis: str
    hypothesis_source: ExplanationSource
    evidence: tuple[str, ...] = ()


class ProblemLink(Contract):
    cause: StopCode
    effect: DefectCode
    window: NonEmptyStr
    support: Count
    q_in_window: Count
    produced_in_window: Count
    rate_in_window: Ratio
    base_rate: Ratio
    lift: Ratio | None
    extra_rejects: Ratio
    link_type: Literal["same_process", "cross_process"]
    process: str | None = None
    confidence: Literal["high", "medium", "low"]
    combined_impact_pcs: Ratio
    explanation: str | None = None
    explanation_source: ExplanationSource | None = None
    evidence: tuple[str, ...] = ()


class PeriodAnalytics(Contract):
    period: PeriodInfo
    kpi: Kpi
    totals: Totals
    waterfall_pcs: Waterfall
    shift_series: tuple[ShiftPoint, ...] = ()
    weekly: tuple[WeekRow, ...] = ()
    issue_stats: tuple[IssueStat, ...] = ()
    defect_stats: tuple[DefectStat, ...] = ()
    unattributed_speed_loss: UnattributedSpeedLoss
    problem_ranking: tuple[RankingRow, ...] = ()
    patterns: tuple[Pattern, ...] = ()
    problem_links: tuple[ProblemLink, ...] = ()
    data_quality: tuple[DataQualityIssue, ...] = ()

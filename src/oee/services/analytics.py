"""Analytika zmeny na požiadanie z primárnych záznamov (TASK §6, §7, §10.2; PLANNING D6).

Služba iba načíta záznamy, zavolá doménu (`downtime`, `kpi`, `losses`, `validation`) a zloží kontrakt.

- Provisional zmena: KPI, kaskáda a Pareto sú z **odoslaných** hodín; nevyplnené hodiny majú v `hourly`
  hodnoty `None` a príznak `not_submitted` (§7C).
- Rozklad S v sekundách je P1 (`decomposition_s = None`). Shift Summary dopĺňa AI vrstva (P0-23/24).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal, get_args

from sqlalchemy import select
from sqlalchemy.orm import Session

from oee.catalog.loader import Catalog
from oee.contracts.common import DataQualityIssue
from oee.contracts.period_analytics import (
    DefectStat,
    HourOfShiftSpeedLoss,
    IssueStat,
    KpiImpact,
    PeriodAnalytics,
    PeriodInfo,
    ProblemLink,
    RankingRow,
    ShiftPoint,
    Totals,
    UnattributedSpeedLoss,
    WeekRow,
)
from oee.contracts.shift_analytics import (
    CategoryLoss,
    DefectQty,
    HourRow,
    IssueRow,
    Kpi,
    ParetoBucket,
    QualityBlock,
    ShiftAnalytics,
    ShiftHeader,
    ShiftModelSnapshot,
    SpeedLoss,
    TargetVsActual,
    TechnicalLosses,
    Waterfall,
    Weekday,
)
from oee.domain.correlation import HourObs, StopEvent, find_problem_links
from oee.domain.downtime import CountedSegment, DowntimeEvent, DowntimeSummary, count_downtime
from oee.domain.kpi import SECONDS_PER_MINUTE, Cascade, ratio, sum_cascades
from oee.domain.losses import UNSPECIFIED, event_flags, goal_status, hour_flags, loss_pareto
from oee.domain.period import first_pass_quality, is_week_complete, period_goal
from oee.domain.ranking import Kind, ProblemStats, RankedProblem, WeekInfo, rank_problems
from oee.domain.shift_model import ShiftModelConfig, ShiftPlan, build_shift_plan, config_from_snapshot
from oee.domain.validation import speed_loss_exceeds_tolerance
from oee.persistence.models import (
    DefectType,
    HourlyReportRow,
    IssueEvent,
    IssueType,
    ProductionRecord,
    QualityRecord,
    Shift,
)
from oee.persistence.repositories import active_issues_for_hours

WEEKDAYS: tuple[Weekday, ...] = get_args(Weekday)
PeriodType = Literal["week", "month", "range"]


class ShiftNotFound(LookupError):
    pass


@dataclass(frozen=True)
class _Records:
    shift: Shift
    hours: dict[int, tuple[HourlyReportRow, ProductionRecord]]
    """Odoslané hodiny podľa poradia v zmene."""
    issues: list[IssueEvent]
    issue_types: dict[str, IssueType]
    quality: list[QualityRecord]
    defect_types: dict[str, DefectType]

    @property
    def hour_no_by_id(self) -> dict[str, int]:
        return {row.hour_id: no for no, (row, _) in self.hours.items()}


def _load(session: Session, shift_id: str) -> _Records:
    shift = session.get(Shift, shift_id)
    if shift is None:
        raise ShiftNotFound(shift_id)
    rows = session.execute(
        select(HourlyReportRow, ProductionRecord)
        .join(ProductionRecord, ProductionRecord.hour_id == HourlyReportRow.hour_id)
        .where(HourlyReportRow.shift_id == shift_id)
    ).all()
    hours = {row.hour_no: (row, prod) for row, prod in rows}
    hour_ids = [row.hour_id for row, _ in hours.values()]
    issues = active_issues_for_hours(session, hour_ids)
    quality = list(session.scalars(select(QualityRecord).where(QualityRecord.hour_id.in_(hour_ids))))
    stop_codes = {e.issue_type_code for e in issues}
    defect_codes = {q.defect_type_code for q in quality if q.defect_type_code}
    return _Records(
        shift=shift,
        hours=hours,
        issues=issues,
        issue_types={
            t.code: t for t in session.scalars(select(IssueType).where(IssueType.code.in_(stop_codes)))
        },
        quality=quality,
        defect_types={
            t.code: t for t in session.scalars(select(DefectType).where(DefectType.code.in_(defect_codes)))
        },
    )


def _count_downtime(plan: ShiftPlan, rec: _Records) -> DowntimeSummary:
    hour_no = rec.hour_no_by_id
    return count_downtime(
        plan,
        [
            DowntimeEvent(e.issue_id, hour_no[e.hour_id], e.duration_min, e.start_at, e.continues_issue_id)
            for e in rec.issues
        ],
    )


def _hourly(
    plan: ShiftPlan, rec: _Records, downtime: DowntimeSummary, goal: float
) -> tuple[list[HourRow], dict[int, Cascade], list[DataQualityIssue]]:
    down_by_hour = {h.hour_no: h.downtime_min for h in downtime.hours}
    rows: list[HourRow] = []
    cascades: dict[int, Cascade] = {}
    data_quality: list[DataQualityIssue] = []
    for slot in plan.slots:
        base = {
            "hour_no": slot.hour_no,
            "slot": f"{slot.start:%H:%M}-{slot.end:%H:%M}",
            "planned_min": slot.planned_min,
            "target_pcs": slot.target,
        }
        submitted = rec.hours.get(slot.hour_no)
        if submitted is None:
            empty = dict.fromkeys(
                (
                    "produced",
                    "rejects",
                    "downtime_min",
                    "speed_loss_pcs",
                    "availability",
                    "performance",
                    "quality",
                    "oee",
                )
            )
            rows.append(HourRow.model_validate({**base, **empty, "flags": ("not_submitted",)}))
            continue
        hour, production = submitted
        c = Cascade.from_minutes(
            planned_min=slot.planned_min,
            downtime_min=down_by_hour[slot.hour_no],
            produced=production.produced_qty,
            rejects=production.rejects_qty,
            ideal_cycle_s=plan.ideal_cycle_s,
        )
        cascades[slot.hour_no] = c
        if speed_loss_exceeds_tolerance(c):
            data_quality.append(
                DataQualityIssue(
                    rule="V3",
                    level="warning",
                    message="Produced exceeds what is possible in run time",
                    subject=hour.hour_id,
                )
            )
        rows.append(
            HourRow.model_validate(
                {
                    **base,
                    "produced": c.produced,
                    "rejects": c.rejects,
                    "downtime_min": c.downtime_min,
                    "speed_loss_pcs": c.speed_loss,
                    "availability": c.availability,
                    "performance": c.performance,
                    "quality": c.quality,
                    "oee": c.oee,
                    "flags": hour_flags(c, goal=goal),
                }
            )
        )
    return rows, cascades, data_quality


def _issues(
    rec: _Records, downtime: DowntimeSummary, catalog: Catalog, pcs_per_min: float, target: float
) -> tuple[list[IssueRow], list[CategoryLoss], dict[str, float]]:
    """Riadky udalostí, straty podľa kategórie a stratené kusy podľa kódu prestoja."""
    hour_no = rec.hour_no_by_id
    segments = {s.event_id: s for s in downtime.segments}
    stop_minutes: dict[str, float] = defaultdict(
        float
    )  # nahlásené trvanie celej zastávky (koreň + pokračovania)
    for e in rec.issues:
        stop_minutes[segments[e.issue_id].root_id] += e.duration_min

    rows: list[IssueRow] = []
    min_by_category: dict[str, float] = defaultdict(float)
    roots_by_category: dict[str, set[str]] = defaultdict(set)
    pcs_by_stop: dict[str, float] = defaultdict(float)
    ordered = sorted(
        rec.issues, key=lambda e: (e.start_at is None, e.start_at or datetime.min, hour_no[e.hour_id])
    )
    for e in ordered:
        seg = segments[e.issue_id]
        issue_type = rec.issue_types[e.issue_type_code]
        category = catalog.categories.get(issue_type.category, issue_type.category)
        lost = seg.counted_min * pcs_per_min
        min_by_category[category] += seg.counted_min
        roots_by_category[category].add(seg.root_id)
        pcs_by_stop[issue_type.code] += lost
        rows.append(
            IssueRow(
                issue_id=e.issue_id,
                hour_no=hour_no[e.hour_id],
                start_time=e.start_at.time().replace(second=0, microsecond=0) if e.start_at else None,
                category=category,
                issue_type=issue_type.code,
                name=issue_type.name_en,
                duration_min=e.duration_min,
                lost_pcs=lost,
                share_of_target=ratio(lost, target),
                flags=event_flags(
                    stop_duration_min=stop_minutes[seg.root_id],
                    is_continuation=e.continues_issue_id is not None,
                ),
                comment=e.comment,
            )
        )
    by_category = sorted(
        (
            CategoryLoss(category=k, min=v, events=len(roots_by_category[k]))
            for k, v in min_by_category.items()
        ),
        key=lambda c: (-c.min, c.category),
    )
    return rows, by_category, pcs_by_stop


def _defects(rec: _Records) -> dict[str | None, int]:
    """Zmätky podľa kódu (None = Unspecified), zoradené podľa množstva ↓, potom kódu."""
    qty: dict[str | None, int] = defaultdict(int)
    for q in rec.quality:
        qty[q.defect_type_code] += q.qty
    return dict(sorted(qty.items(), key=lambda kv: (-kv[1], kv[0] is None, kv[0] or "")))


def _category_names(types: Mapping[str, IssueType | DefectType], catalog: Catalog) -> dict[str, str]:
    return {code: catalog.categories.get(t.category, t.category) for code, t in types.items()}


@dataclass(frozen=True)
class _ShiftCore:
    """Výsledok výpočtu jednej zmeny — spoločný pre `build_shift` aj `build_period`."""

    rec: _Records
    config: ShiftModelConfig
    plan: ShiftPlan
    downtime: DowntimeSummary
    hour_rows: list[HourRow]
    cascades: dict[int, Cascade]
    """Kaskáda odoslaných hodín podľa poradia hodiny."""
    data_quality: list[DataQualityIssue]
    total: Cascade
    issue_rows: list[IssueRow]
    by_category: list[CategoryLoss]
    pcs_by_stop: dict[str, float]
    defect_qty: dict[str | None, int]
    segments: dict[str, CountedSegment]
    """Započítané segmenty podľa `issue_id`."""

    @property
    def goal(self) -> float:
        return self.config.target_oee

    @property
    def pcs_per_min(self) -> float:
        return SECONDS_PER_MINUTE / self.plan.ideal_cycle_s


def _compute(session: Session, shift_id: str, catalog: Catalog) -> _ShiftCore:
    rec = _load(session, shift_id)
    config = config_from_snapshot(rec.shift.model_snapshot)
    plan = build_shift_plan(config, rec.shift.date)
    downtime = _count_downtime(plan, rec)
    hour_rows, cascades, data_quality = _hourly(plan, rec, downtime, config.target_oee)
    total = sum_cascades(cascades.values())
    pcs_per_min = SECONDS_PER_MINUTE / plan.ideal_cycle_s
    issue_rows, by_category, pcs_by_stop = _issues(rec, downtime, catalog, pcs_per_min, total.target)
    return _ShiftCore(
        rec=rec,
        config=config,
        plan=plan,
        downtime=downtime,
        hour_rows=hour_rows,
        cascades=cascades,
        data_quality=data_quality,
        total=total,
        issue_rows=issue_rows,
        by_category=by_category,
        pcs_by_stop=pcs_by_stop,
        defect_qty=_defects(rec),
        segments={seg.event_id: seg for seg in downtime.segments},
    )


def build_shift(session: Session, shift_id: str, *, catalog: Catalog, now: datetime) -> ShiftAnalytics:
    """`ShiftAnalytics` (TASK §10.2) zmeny `shift_id`. `now` = čas výpočtu (naivný UTC).

    Raises:
        ShiftNotFound: zmena neexistuje.
    """
    core = _compute(session, shift_id, catalog)
    rec, config, plan, goal, total = core.rec, core.config, core.plan, core.goal, core.total
    shift, downtime, hour_rows, data_quality = rec.shift, core.downtime, core.hour_rows, core.data_quality
    issue_rows, by_category, pcs_by_stop, defect_qty = (
        core.issue_rows,
        core.by_category,
        core.pcs_by_stop,
        core.defect_qty,
    )
    pareto = loss_pareto(
        total,
        stop_pcs=pcs_by_stop,
        defect_qty=defect_qty,
        stop_category=_category_names(rec.issue_types, catalog),
        defect_category=_category_names(rec.defect_types, catalog),
    )

    return ShiftAnalytics(
        shift=ShiftHeader(
            shift_id=shift.shift_id,
            date=shift.date,
            weekday=WEEKDAYS[shift.date.weekday()],
            line=shift.line_id,
            product=shift.product_id,
            status=shift.status,  # type: ignore[arg-type]  # DB CHECK = ShiftStatus
            provisional=shift.status != "completed",
            hours_submitted=len(rec.hours),
            hours_total=len(plan.slots),
            revision=shift.revision,
            computed_at=now,
        ),
        model=ShiftModelSnapshot(
            calendar_min=config.duration_min,
            planned_min=plan.planned_min,
            ideal_cycle_s=plan.ideal_cycle_s,
            target_oee=goal,
        ),
        kpi=Kpi(
            availability=total.availability,
            performance=total.performance,
            quality=total.quality,
            oee=total.oee,
            oee_gap_pp=total.goal_gap_pp(goal),
            oee_status=goal_status(total.oee, goal),
        ),
        target_vs_actual=TargetVsActual(
            target_pcs=total.target,
            produced_pcs=total.produced,
            rejects_pcs=total.rejects,
            good_pcs=total.good,
            production_vs_target=ratio(total.produced, total.target),
            good_vs_target=ratio(total.good, total.target),
            deviation_from_target_pcs=total.deviation,
            oee_goal_pcs=total.target * goal,
        ),
        waterfall_pcs=Waterfall(
            target=total.target,
            technical_losses=total.technical_loss,
            speed_loss=total.speed_loss,
            quality_loss=total.quality_loss,
            good=total.good,
        ),
        technical_losses=TechnicalLosses(
            total_min=total.downtime_min,
            events=downtime.event_count,
            share_of_target=ratio(total.technical_loss, total.target),
            by_category=tuple(by_category),
        ),
        speed_loss=SpeedLoss(pcs=total.speed_loss, decomposition_s=None),
        quality=QualityBlock(
            rejects=total.rejects,
            reject_rate=ratio(total.rejects, total.produced),
            by_defect=tuple(DefectQty(code=code, qty=qty) for code, qty in defect_qty.items()),
            by_hour=tuple(r.rejects for r in hour_rows),
        ),
        hourly=tuple(hour_rows),
        issues=tuple(issue_rows),
        loss_pareto=tuple(
            ParetoBucket(
                bucket=b.bucket,
                kind=b.kind,
                pcs=b.pcs,
                share_of_losses=b.share_of_losses,
                category=b.category,
            )
            for b in pareto
        ),
        data_quality=tuple(data_quality),
    )


# --- obdobie (TASK §8.1–8.6, §10.3) -------------------------------------------------------------

UNSPECIFIED_NAME = "Unspecified defect"


def _week_key(day: date) -> str:
    iso = day.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


@dataclass
class _ProblemAcc:
    """Súhrn jedného kódu problému za obdobie."""

    kind: Kind
    lost: float = 0.0
    minutes: float = 0.0
    records: int = 0
    roots: set[str] = field(default_factory=set)
    last: date | None = None
    weekly: dict[str, list[float]] = field(default_factory=dict)
    """Týždeň → [stratené kusy, frekvencia]."""

    @property
    def frequency(self) -> int:
        return len(self.roots) if self.kind == "downtime" else self.records

    def add(self, day: date, lost: float, freq: int) -> None:
        self.lost += lost
        self.last = day if self.last is None or day > self.last else self.last
        week = self.weekly.setdefault(_week_key(day), [0.0, 0])
        week[0] += lost
        week[1] += freq


def _problems(cores: Sequence[_ShiftCore]) -> dict[str, _ProblemAcc]:
    acc: dict[str, _ProblemAcc] = {}
    for core in cores:
        day = core.rec.shift.date
        segments = core.segments
        for e in core.rec.issues:
            seg = segments[e.issue_id]
            a = acc.setdefault(e.issue_type_code, _ProblemAcc("downtime"))
            new_root = seg.root_id not in a.roots
            a.roots.add(seg.root_id)
            a.minutes += seg.counted_min
            a.add(day, seg.counted_min * core.pcs_per_min, 1 if new_root else 0)
        for q in core.rec.quality:
            a = acc.setdefault(q.defect_type_code or UNSPECIFIED, _ProblemAcc("quality"))
            a.records += 1
            a.roots.add(q.quality_id)
            a.add(day, float(q.qty), 1)
    return acc


def _weeks(cores: Sequence[_ShiftCore], start: date, end: date) -> list[tuple[str, list[_ShiftCore], bool]]:
    """ISO týždne obdobia; úplný = každý pracovný deň (zo snapshotov) v rámci obdobia má dokončenú zmenu."""
    by_week: dict[str, list[_ShiftCore]] = defaultdict(list)
    for core in cores:
        by_week[_week_key(core.rec.shift.date)].append(core)
    out = []
    for key in sorted(by_week):
        week_cores = by_week[key]
        complete = is_week_complete(
            done={c.rec.shift.date for c in week_cores},
            working_days=set().union(*(c.config.working_days for c in week_cores)),
            start=start,
            end=end,
        )
        out.append((key, week_cores, complete))
    return out


def _links(
    session: Session, cores: Sequence[_ShiftCore], problems: Mapping[str, _ProblemAcc], catalog: Catalog
) -> list[ProblemLink]:
    stop_codes = set(
        session.scalars(select(IssueType.code).where(IssueType.active_top10, IssueType.is_other.is_(False)))
    )
    defect_codes = set(
        session.scalars(
            select(DefectType.code).where(DefectType.active_top10, DefectType.is_other.is_(False))
        )
    )
    hours: list[HourObs] = []
    events: dict[str, tuple[str, str, set[int]]] = {}
    for core in cores:
        sid = core.rec.shift.shift_id
        hour_no = core.rec.hour_no_by_id
        defects: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for q in core.rec.quality:
            if q.defect_type_code:
                defects[q.hour_id][q.defect_type_code] += q.qty
        hours += [
            HourObs(sid, no, prod.produced_qty, dict(defects[row.hour_id]))
            for no, (row, prod) in core.rec.hours.items()
        ]
        segments = core.segments
        codes = {e.issue_id: e.issue_type_code for e in core.rec.issues}
        for e in core.rec.issues:
            root = segments[e.issue_id].root_id
            events.setdefault(root, (codes.get(root, e.issue_type_code), sid, set()))[2].add(
                hour_no[e.hour_id]
            )
    same_process = {
        (st, q): process
        for st in stop_codes
        for q in defect_codes
        if (process := catalog.link_type(st, q)[1]) is not None
    }
    results = find_problem_links(
        hours,
        [StopEvent(root, code, sid, tuple(sorted(hrs))) for root, (code, sid, hrs) in events.items()],
        stop_codes=stop_codes,
        defect_codes=defect_codes,
        same_process=same_process,
        stop_lost_pcs={code: a.lost for code, a in problems.items() if a.kind == "downtime"},
    )
    return [
        ProblemLink(
            cause=r.cause,
            effect=r.effect,
            window=r.window,
            support=r.support,
            q_in_window=r.q_in_window,
            produced_in_window=r.produced_in_window,
            rate_in_window=r.rate_in_window or 0.0,
            base_rate=r.base_rate or 0.0,
            lift=r.lift,
            extra_rejects=r.extra_rejects,
            link_type=r.link_type,
            process=r.process,
            confidence=r.confidence,
            combined_impact_pcs=r.combined_impact_pcs,
            evidence=r.evidence,
        )
        for r in results
        if r.is_link
    ]


def _ranking_rows(
    ranked: Sequence[RankedProblem],
    problems: Mapping[str, _ProblemAcc],
    describe: Callable[[str], tuple[str, str]],
) -> tuple[RankingRow, ...]:
    rows = []
    for r in ranked:
        a = problems[r.code]
        is_stop = r.kind == "downtime"
        name, category = describe(r.code)
        rows.append(
            RankingRow(
                rank=r.rank,
                class_=r.abc_class,
                kind=r.kind,
                code=r.code,
                name=name,
                category=category,
                events=r.frequency,
                total_min=a.minutes if is_stop else None,
                avg_min=a.minutes / r.frequency if is_stop and r.frequency else None,
                lost_pcs=r.lost_pcs,
                share_of_recorded=r.share_of_recorded,
                share_of_all_losses=r.share_of_all_losses,
                kpi_impact=KpiImpact(kpi=r.kpi, pp=r.kpi_impact_pp or 0.0),
                trend=r.trend,
                trend_change=r.trend_change,
                recurring=False,  # odznak určujú Patterns (P1, TASK §8.5)
                last_occurrence=r.last_occurrence,
                evidence=tuple(sorted(a.roots)),
            )
        )
    return tuple(rows)


def build_period(
    session: Session,
    start: date,
    end: date,
    *,
    line: str,
    period_type: PeriodType,
    catalog: Catalog,
    now: datetime,
) -> PeriodAnalytics:
    """`PeriodAnalytics` (TASK §10.3) za dokončené zmeny linky v dňoch `start`–`end` (vrátane).

    Agregácia iba cez súčty (D8): target = Σ targetov, cieľ OEE = Σ (target × cieľ) / Σ target.
    Zmeny, ktoré nie sú `completed`, sa vylúčia a spočítajú v `shifts_excluded_incomplete`.
    `now` sa zatiaľ nepoužíva (stav `incomplete` vyhodnocuje P0-14); ostáva kvôli jednotnému API.
    """
    shifts = list(
        session.scalars(
            select(Shift)
            .where(Shift.line_id == line, Shift.date >= start, Shift.date <= end)
            .order_by(Shift.date)
        )
    )
    cores = [_compute(session, s.shift_id, catalog) for s in shifts if s.status == "completed"]
    total = sum_cascades(c.total for c in cores)
    goal_pcs = sum(c.total.target * c.goal for c in cores)
    goal = period_goal((c.total.target, c.goal) for c in cores)
    losses = total.target - total.good

    fpq = first_pass_quality(
        good=total.good,
        produced=total.produced,
        retests=[prod.retests for c in cores for _, prod in c.rec.hours.values()],
    )

    weeks = _weeks(cores, start, end)
    problems = _problems(cores)
    ranked = rank_problems(
        [
            ProblemStats(
                code, a.kind, a.lost, a.frequency, a.last, {k: (v[0], int(v[1])) for k, v in a.weekly.items()}
            )
            for code, a in problems.items()
        ],
        [WeekInfo(key, complete, len(wc)) for key, wc, complete in weeks],
        period_target=total.target,
        all_losses=losses,
    )
    types: dict[str, IssueType | DefectType] = {}
    for c in cores:
        types |= c.rec.issue_types
        types |= c.rec.defect_types

    def describe(code: str) -> tuple[str, str]:
        t = types.get(code)
        if t is None:
            return UNSPECIFIED_NAME, UNSPECIFIED_NAME
        return t.name_en, catalog.categories.get(t.category, t.category)

    by_hour: dict[int, list[Cascade]] = defaultdict(list)
    for c in cores:
        for no, cascade in c.cascades.items():
            by_hour[no].append(cascade)
    week_totals = [(wc, complete, sum_cascades(c.total for c in wc)) for _, wc, complete in weeks]
    hour_totals = [(no, sum_cascades(cs)) for no, cs in sorted(by_hour.items())]
    stops = sorted(
        ((k, v) for k, v in problems.items() if v.kind == "downtime"),
        key=lambda kv: (-kv[1].minutes, -kv[1].frequency, kv[0]),
    )
    defects = sorted(
        ((k, v) for k, v in problems.items() if v.kind == "quality" and k != UNSPECIFIED),
        key=lambda kv: (-kv[1].lost, -kv[1].records, kv[0]),
    )

    return PeriodAnalytics(
        period=PeriodInfo(
            type=period_type,
            from_=start,
            to=end,
            line=line,
            shifts_completed=len(cores),
            shifts_excluded_incomplete=len(shifts) - len(cores),
        ),
        kpi=Kpi(
            availability=total.availability,
            performance=total.performance,
            quality=total.quality,
            oee=total.oee,
            oee_gap_pp=None if goal is None else total.goal_gap_pp(goal),
            oee_status=None if goal is None else goal_status(total.oee, goal),
            first_pass_quality=fpq,
        ),
        totals=Totals(
            planned_min=total.planned_min,
            target_pcs=total.target,
            oee_goal_pcs=goal_pcs,
            downtime_min=total.downtime_min,
            downtime_events=sum(c.downtime.event_count for c in cores),
            produced=total.produced,
            rejects=total.rejects,
            good=total.good,
            speed_loss_pcs=total.speed_loss,
            production_vs_target=ratio(total.produced, total.target),
            deviation_from_target_pcs=total.deviation,
        ),
        waterfall_pcs=Waterfall(
            target=total.target,
            technical_losses=total.technical_loss,
            speed_loss=total.speed_loss,
            quality_loss=total.quality_loss,
            good=total.good,
        ),
        shift_series=tuple(
            ShiftPoint(
                shift_id=c.rec.shift.shift_id,
                date=c.rec.shift.date,
                oee=c.total.oee,
                status=goal_status(c.total.oee, c.goal) or "below_goal",
            )
            for c in cores
        ),
        weekly=tuple(
            WeekRow(
                iso_week=wc[0].rec.shift.date.isocalendar().week,
                from_=min(c.rec.shift.date for c in wc),
                to=max(c.rec.shift.date for c in wc),
                shifts=len(wc),
                partial=not complete,
                oee=wk.oee,
                availability=wk.availability,
                performance=wk.performance,
                quality=wk.quality,
            )
            for wc, complete, wk in week_totals
        ),
        issue_stats=tuple(
            IssueStat(
                code=code,
                category=describe(code)[1],
                events=a.frequency,
                total_min=a.minutes,
                avg_min=a.minutes / a.frequency if a.frequency else 0.0,
                lost_pcs=a.lost,
            )
            for code, a in stops
        ),
        defect_stats=tuple(DefectStat(code=code, records=a.records, qty=int(a.lost)) for code, a in defects),
        unattributed_speed_loss=UnattributedSpeedLoss(
            pcs=total.speed_loss,
            share_of_all_losses=ratio(total.speed_loss, losses),
            by_hour_of_shift=tuple(
                HourOfShiftSpeedLoss(hour_no=no, pcs=h.speed_loss, performance=h.performance)
                for no, h in hour_totals
            ),
        ),
        problem_ranking=_ranking_rows(ranked, problems, describe),
        problem_links=tuple(_links(session, cores, problems, catalog)),
        data_quality=tuple(dq for c in cores for dq in c.data_quality),
    )

"""Validácia hodinového hlásenia — pravidlá V1–V12, V14 (TASK §5.5, PLANNING D10).

Čistá funkcia: vstup = hodina + udalosti ostatných hodín zmeny (pre V7 a pokračovania) + aktívne kódy
(parameter, bez DB). Výstup = správy `{level, rule, field, message}`; chyby blokujú uloženie, varovania
nastavia `needs_attention`.

Poznámky:
- V2/V3 majú toleranciu +1 ks na hodinu (kus na hranici slotov, TASK §3.4 pravidlo 8).
- V5 kontroluje **nahlásené** minúty (zjednotenie časovaných + súčet nečasovaných) pred stropom z `downtime`.
- V6 navyše varuje, keď časovaná udalosť presahuje koniec hodiny a nemá pokračovanie (D10) — inak by sa zvyšok
  nezapočítal.
- V9 (idempotencia) a V14 (jeden záznam na hodinu) vynucuje aj perzistencia; tu sa overí prítomnosť
  `client_key`, jeho jedinečnosť v hodine a to, že hodina patrí do zmeny.
- V11: „Other" vyžaduje komentár pri prestojoch aj pri zmätkoch.
"""

from __future__ import annotations

import math
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from oee.domain.downtime import DowntimeEvent, count_downtime
from oee.domain.kpi import EPS, Cascade
from oee.domain.shift_model import HourSlot, ShiftPlan

TOLERANCE_PCS = 1  # TASK §5.5 V2/V3: +1 ks na hodinu
_EPS = EPS

Level = Literal["error", "warning"]


@dataclass(frozen=True)
class IssueInput:
    """Udalosť (segment) prestoja tak, ako ju nahlásil operátor."""

    key: str
    """Identita udalosti (issue_id alebo client_key) — na ňu odkazuje `continues_key`."""
    client_key: str | None
    code: str
    duration_min: float
    start: datetime | None = None
    continues_key: str | None = None
    comment: str | None = None


@dataclass(frozen=True)
class RejectLine:
    code: str
    qty: int
    comment: str | None = None


@dataclass(frozen=True)
class HourInput:
    hour_no: int
    produced: int | None
    rejects: int | None
    rejects_by_defect: tuple[RejectLine, ...] = ()
    issues: tuple[IssueInput, ...] = ()


@dataclass(frozen=True)
class ActiveCodes:
    """Kódy, ktoré operátor smie vybrať (Top-10 + „Other"); zdroj = katalóg / Settings."""

    stop_codes: frozenset[str]
    defect_codes: frozenset[str]
    other_stop_code: str
    other_defect_code: str


@dataclass(frozen=True)
class ValidationMessage:
    level: Level
    rule: str
    field: str
    message: str


def speed_loss_exceeds_tolerance(cascade: Cascade) -> bool:
    """V3: vyrobené prevyšuje možné v čase chodu o viac ako toleranciu (S < −1 ks, TASK §3.4 pravidlo 8)."""
    return cascade.speed_loss < -TOLERANCE_PCS - EPS


def has_errors(messages: Sequence[ValidationMessage]) -> bool:
    return any(m.level == "error" for m in messages)


# --- pomocné ------------------------------------------------------------------------------------


def _err(rule: str, field: str, message: str) -> ValidationMessage:
    return ValidationMessage("error", rule, field, message)


def _warn(rule: str, field: str, message: str) -> ValidationMessage:
    return ValidationMessage("warning", rule, field, message)


def _valid_duration(d: float) -> bool:
    return math.isfinite(d) and d > 0


def _interval(issue: IssueInput) -> tuple[datetime, datetime] | None:
    if issue.start is None or not _valid_duration(issue.duration_min):
        return None
    return issue.start, issue.start + timedelta(minutes=issue.duration_min)


def _overlaps(a: tuple[datetime, datetime], b: tuple[datetime, datetime]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def _blank(text: str | None) -> bool:
    return text is None or not text.strip()


def _as_events(slot: HourSlot, issues: Sequence[IssueInput]) -> list[DowntimeEvent]:
    return [
        DowntimeEvent(event_id=str(i), hour_no=slot.hour_no, duration_min=x.duration_min, start=x.start)
        for i, x in enumerate(issues)
    ]


def _hour_downtime(plan: ShiftPlan, slot: HourSlot, issues: Sequence[IssueInput]) -> float:
    return count_downtime(plan, _as_events(slot, issues)).hours[slot.hour_no - 1].downtime_min


# --- pravidlá -----------------------------------------------------------------------------------


def _production_rules(plan: ShiftPlan, slot: HourSlot, hour: HourInput) -> Iterator[ValidationMessage]:
    produced = hour.produced
    if produced is None or produced < 0:
        yield _err("V1", "produced", "Produced is required and must be a whole number ≥ 0")
        produced = None
    elif produced > slot.target + TOLERANCE_PCS + _EPS:
        yield _err(
            "V2",
            "produced",
            f"Produced exceeds hourly target {slot.target:g} + {TOLERANCE_PCS} (physically impossible)",
        )
    elif hour.issues or produced > 0:
        downtime = _hour_downtime(plan, slot, hour.issues)
        cascade = Cascade.from_minutes(
            planned_min=slot.planned_min,
            downtime_min=downtime,
            produced=produced,
            rejects=0,
            ideal_cycle_s=plan.ideal_cycle_s,
        )
        if speed_loss_exceeds_tolerance(cascade):
            yield _warn(
                "V3",
                "produced",
                "Produced exceeds what is possible in run time — downtime overstated or quantity wrong?",
            )

    if produced == 0 and not hour.issues:
        yield _warn("V12", "produced", "No production and no problem reported")

    rejects = hour.rejects
    if rejects is None or rejects < 0:
        yield _err("V10", "rejects", "Rejects is required and must be a whole number ≥ 0")
        rejects = None
    elif produced is not None and rejects > produced:
        yield _err("V10", "rejects", "Rejects must not exceed Produced")

    for i, line in enumerate(hour.rejects_by_defect):
        if line.qty <= 0:
            yield _err("V10", f"rejects_by_defect[{i}].qty", "Quantity must be greater than 0")
    if hour.rejects_by_defect and rejects is not None:
        total = sum(line.qty for line in hour.rejects_by_defect)
        if total != rejects:
            yield _err("V10", "rejects_by_defect", f"Breakdown sums to {total}, but Rejects is {rejects}")


def _code_rules(hour: HourInput, codes: ActiveCodes) -> Iterator[ValidationMessage]:
    allowed_stops = codes.stop_codes | {codes.other_stop_code}
    for i, x in enumerate(hour.issues):
        if x.code not in allowed_stops:
            yield _err("V11", f"issues[{i}].code", "Choose a problem type from the codebook or Other")
        elif x.code == codes.other_stop_code and _blank(x.comment):
            yield _err("V11", f"issues[{i}].comment", "A comment is required for Other")

    allowed_defects = codes.defect_codes | {codes.other_defect_code}
    for i, line in enumerate(hour.rejects_by_defect):
        if line.code not in allowed_defects:
            yield _err(
                "V11",
                f"rejects_by_defect[{i}].code",
                "Choose a defect type from the codebook or Other",
            )
        elif line.code == codes.other_defect_code and _blank(line.comment):
            yield _err("V11", f"rejects_by_defect[{i}].comment", "A comment is required for Other")


def _issue_rules(
    plan: ShiftPlan, slot: HourSlot, hour: HourInput, other_issues: Sequence[IssueInput]
) -> Iterator[ValidationMessage]:
    issues = hour.issues
    hour_keys = {x.key for x in issues}
    others = [o for o in other_issues if o.key not in hour_keys]
    continued = {x.continues_key for x in [*issues, *others] if x.continues_key is not None}

    seen_client_keys: set[str] = set()
    for i, x in enumerate(issues):
        # V4
        if not _valid_duration(x.duration_min):
            yield _err("V4", f"issues[{i}].duration_min", "Duration must be greater than 0 minutes")
        elif x.duration_min > slot.planned_min + _EPS:
            yield _err(
                "V4",
                f"issues[{i}].duration_min",
                f"Duration exceeds planned minutes of this hour ({slot.planned_min})",
            )
        # V6
        if x.start is not None:
            if not slot.start <= x.start < slot.end:
                yield _err("V6", f"issues[{i}].start_time", "Start time must be within this hour")
            else:
                if any(w0 <= x.start < w1 for w0, w1 in slot.allowance_windows):
                    yield _warn(
                        "V6",
                        f"issues[{i}].start_time",
                        "Starts during break / AM — those minutes are not counted",
                    )
                iv = _interval(x)
                if iv is not None and iv[1] > slot.end and x.key not in continued:
                    yield _warn(
                        "V6",
                        f"issues[{i}].duration_min",
                        "Extends past the end of the hour — add a continuation in the next hour",
                    )
        # V9
        if _blank(x.client_key):
            yield _err("V9", f"issues[{i}].client_key", "Missing idempotency key")
        else:
            assert x.client_key is not None
            if x.client_key in seen_client_keys:
                yield _err("V9", f"issues[{i}].client_key", "Duplicate idempotency key in this hour")
            seen_client_keys.add(x.client_key)

    # V5 — nahlásené minúty (pred stropom)
    timed = [x for x in issues if x.start is not None and _valid_duration(x.duration_min)]
    untimed_total = sum(x.duration_min for x in issues if x.start is None and _valid_duration(x.duration_min))
    reported = _hour_downtime(plan, slot, timed) + untimed_total
    if reported > slot.planned_min + _EPS:
        yield _err(
            "V5",
            "issues",
            f"Problem minutes ({reported:g}) exceed planned minutes of this hour ({slot.planned_min})",
        )

    # V7 — prekryvy v hodine a naprieč zmenou. Udalosť a jej vlastné pokračovanie sa neporovnávajú:
    # čas za koncom hodiny patrí pokračovaniu (D10), `downtime` ho v pôvodnej hodine oreže.
    def conflicts(x: IssueInput, candidates: Sequence[IssueInput]) -> bool:
        iv = _interval(x)
        return iv is not None and any(
            (other := _interval(c)) is not None
            and _overlaps(iv, other)
            and c.continues_key != x.key
            and x.continues_key != c.key
            for c in candidates
        )

    for j, x in enumerate(issues):
        if conflicts(x, [*issues[:j], *others]):
            yield _err(
                "V7",
                f"issues[{j}].start_time",
                "Overlaps another problem — choose the main cause or fix the time",
            )

    # V8 — možný duplikát
    for j, x in enumerate(issues):
        if x.start is not None:
            continue
        for i in range(j):
            y = issues[i]
            if y.start is None and y.code == x.code and y.duration_min == x.duration_min:
                yield _warn("V8", f"issues[{j}]", "Possible duplicate of another problem in this hour")
                break


def validate_hour(
    plan: ShiftPlan, hour: HourInput, other_issues: Sequence[IssueInput], codes: ActiveCodes
) -> list[ValidationMessage]:
    """Všetky správy validácie hodiny; chyby sú pred varovaniami."""
    slots = {s.hour_no: s for s in plan.slots}
    slot = slots.get(hour.hour_no)
    if slot is None:
        return [_err("V14", "hour_no", f"Hour {hour.hour_no} is not part of this shift (1–{len(slots)})")]

    messages = [
        *_production_rules(plan, slot, hour),
        *_issue_rules(plan, slot, hour, other_issues),
        *_code_rules(hour, codes),
    ]
    return sorted(messages, key=lambda m: m.level != "error")

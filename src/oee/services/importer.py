"""Import Excel datasetu (TASK §11, PLANNING P0-09, ARCHITECTURE §10.4).

- Súbor sa iba ČÍTA (`read_only=True, data_only=True`, vždy `close()`), nikdy neukladá (CLAUDE.md pravidlo 9).
- Stĺpce sa mapujú podľa názvov v 1. riadku (v read-only režime `ws.tables` neexistuje).
- **Model každej zmeny sa odvodí zo súboru** (výkon = 3600 / `Ideal_cyklus_s`, začiatok = `Cas_od` 1. hodiny,
  dĺžka = Σ `Interval_min`, AM a prestávka z ich hodín, cieľ OEE z `Dashboard!E51`,
  pracovné dni = dni v súbore). Nastavenia v Settings sa nemenia.
- Prirodzené kľúče (`hour_id`, `external_ref`): opakovaný import nič nepridá; existujúca hodina
  (napr. ručne zadaná) sa nemení.
- Celý import = jedna transakcia (chyba → rollback, `DatasetError`).
- Kontroly TASK §11.7 sa vrátia v `ImportResult.checks`; stĺpce s cache hodnotami sú voliteľné
  (chýbajú → kontrola = None).
"""

from __future__ import annotations

import math
import warnings
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import openpyxl
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from oee.domain.downtime import DowntimeEvent, count_downtime
from oee.domain.kpi import SECONDS_PER_MINUTE, Cascade, sum_cascades
from oee.domain.shift_model import (
    MINUTES_PER_HOUR,
    SECONDS_PER_HOUR,
    Allowance,
    ShiftModelConfig,
    ShiftPlan,
    build_shift_plan,
    config_to_snapshot,
    validate_shift_model,
)
from oee.persistence.models import (
    DefectType,
    HourlyReportRow,
    IssueEvent,
    IssueType,
    ProductionRecord,
    Shift,
)
from oee.persistence.repositories import QualityInvariantError, QualityLine, replace_hour_quality
from oee.services.reporting import SHIFT_CODE  # TASK §11.8: shift_id = {Linka}-{YYYYMMDD}-M

SOURCE = "import"
GOAL_CELL = ("Dashboard", "E51")
_TOL = 1e-6

VYROBA_REQUIRED = (
    "Hodina_ID", "Datum", "Linka", "Produkt", "Hodina_zmeny", "Cas_od", "Cas_do", "Interval_min", "AM_min",
    "Pauza_min", "Ideal_cyklus_s", "Vyrobene_ks", "NOK_ks",
)  # fmt: skip
PRESTOJE_REQUIRED = ("Kod_chyby", "Hodina_ID", "Cas_od", "Cas_do")
NOK_REQUIRED = ("NOK_ID", "Hodina_ID", "NOK_ks", "Kod_chyby")

Row = dict[str, Any]


class DatasetError(ValueError):
    """Súbor sa nedá importovať (chýba stĺpec, neznámy kód, nekonzistentné dáta …)."""


@dataclass(frozen=True)
class ShiftCheck:
    """Kontroly TASK §11.7 pre jednu zmenu; None = nedá sa overiť (chýba stĺpec s cache hodnotou)."""

    shift_id: str
    checks: Mapping[str, bool | None]

    @property
    def ok(self) -> bool:
        return all(v is not False for v in self.checks.values())


@dataclass
class ImportResult:
    shifts_added: int = 0
    hours_added: int = 0
    issues_added: int = 0
    quality_added: int = 0
    hours_skipped: int = 0
    models: dict[str, ShiftModelConfig] = field(default_factory=dict)
    checks: list[ShiftCheck] = field(default_factory=list)


@dataclass
class _Dataset:
    hours: list[Row]
    stops: list[Row]
    defects: list[Row]
    target_oee: float
    shift_summary: dict[date, Row]


# --- čítanie ------------------------------------------------------------------------------------


def _sheet_rows(wb: Any, name: str, required: Iterable[str], *, optional: bool = False) -> list[Row]:
    if name not in wb.sheetnames:
        if optional:
            return []
        raise DatasetError(f"sheet {name!r} is missing")
    rows = wb[name].iter_rows(values_only=True)
    header = [str(h).strip() if h is not None else "" for h in next(rows, ())]
    missing = [c for c in required if c not in header]
    if missing:
        raise DatasetError(f"sheet {name!r}: missing column(s) {', '.join(missing)}")
    return [dict(zip(header, r, strict=False)) for r in rows if any(v is not None for v in r)]


def _read(path: Path) -> _Dataset:
    if not path.is_file():
        raise DatasetError(f"file not found: {path}")
    with warnings.catch_warnings():
        # nepodporované rozšírenia (grafy, podmienené formáty);
        # v read-only režime sa hlásia až pri čítaní riadkov
        warnings.simplefilter("ignore", UserWarning)
        return _read_workbook(path)


def _read_workbook(path: Path) -> _Dataset:
    try:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    except Exception as exc:  # poškodený / nie xlsx
        raise DatasetError(f"cannot open workbook: {exc}") from exc
    try:
        hours = _sheet_rows(wb, "Vyroba_hodiny", VYROBA_REQUIRED)
        stops = _sheet_rows(wb, "Prestoje", PRESTOJE_REQUIRED)
        defects = _sheet_rows(wb, "NOK_detail", NOK_REQUIRED)
        summary = _sheet_rows(wb, "Kontrola_zmien", ("Datum",), optional=True)
        sheet, cell = GOAL_CELL
        goal = wb[sheet][cell].value if sheet in wb.sheetnames else None
    finally:
        wb.close()
    if not isinstance(goal, int | float) or isinstance(goal, bool):
        raise DatasetError(f"OEE goal missing in {sheet}!{cell}")
    return _Dataset(
        hours=hours,
        stops=stops,
        defects=defects,
        target_oee=float(goal),
        shift_summary={
            _as_date(r["Datum"]): r for r in summary if isinstance(r.get("Datum"), datetime | date)
        },
    )


# --- prevody a validácia hodnôt -----------------------------------------------------------------


def _as_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raise DatasetError(f"invalid date {value!r}")


def _as_dt(value: Any, what: str) -> datetime:
    if not isinstance(value, datetime):
        raise DatasetError(f"{what}: invalid date/time {value!r}")
    return value


def _as_int(row: Row, col: str, ref: str, *, minimum: int = 0) -> int:
    value = row.get(col)
    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or value != int(value)
        or value < minimum
    ):
        raise DatasetError(f"{ref}: {col} must be a whole number ≥ {minimum}, got {value!r}")
    return int(value)


def _as_float(row: Row, col: str) -> float | None:
    value = row.get(col)
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def _duration_min(start: datetime, end: datetime) -> float:
    """Trvanie zaokrúhlené na celé sekundy (Excel serial → datetime má mikrosekundové odchýlky)."""
    return round((end - start).total_seconds()) / 60


# --- odvodenie modelu zmeny ---------------------------------------------------------------------


def _allowance(hours: list[Row], col: str, shift_id: str) -> Allowance:
    used = [(int(h["Hodina_zmeny"]), _as_int(h, col, h["Hodina_ID"])) for h in hours if (h.get(col) or 0) > 0]
    if len(used) > 1:
        raise DatasetError(f"{shift_id}: {col} appears in more than one hour")
    if not used:
        return Allowance(minutes=0, hour_no=1)
    hour_no, minutes = used[0]
    return Allowance(minutes=minutes, hour_no=hour_no, offset_min=0)  # posun = začiatok hodiny (TASK §3.1)


def _derive_model(
    shift_id: str, hours: list[Row], target_oee: float, working_days: frozenset[int]
) -> ShiftModelConfig:
    numbers = [int(h["Hodina_zmeny"]) for h in hours]
    if numbers != list(range(1, len(hours) + 1)):
        raise DatasetError(f"{shift_id}: shift hours must be 1..N without gaps, got {numbers}")
    for h in hours:
        if h["Interval_min"] != MINUTES_PER_HOUR:
            raise DatasetError(f"{h['Hodina_ID']}: Interval_min must be {MINUTES_PER_HOUR} (hourly slots)")
    cycles = {_as_float(h, "Ideal_cyklus_s") for h in hours}
    if len(cycles) != 1 or None in cycles or not (cycle := cycles.pop()) or cycle <= 0:
        raise DatasetError(f"{shift_id}: Ideal_cyklus_s must be one positive value per shift")
    config = ShiftModelConfig(
        rate_per_hour=SECONDS_PER_HOUR / cycle,
        start=_as_dt(hours[0]["Cas_od"], hours[0]["Hodina_ID"]).time(),
        duration_min=sum(int(h["Interval_min"]) for h in hours),
        break_=_allowance(hours, "Pauza_min", shift_id),
        am=_allowance(hours, "AM_min", shift_id),
        target_oee=target_oee,
        working_days=working_days,
    )
    issues = validate_shift_model(config)
    if issues:
        raise DatasetError(
            f"{shift_id}: invalid shift model — " + "; ".join(f"{i.field}: {i.message}" for i in issues)
        )
    return config


# --- kontroly §11.7 -----------------------------------------------------------------------------


def _check_shift(
    shift_id: str,
    plan: ShiftPlan,
    hours: list[Row],
    stops_by_hour: Mapping[str, list[Row]],
    summary: Row | None,
) -> ShiftCheck:
    events = [
        DowntimeEvent(
            event_id=f"{s['Hodina_ID']}|{i}",
            hour_no=int(h["Hodina_zmeny"]),
            duration_min=_duration_min(s["Cas_od"], s["Cas_do"]),
            start=s["Cas_od"],
        )
        for h in hours
        for i, s in enumerate(stops_by_hour.get(h["Hodina_ID"], []))
    ]
    downtime = count_downtime(plan, events)

    plan_ok = downtime_ok = balance_ok = kontrola_ok = kpi_ok = True
    balance_known = kontrola_known = True
    cascades: list[Cascade] = []
    for h, slot, dt in zip(hours, plan.slots, downtime.hours, strict=True):
        file_plan = h["Interval_min"] - (h.get("AM_min") or 0) - (h.get("Pauza_min") or 0)
        cached_plan = _as_float(h, "Plan_min")
        plan_ok &= math.isclose(file_plan, slot.planned_min) and (
            cached_plan is None or math.isclose(cached_plan, slot.planned_min)
        )

        raw_minutes = sum(
            _duration_min(s["Cas_od"], s["Cas_do"]) for s in stops_by_hour.get(h["Hodina_ID"], [])
        )
        cached_down = _as_float(h, "Prestoj_min")
        downtime_ok &= math.isclose(raw_minutes, dt.downtime_min, abs_tol=_TOL) and (
            cached_down is None or math.isclose(cached_down, raw_minutes, abs_tol=_TOL)
        )

        produced, rejects = int(h["Vyrobene_ks"]), int(h["NOK_ks"])
        parts = [_as_float(h, c) for c in ("Mikrostop_s", "Retest_cas_s", "Spomalenie_s")]
        if None in parts:
            balance_known = False
        else:
            run_s = (slot.planned_min - dt.downtime_min) * SECONDS_PER_MINUTE
            balance = run_s - produced * plan.ideal_cycle_s - sum(p or 0 for p in parts)
            balance_ok &= abs(balance) < _TOL

        ok_cached = _as_float(h, "OK_ks")
        if ok_cached is None:
            kontrola_known = False
        else:
            kontrola_ok &= produced - ok_cached - rejects == 0

        c = Cascade.from_minutes(
            planned_min=slot.planned_min,
            downtime_min=dt.downtime_min,
            produced=produced,
            rejects=rejects,
            ideal_cycle_s=plan.ideal_cycle_s,
        )
        cascades.append(c)
        kpi_ok &= all(v is None or -_TOL <= v <= 1 + _TOL for v in (c.availability, c.performance, c.quality))

    shift_oee = sum_cascades(cascades).oee
    summary_ok: bool | None = None
    if summary is not None:
        cached_oee = _as_float(summary, "OEE")
        summary_ok = summary.get("Kontrola") in (None, "SEDI") and (
            cached_oee is None
            or (shift_oee is not None and math.isclose(cached_oee, shift_oee, abs_tol=1e-9))
        )
    return ShiftCheck(
        shift_id=shift_id,
        checks={
            "plan_min": plan_ok,
            "downtime": downtime_ok,
            "balance_s": balance_ok if balance_known else None,
            "kontrola_ks": kontrola_ok if kontrola_known else None,
            "kpi_range": kpi_ok,
            "kontrola_zmien": summary_ok,
        },
    )


# --- zápis --------------------------------------------------------------------------------------


def _group(rows: Iterable[Row], key: str) -> dict[str, list[Row]]:
    out: dict[str, list[Row]] = defaultdict(list)
    for r in rows:
        out[str(r[key])].append(r)
    return out


def _import(session: Session, data: _Dataset, now: datetime) -> ImportResult:
    result = ImportResult()
    known_stops = set(session.scalars(select(IssueType.code)))
    known_defects = set(session.scalars(select(DefectType.code)))
    hour_ids = {str(h["Hodina_ID"]) for h in data.hours}

    for s in data.stops:
        if s["Kod_chyby"] not in known_stops:
            raise DatasetError(f"Prestoje: unknown stop code {s['Kod_chyby']} ({s['Hodina_ID']})")
        if str(s["Hodina_ID"]) not in hour_ids:
            raise DatasetError(f"Prestoje: unknown hour {s['Hodina_ID']}")
        _as_dt(s["Cas_od"], str(s["Hodina_ID"]))
        _as_dt(s["Cas_do"], str(s["Hodina_ID"]))
    for d in data.defects:
        if d["Kod_chyby"] not in known_defects:
            raise DatasetError(f"NOK_detail: unknown defect code {d['Kod_chyby']} ({d['NOK_ID']})")
        if str(d["Hodina_ID"]) not in hour_ids:
            raise DatasetError(f"NOK_detail: unknown hour {d['Hodina_ID']}")
        _as_int(d, "NOK_ks", str(d["NOK_ID"]), minimum=1)

    stops_by_hour = _group(data.stops, "Hodina_ID")
    defects_by_hour = _group(data.defects, "Hodina_ID")
    shifts: dict[tuple[str, date], list[Row]] = defaultdict(list)
    for h in data.hours:
        ref = str(h["Hodina_ID"])
        produced = _as_int(h, "Vyrobene_ks", ref)
        rejects = _as_int(h, "NOK_ks", ref)
        if rejects > produced:
            raise DatasetError(f"{ref}: NOK_ks exceeds Vyrobene_ks")
        shifts[(str(h["Linka"]), _as_date(h["Datum"]))].append(h)
    working_days = frozenset(day.weekday() for _, day in shifts)

    for (line, day), rows in sorted(shifts.items()):
        rows.sort(key=lambda r: int(r["Hodina_zmeny"]))
        shift_id = f"{line}-{day:%Y%m%d}-{SHIFT_CODE}"
        model = _derive_model(shift_id, rows, data.target_oee, working_days)
        plan = build_shift_plan(model, day)
        result.models[shift_id] = model
        check = _check_shift(shift_id, plan, rows, stops_by_hour, data.shift_summary.get(day))

        shift = session.get(Shift, shift_id)
        # existujúca zmena si drží svoj snapshot; rozdiel voči súboru sa iba nahlási
        snapshot_ok = shift is None or shift.model_snapshot == config_to_snapshot(model)
        result.checks.append(ShiftCheck(shift_id, {**check.checks, "model_snapshot": snapshot_ok}))
        if shift is None:
            complete = len(rows) == len(plan.slots)
            shift = Shift(
                shift_id=shift_id,
                line_id=line,
                product_id=str(rows[0]["Produkt"]),
                date=day,
                shift_code=SHIFT_CODE,
                model_snapshot=config_to_snapshot(model),
                status="completed" if complete else "in_progress",
                revision=0,
                created_at=now,
                completed_at=now if complete else None,
                updated_at=now,
            )
            session.add(shift)
            result.shifts_added += 1

        for h, slot in zip(rows, plan.slots, strict=True):
            hour_id = str(h["Hodina_ID"])
            if session.get(HourlyReportRow, hour_id) is not None:
                result.hours_skipped += 1
                continue
            session.add(
                HourlyReportRow(
                    hour_id=hour_id,
                    shift_id=shift_id,
                    hour_no=slot.hour_no,
                    slot_start=slot.start,
                    slot_end=slot.end,
                    planned_min=slot.planned_min,
                    status="submitted",
                    submitted_by=SOURCE,
                    submitted_at=now,
                    updated_at=now,
                )
            )
            retests = _as_float(h, "Retesty_pocet")
            session.add(
                ProductionRecord(
                    hour_id=hour_id,
                    produced_qty=int(h["Vyrobene_ks"]),
                    rejects_qty=int(h["NOK_ks"]),
                    retests=None if retests is None else int(retests),
                    microstop_s=_as_float(h, "Mikrostop_s"),
                    slowdown_s=_as_float(h, "Spomalenie_s"),
                    source=SOURCE,
                )
            )
            session.flush()
            result.hours_added += 1

            for s in stops_by_hour.get(hour_id, []):
                start, end = s["Cas_od"], s["Cas_do"]
                session.add(
                    IssueEvent(
                        hour_id=hour_id,
                        issue_type_code=str(s["Kod_chyby"]),
                        start_at=start,
                        duration_min=_duration_min(start, end),
                        source=SOURCE,
                        external_ref=f"{hour_id}|{s['Kod_chyby']}|{start:%H:%M:%S}",
                        created_at=now,
                        updated_at=now,
                    )
                )
                result.issues_added += 1

            lines = [
                QualityLine(str(d["Kod_chyby"]), int(d["NOK_ks"]), external_ref=str(d["NOK_ID"]))
                for d in defects_by_hour.get(hour_id, [])
            ]
            try:
                records = replace_hour_quality(session, hour_id, lines, source=SOURCE, now=now)
            except QualityInvariantError as exc:
                raise DatasetError(f"{hour_id}: NOK_detail does not match NOK_ks — {exc}") from exc
            result.quality_added += sum(1 for r in records if r.external_ref is not None)

        _complete_if_all_hours(session, shift, now)
    session.flush()
    return result


def _complete_if_all_hours(session: Session, shift: Shift, now: datetime) -> None:
    """Zmena, ktorej import doplnil všetky hodiny podľa jej snapshotu, sa stane `completed`."""
    if shift.status == "completed":
        return
    session.flush()
    expected = int(shift.model_snapshot["duration_min"]) // MINUTES_PER_HOUR
    present = session.scalar(select(func.count()).where(HourlyReportRow.shift_id == shift.shift_id))
    if present == expected:
        shift.status, shift.completed_at, shift.updated_at = "completed", now, now


def import_excel(session: Session, path: Path, *, now: datetime) -> ImportResult:
    """Importuje dataset v jednej transakcii (commit pri úspechu, rollback pri chybe).

    Číselník kódov musí byť v DB (seed). `now` = naivný UTC čas auditu.

    Raises:
        DatasetError: súbor chýba, je poškodený alebo nekonzistentný.
    """
    data = _read(path)
    try:
        result = _import(session, data, now)
        session.commit()
    except DatasetError:
        session.rollback()
        raise
    except (KeyError, TypeError, ValueError) as exc:  # neočakávaný typ hodnoty v bunke
        session.rollback()
        raise DatasetError(f"invalid value in workbook: {exc!r}") from exc
    except Exception:
        session.rollback()
        raise
    return result

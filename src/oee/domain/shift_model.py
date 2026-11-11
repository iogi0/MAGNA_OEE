"""Model zmeny a target (TASK §3.1–3.2, PLANNING D8, D10).

Všetko sa počíta z konfigurácie, ktorú zadáva manažér (žiadne pevné čísla ako 440 / 480 / 60 ks/h — D8):

    planned_min (zmena) = dĺžka zmeny − prestávka − nastavenie/AM
    target (ks)         = výkon (ks/h) × planned_min / 60      (/ 60 = prevod minút na hodiny)
    ideal_cycle_s       = 3600 / výkon
    target hodiny       = výkon × planned_min hodiny / 60

Zmena má N = dĺžka / 60 hodinových slotov. Časy slotov sú naivný lokálny čas linky (ARCHITECTURE §10.3);
zmena môže prechádzať cez polnoc, dátum zmeny = dátum jej začiatku.
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

MINUTES_PER_HOUR = 60
SECONDS_PER_HOUR = 3600
WEEKDAYS = range(7)  # 0 = pondelok … 6 = nedeľa (date.weekday())


@dataclass(frozen=True)
class Allowance:
    """Plánovaná neprodukčná doba (prestávka alebo AM) v jednej hodine zmeny.

    `hour_no` je poradie hodiny zmeny (od 1), `offset_min` posun od začiatku tejto hodiny.
    """

    minutes: int
    hour_no: int
    offset_min: int = 0


@dataclass(frozen=True)
class ShiftModelConfig:
    """Konfigurácia modelu zmeny (snapshot sa ukladá so zmenou)."""

    rate_per_hour: float
    start: time
    duration_min: int
    break_: Allowance
    am: Allowance
    target_oee: float
    working_days: frozenset[int]


@dataclass(frozen=True)
class ConfigIssue:
    field: str
    message: str


class ShiftModelError(ValueError):
    """Nevalidná konfigurácia modelu zmeny; `issues` obsahuje všetky nájdené chyby."""

    def __init__(self, issues: list[ConfigIssue]) -> None:
        super().__init__("; ".join(f"{i.field}: {i.message}" for i in issues))
        self.issues = issues


@dataclass(frozen=True)
class HourSlot:
    hour_no: int
    start: datetime
    end: datetime
    am_min: int
    break_min: int
    planned_min: int
    target: float
    allowance_windows: tuple[tuple[datetime, datetime], ...] = ()
    """Okná prestávky / AM v tejto hodine (zoradené) — nie sú plánovaný čas (TASK §3.4 pravidlo 4)."""


@dataclass(frozen=True)
class ShiftPlan:
    shift_date: date
    config: ShiftModelConfig
    slots: tuple[HourSlot, ...]
    planned_min: int
    target: float
    ideal_cycle_s: float

    @property
    def target_oee(self) -> float:
        return self.config.target_oee

    @property
    def goal_good_pcs(self) -> float:
        """Cieľ OEE v kusoch: minimálny počet dobrých kusov zmeny = target × cieľ OEE (TASK §3.2)."""
        return self.target * self.config.target_oee

    @property
    def start(self) -> datetime:
        return self.slots[0].start

    @property
    def end(self) -> datetime:
        return self.slots[-1].end


# --- validácia ----------------------------------------------------------------------------------


def _hour_count(config: ShiftModelConfig) -> int | None:
    if config.duration_min > 0 and config.duration_min % MINUTES_PER_HOUR == 0:
        return config.duration_min // MINUTES_PER_HOUR
    return None


def _allowance_issues(name: str, a: Allowance, hours: int | None) -> Iterator[ConfigIssue]:
    if a.minutes < 0:
        yield ConfigIssue(name, "minutes must not be negative")
    if a.offset_min < 0:
        yield ConfigIssue(name, "offset must not be negative")
    if a.offset_min + a.minutes > MINUTES_PER_HOUR:
        yield ConfigIssue(name, f"must fit within its hour (offset + minutes ≤ {MINUTES_PER_HOUR})")
    if a.hour_no < 1 or (hours is not None and a.hour_no > hours):
        yield ConfigIssue(name, f"hour {a.hour_no} is outside the shift")


def _overlaps(a: Allowance, b: Allowance) -> bool:
    if a.hour_no != b.hour_no or a.minutes <= 0 or b.minutes <= 0:
        return False
    return a.offset_min < b.offset_min + b.minutes and b.offset_min < a.offset_min + a.minutes


def _slot_minutes(config: ShiftModelConfig, hour_no: int) -> tuple[int, int, int]:
    am = config.am.minutes if config.am.hour_no == hour_no else 0
    brk = config.break_.minutes if config.break_.hour_no == hour_no else 0
    return am, brk, MINUTES_PER_HOUR - am - brk


def _allowance_windows(
    config: ShiftModelConfig, hour_no: int, slot_start: datetime
) -> tuple[tuple[datetime, datetime], ...]:
    windows = [
        (
            slot_start + timedelta(minutes=a.offset_min),
            slot_start + timedelta(minutes=a.offset_min + a.minutes),
        )
        for a in (config.am, config.break_)
        if a.hour_no == hour_no and a.minutes > 0
    ]
    return tuple(sorted(windows))


def validate_shift_model(config: ShiftModelConfig) -> list[ConfigIssue]:
    """Všetky chyby konfigurácie (prázdny zoznam = konfigurácia je platná)."""
    issues: list[ConfigIssue] = []

    if not (math.isfinite(config.rate_per_hour) and config.rate_per_hour > 0):
        issues.append(ConfigIssue("rate_per_hour", "line rate must be greater than 0 pcs/h"))

    hours = _hour_count(config)
    if hours is None:
        issues.append(ConfigIssue("duration_min", "shift length must be a positive whole number of hours"))

    allowance_issues = [
        *_allowance_issues("break_", config.break_, hours),
        *_allowance_issues("am", config.am, hours),
    ]
    if _overlaps(config.break_, config.am):
        allowance_issues.append(ConfigIssue("break_", "break and AM overlap in the same hour"))
    issues.extend(allowance_issues)

    if config.break_.minutes + config.am.minutes >= config.duration_min:
        issues.append(ConfigIssue("duration_min", "break + AM must be shorter than the shift"))

    if hours is not None and not allowance_issues:
        empty = [h for h in range(1, hours + 1) if _slot_minutes(config, h)[2] <= 0]
        if empty:
            listed = ", ".join(str(h) for h in empty)
            issues.append(ConfigIssue("slots", f"hour(s) {listed} would have no planned production time"))

    if not 0 < config.target_oee <= 1:
        issues.append(ConfigIssue("target_oee", "OEE goal must be in (0, 1]"))

    if not config.working_days:
        issues.append(ConfigIssue("working_days", "at least one working day is required"))
    elif not config.working_days <= set(WEEKDAYS):
        issues.append(ConfigIssue("working_days", "working days must be weekdays 0 (Mon) … 6 (Sun)"))

    return issues


# --- výpočet ------------------------------------------------------------------------------------


def build_shift_plan(config: ShiftModelConfig, shift_date: date) -> ShiftPlan:
    """Sloty, plánované minúty a targety zmeny začínajúcej v deň `shift_date`.

    Raises:
        ShiftModelError: konfigurácia je nevalidná.
    """
    issues = validate_shift_model(config)
    if issues:
        raise ShiftModelError(issues)

    rate = config.rate_per_hour
    shift_start = datetime.combine(shift_date, config.start)
    hour = timedelta(minutes=MINUTES_PER_HOUR)
    slots: list[HourSlot] = []
    for i in range(config.duration_min // MINUTES_PER_HOUR):
        hour_no = i + 1
        am, brk, planned = _slot_minutes(config, hour_no)
        start = shift_start + i * hour
        slots.append(
            HourSlot(
                hour_no=hour_no,
                start=start,
                end=start + hour,
                am_min=am,
                break_min=brk,
                planned_min=planned,
                target=rate * planned / MINUTES_PER_HOUR,
                allowance_windows=_allowance_windows(config, hour_no, start),
            )
        )

    planned_total = sum(s.planned_min for s in slots)
    return ShiftPlan(
        shift_date=shift_date,
        config=config,
        slots=tuple(slots),
        planned_min=planned_total,
        target=rate * planned_total / MINUTES_PER_HOUR,
        ideal_cycle_s=SECONDS_PER_HOUR / rate,
    )


# --- snapshot (JSON) ----------------------------------------------------------------------------

Snapshot = dict[str, object]


def _allowance_to_dict(a: Allowance) -> dict[str, int]:
    return {"minutes": a.minutes, "hour_no": a.hour_no, "offset_min": a.offset_min}


def config_to_snapshot(config: ShiftModelConfig) -> Snapshot:
    """Model zmeny ako JSON-kompatibilný slovník (ukladá sa so zmenou, TASK §3.1)."""
    return {
        "rate_per_hour": config.rate_per_hour,
        "start": config.start.strftime("%H:%M"),
        "duration_min": config.duration_min,
        "break": _allowance_to_dict(config.break_),
        "am": _allowance_to_dict(config.am),
        "target_oee": config.target_oee,
        "working_days": sorted(config.working_days),
    }


def _allowance_from(data: object) -> Allowance:
    if not isinstance(data, dict):
        raise TypeError("allowance must be an object")
    return Allowance(
        minutes=int(data["minutes"]), hour_no=int(data["hour_no"]), offset_min=int(data.get("offset_min", 0))
    )


def config_from_snapshot(snapshot: Snapshot) -> ShiftModelConfig:
    """Opak `config_to_snapshot`; výsledok sa overí `validate_shift_model`.

    Raises:
        ShiftModelError: snapshot je neúplný alebo model je nevalidný.
    """
    try:
        days = snapshot["working_days"]
        if not isinstance(days, list):
            raise TypeError("working_days must be a list")
        config = ShiftModelConfig(
            rate_per_hour=float(snapshot["rate_per_hour"]),  # type: ignore[arg-type]
            start=time.fromisoformat(str(snapshot["start"])),
            duration_min=int(snapshot["duration_min"]),  # type: ignore[call-overload]
            break_=_allowance_from(snapshot["break"]),
            am=_allowance_from(snapshot["am"]),
            target_oee=float(snapshot["target_oee"]),  # type: ignore[arg-type]
            working_days=frozenset(int(d) for d in days),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ShiftModelError([ConfigIssue("snapshot", f"invalid shift model snapshot: {exc!r}")]) from exc
    issues = validate_shift_model(config)
    if issues:
        raise ShiftModelError(issues)
    return config

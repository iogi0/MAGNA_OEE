"""Formulár modelu zmeny v Settings (TASK §3.2, PLANNING D8).

Iba prevod textových polí na `ShiftModelConfig` (dĺžka zmeny v hodinách → minúty, cieľ OEE v % → podiel)
a zber chýb. Pravidlá platnosti modelu sú v doméne (`validate_shift_model`), nie tu.
Prázdny formulár nemá žiadne predvolené hodnoty (D8) — príklad sa načíta iba tlačidlom „Fill with example".
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import time

from starlette.datastructures import FormData

from oee.domain.shift_model import (
    MINUTES_PER_HOUR,
    WEEKDAYS,
    Allowance,
    ShiftModelConfig,
    validate_shift_model,
)

PERCENT = 100
TEXT_FIELDS = (
    "product",
    "rate_per_hour",
    "start",
    "duration_h",
    "break_min",
    "break_hour_no",
    "break_offset_min",
    "am_min",
    "am_hour_no",
    "am_offset_min",
    "target_oee_pct",
    "grace_min",
)
# pole domény (ConfigIssue.field) → pole formulára
DOMAIN_FIELD = {
    "rate_per_hour": "rate_per_hour",
    "duration_min": "duration_h",
    "break_": "break_min",
    "am": "am_min",
    "slots": "duration_h",
    "target_oee": "target_oee_pct",
    "working_days": "working_days",
}
# doménové správy, ktoré formulár zadáva inak (cieľ OEE v %)
DOMAIN_MESSAGE = {"target_oee": "must be greater than 0 % and at most 100 %"}
LABELS = {
    "product": "Product",
    "rate_per_hour": "Line rate",
    "start": "Shift start",
    "duration_h": "Shift length",
    "break_min": "Break",
    "am_min": "Setup / AM",
    "target_oee_pct": "OEE goal",
    "working_days": "Working days",
    "grace_min": "Grace",
}


@dataclass
class ModelForm:
    values: dict[str, str]
    working_days: frozenset[int]
    errors: list[tuple[str, str]] = field(default_factory=list)
    """(pole formulára, správa) — zobrazené používateľovi."""
    config: ShiftModelConfig | None = None
    product: str | None = None
    grace_min: int | None = None

    @property
    def ok(self) -> bool:
        return self.config is not None and not self.errors

    @property
    def invalid_fields(self) -> set[str]:
        return {f for f, _ in self.errors}


def _domain_error(domain_field: str, message: str) -> tuple[str, str]:
    name = DOMAIN_FIELD.get(domain_field, domain_field)
    label = LABELS.get(name)
    return name, f"{label}: {message}" if label else message


def empty_form() -> ModelForm:
    return ModelForm(values=dict.fromkeys(TEXT_FIELDS, ""), working_days=frozenset())


def _fmt(value: float) -> str:
    return f"{value:.4f}".rstrip("0").rstrip(".")


def form_from_config(config: ShiftModelConfig, *, product: str, grace_min: int) -> ModelForm:
    """Formulár predvyplnený existujúcim modelom (aktívny model alebo príklad)."""
    values = {
        "product": product,
        "rate_per_hour": _fmt(config.rate_per_hour),
        "start": config.start.strftime("%H:%M"),
        "duration_h": str(config.duration_min // MINUTES_PER_HOUR),
        "break_min": str(config.break_.minutes),
        "break_hour_no": str(config.break_.hour_no),
        "break_offset_min": str(config.break_.offset_min),
        "am_min": str(config.am.minutes),
        "am_hour_no": str(config.am.hour_no),
        "am_offset_min": str(config.am.offset_min),
        "target_oee_pct": _fmt(config.target_oee * PERCENT),
        "grace_min": str(grace_min),
    }
    return ModelForm(values, config.working_days, config=config, product=product, grace_min=grace_min)


def parse_model_form(data: FormData) -> ModelForm:
    """Textové polia → `ShiftModelConfig`; chyby prevodu aj doménovej validácie sú v `errors`."""
    values = {name: str(data.get(name) or "").strip() for name in TEXT_FIELDS}
    errors: list[tuple[str, str]] = []

    def number(name: str, *, integer: bool) -> float | None:
        raw = values[name]
        label = LABELS.get(name, name.replace("_", " ").capitalize())
        try:
            value = int(raw) if integer else float(raw.replace(",", "."))
        except ValueError:
            errors.append((name, f"{label}: enter a {'whole ' if integer else ''}number"))
            return None
        if not math.isfinite(value):
            errors.append((name, f"{label}: enter a finite number"))
            return None
        return value

    days: set[int] = set()
    for raw in data.getlist("working_days"):
        if isinstance(raw, str) and raw.isdigit() and int(raw) in WEEKDAYS:
            days.add(int(raw))
        else:
            errors.append(("working_days", "Working days: invalid weekday"))

    product = values["product"]
    if not product:
        errors.append(("product", "Product: enter the product id"))
    try:
        start: time | None = time.fromisoformat(values["start"])
    except ValueError:
        start = None
        errors.append(("start", "Shift start: enter a time as HH:MM"))

    rate = number("rate_per_hour", integer=False)
    hours = number("duration_h", integer=True)
    goal_pct = number("target_oee_pct", integer=False)
    grace = number("grace_min", integer=True)
    if grace is not None and grace < 0:
        errors.append(("grace_min", "Grace: must not be negative"))
    allowance = {
        name: number(name, integer=True)
        for name in (
            "break_min",
            "break_hour_no",
            "break_offset_min",
            "am_min",
            "am_hour_no",
            "am_offset_min",
        )
    }

    form = ModelForm(values, frozenset(days), errors)
    if errors or None in (rate, hours, goal_pct, start) or None in allowance.values():
        return form

    def allow(prefix: str) -> Allowance:
        return Allowance(
            minutes=int(allowance[f"{prefix}_min"] or 0),
            hour_no=int(allowance[f"{prefix}_hour_no"] or 0),
            offset_min=int(allowance[f"{prefix}_offset_min"] or 0),
        )

    assert rate is not None and hours is not None and goal_pct is not None and start is not None
    config = ShiftModelConfig(
        rate_per_hour=rate,
        start=start,
        duration_min=int(hours) * MINUTES_PER_HOUR,
        break_=allow("break"),
        am=allow("am"),
        target_oee=goal_pct / PERCENT,
        working_days=frozenset(days),
    )
    issues = validate_shift_model(config)
    if issues:
        form.errors.extend(_domain_error(i.field, DOMAIN_MESSAGE.get(i.field, i.message)) for i in issues)
        return form
    assert grace is not None
    form.config, form.product, form.grace_min = config, product, int(grace)
    return form

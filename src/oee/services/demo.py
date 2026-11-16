"""Demo dáta (P0-25, TASK §14, §12.8, PLANNING D8).

- `ensure_active_model`: ak linka nemá aktívny model zmeny, aktivuje príklad z `example_shift_model.yaml`
  (D8 — príklad sa použije iba tu a v Settings „Fill with example", nikdy ako skrytý predvolený stav).
  Model, ktorý zadal manažér, sa nemení.
- `build_demo_shift`: ručne „zadaná" zmena cez tú istú službu ako web (`save_hour`, validácia V1–V12, V14).
  V hodinách 2, 3, 4 je prestoj ST-038 (camera light) a v hodine po každom z nich zmätky Q-030 (image check);
  jeden Q-030 je aj v 1. hodine mimo okna, aby existoval základný rate (okno = hodina prestoja + nasledujúca).
  Výsledok: väzba ST-038 → Q-030 (same_process)
  s vysokým liftom, ktorú AI vysvetlí. Kusy sa počítajú z plánu zmeny (žiadne pevné čísla modelu).
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from oee.catalog.loader import load_example_settings
from oee.contracts.hourly_report import HourlyReport, IssueReport, RejectByDefect
from oee.domain.shift_model import MINUTES_PER_HOUR, build_shift_plan, config_from_snapshot
from oee.persistence.models import Shift
from oee.services.codebook import get_active_codes
from oee.services.reporting import hour_id_for, open_shift, save_hour, shift_id_for
from oee.services.shift_models import activate_shift_model, get_active_model

CAUSE = "ST-038"
EFFECT = "Q-030"
CAUSE_HOURS = (2, 3, 4)  # hodina s prestojom; nasledujúca hodina má zmätky EFFECT
BASELINE_HOUR = 1  # jeden zmätok EFFECT mimo okna → základný rate > 0
EFFECT_QTY = 2
STOP_MIN = 12
STOP_OFFSET_MIN = 5
SPEED_FACTOR = 0.95  # mierne straty rýchlosti, nech dashboard ukáže všetky tri straty
MIN_HOURS = max(CAUSE_HOURS) + 2  # okno + aspoň jedna hodina základne po ňom


class DemoError(RuntimeError):
    """Demo zmena sa nedá vytvoriť (už existuje, krátka zmena …)."""


def ensure_active_model(session: Session, *, line: str, now: datetime) -> bool:
    """Aktivuje príkladový model, ak linka nemá aktívny (commit). True = príklad bol aktivovaný."""
    if get_active_model(session, line=line) is not None:
        return False
    example = load_example_settings()
    activate_shift_model(
        session, example.config, line=line, product=example.product, grace_min=example.grace_min, now=now
    )
    session.commit()
    return True


def build_demo_shift(
    session: Session, *, line: str, day: date, now: datetime, hours: int | None = None
) -> str:
    """Vytvorí demo zmenu a uloží prvých `hours` hodín (None = všetky → `completed`). Vráti `shift_id`.

    Raises:
        DemoError: zmena v daný deň už existuje, zmena má menej ako `MIN_HOURS` hodín alebo hodina neprejde
            validáciou.
        services.reporting.NoActiveShiftModel: linka nemá aktívny model.
    """
    if session.get(Shift, shift_id_for(line, day)) is not None:
        raise DemoError(f"A shift for {line} on {day:%Y-%m-%d} already exists — choose another --date")
    shift = open_shift(session, line=line, day=day, now=now)
    plan = build_shift_plan(config_from_snapshot(shift.model_snapshot), shift.date)
    if len(plan.slots) < MIN_HOURS:
        session.delete(shift)
        session.commit()
        raise DemoError(
            f"The demo needs a shift of at least {MIN_HOURS} hours (this one has {len(plan.slots)})"
        )

    codes = get_active_codes(session)
    rate_per_min = plan.config.rate_per_hour / MINUTES_PER_HOUR
    for slot in plan.slots[: hours if hours is not None else len(plan.slots)]:
        issues: tuple[IssueReport, ...] = ()
        stop_min = 0
        if slot.hour_no in CAUSE_HOURS:
            stop_min = min(STOP_MIN, slot.planned_min - 1)
            # po prestávke / AM v tejto hodine, nech sa prestoj s nimi neprekrýva
            start = max([slot.start, *(end for _, end in slot.allowance_windows)]) + timedelta(
                minutes=STOP_OFFSET_MIN
            )
            start = min(start, slot.end - timedelta(minutes=stop_min))  # prestoj sa zmestí do hodiny
            issues = (
                IssueReport(
                    client_key=f"demo-{slot.hour_no}",
                    issue_type_code=CAUSE,
                    duration_min=stop_min,
                    start_time=f"{start:%H:%M}",
                    comment="Camera light module interrupted operation (demo)",
                ),
            )
        rejects = 0
        if slot.hour_no - 1 in CAUSE_HOURS:
            rejects = EFFECT_QTY
        elif slot.hour_no == BASELINE_HOUR:
            rejects = 1
        produced = math.floor((slot.planned_min - stop_min) * rate_per_min * SPEED_FACTOR)
        report = HourlyReport(
            hour_id=hour_id_for(line, day, slot.hour_no),
            shift_id=shift.shift_id,
            date=day,
            hour_no=slot.hour_no,
            produced=produced,
            rejects=rejects,
            rejects_by_defect=(RejectByDefect(defect_type_code=EFFECT, qty=rejects),) if rejects else (),
            issues=issues,
            submitted_by="demo",
        )
        result = save_hour(session, shift.shift_id, report, codes=codes, now=now)
        if not result.saved:
            errors = "; ".join(f"{m.rule} {m.message}" for m in result.messages)
            raise DemoError(f"Hour {slot.hour_no} did not pass validation: {errors}")
    return shift.shift_id

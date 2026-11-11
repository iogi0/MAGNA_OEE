"""Vzorový Excel pre stránku Import — ukážka formátu, ktorý číta `services.importer`.

Hlavičky sú tie isté konštanty ako v importéri (`VYROBA_REQUIRED` …), model zmeny je príklad
z `catalog/example_shift_model.yaml` (D8) a kódy sú z katalógu — vzor sa preto nerozíde s importom.
Súbor sa generuje v pamäti; dataset organizátorov sa nečíta ani nemení.
"""

from __future__ import annotations

import io
import math
from datetime import date, datetime, timedelta

import openpyxl
from openpyxl.styles import Font

from oee.catalog.loader import load_catalog, load_example_settings
from oee.domain.shift_model import MINUTES_PER_HOUR, build_shift_plan
from oee.services.importer import GOAL_CELL, NOK_REQUIRED, PRESTOJE_REQUIRED, VYROBA_REQUIRED

INSTRUCTIONS_SHEET = "Instructions"
EXAMPLE_STOP_MIN = 5  # ukážková udalosť prestoja v hodine bez prestávky / AM
EXAMPLE_STOP_OFFSET_MIN = 15
EXAMPLE_SPEED = 0.9  # ukážková výroba = 90 % ideálneho tempa v čase bez prestoja

COLUMN_HELP: tuple[tuple[str, str, str], ...] = (
    ("Vyroba_hodiny", "Hodina_ID", "Unique hour id: {line}-{YYYYMMDD}-{hour no. 01..N}"),
    ("Vyroba_hodiny", "Datum", "Shift date (date of its start)"),
    ("Vyroba_hodiny", "Linka", "Line id"),
    ("Vyroba_hodiny", "Produkt", "Product id"),
    ("Vyroba_hodiny", "Hodina_zmeny", "Hour of the shift, 1..N"),
    ("Vyroba_hodiny", "Cas_od / Cas_do", "Start and end of the hour slot (date and time)"),
    ("Vyroba_hodiny", "Interval_min", "Slot length in minutes (one hour)"),
    ("Vyroba_hodiny", "AM_min / Pauza_min", "Planned setup/AM and break minutes in this hour"),
    ("Vyroba_hodiny", "Ideal_cyklus_s", "Ideal cycle time in seconds (3600 / line rate)"),
    ("Vyroba_hodiny", "Vyrobene_ks", "Produced pieces in the hour, including rejects"),
    ("Vyroba_hodiny", "NOK_ks", "Rejected pieces in the hour"),
    ("Prestoje", "Kod_chyby", "Stop code ST-xxx from the codebook (Settings)"),
    ("Prestoje", "Hodina_ID", "Hour the downtime belongs to"),
    ("Prestoje", "Cas_od / Cas_do", "Downtime start and end (date and time)"),
    ("NOK_detail", "NOK_ID", "Unique id of the reject record"),
    ("NOK_detail", "Hodina_ID", "Hour of the rejects"),
    ("NOK_detail", "NOK_ks", "Rejected pieces; per hour they must add up to NOK_ks in Vyroba_hodiny"),
    ("NOK_detail", "Kod_chyby", "Defect code Q-xxx from the codebook (Settings)"),
    (GOAL_CELL[0], GOAL_CELL[1], "OEE goal as a fraction (e.g. 0.8 = 80 %)"),
)


def _header(ws: object, names: tuple[str, ...]) -> None:
    ws.append(list(names))  # type: ignore[attr-defined]
    for cell in ws[1]:  # type: ignore[index]
        cell.font = Font(bold=True)


def build_example_workbook(day: date, *, line: str) -> bytes:
    """Jedna ukážková zmena v deň `day`: všetky hodiny, jeden prestoj a jeden záznam zmätku."""
    example = load_example_settings()
    catalog = load_catalog()
    plan = build_shift_plan(example.config, day)
    free = next(s for s in plan.slots if not s.allowance_windows)  # hodina bez prestávky a AM

    wb = openpyxl.Workbook()
    info = wb.active
    assert info is not None
    info.title = INSTRUCTIONS_SHEET
    info.append(["Example import file — one shift. Keep sheet names and column headers; add rows below."])
    info.append([])
    _header(info, ("Sheet", "Column", "Meaning"))
    for row in COLUMN_HELP:
        info.append(list(row))
    for col, width in (("A", 16), ("B", 20), ("C", 80)):
        info.column_dimensions[col].width = width

    hours = wb.create_sheet("Vyroba_hodiny")
    _header(hours, VYROBA_REQUIRED)
    for slot in plan.slots:
        run_min = slot.planned_min - (EXAMPLE_STOP_MIN if slot is free else 0)
        produced = math.floor(example.config.rate_per_hour * run_min / MINUTES_PER_HOUR * EXAMPLE_SPEED)
        hours.append(
            [
                f"{line}-{day:%Y%m%d}-{slot.hour_no:02d}",
                datetime.combine(day, datetime.min.time()),
                line,
                example.product,
                slot.hour_no,
                slot.start,
                slot.end,
                MINUTES_PER_HOUR,
                slot.am_min,
                slot.break_min,
                plan.ideal_cycle_s,
                produced,
                1 if slot is free else 0,
            ]
        )

    hour_id = f"{line}-{day:%Y%m%d}-{free.hour_no:02d}"
    stop_start = free.start + timedelta(minutes=EXAMPLE_STOP_OFFSET_MIN)
    stops = wb.create_sheet("Prestoje")
    _header(stops, PRESTOJE_REQUIRED)
    stops.append(
        [catalog.top10_stop[0], hour_id, stop_start, stop_start + timedelta(minutes=EXAMPLE_STOP_MIN)]
    )

    nok = wb.create_sheet("NOK_detail")
    _header(nok, NOK_REQUIRED)
    nok.append([f"NOK-{day:%Y%m%d}-1", hour_id, 1, catalog.top10_defect[0]])

    for ws in (hours, stops):
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                if isinstance(cell.value, datetime):
                    cell.number_format = "yyyy-mm-dd hh:mm"

    goal_sheet = wb.create_sheet(GOAL_CELL[0])
    goal_sheet[GOAL_CELL[1]] = float(example.config.target_oee)

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()

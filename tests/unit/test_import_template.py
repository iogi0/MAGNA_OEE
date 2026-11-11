"""Vzorový Excel na stiahnutie (Import): formát = presne to, čo číta `import_excel`."""

from __future__ import annotations

import io
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

import openpyxl
from sqlalchemy.orm import Session

from oee.catalog.loader import load_catalog, load_example_settings
from oee.domain.shift_model import build_shift_plan
from oee.persistence.seed import seed_codebook
from oee.services.import_template import INSTRUCTIONS_SHEET, build_example_workbook
from oee.services.importer import NOK_REQUIRED, PRESTOJE_REQUIRED, VYROBA_REQUIRED, import_excel

DAY = date(2026, 12, 7)


def test_example_has_required_sheets_and_headers() -> None:
    wb = openpyxl.load_workbook(io.BytesIO(build_example_workbook(DAY, line="L01")), read_only=True)
    try:
        assert wb.sheetnames[0] == INSTRUCTIONS_SHEET
        for sheet, required in (
            ("Vyroba_hodiny", VYROBA_REQUIRED),
            ("Prestoje", PRESTOJE_REQUIRED),
            ("NOK_detail", NOK_REQUIRED),
        ):
            header = next(wb[sheet].iter_rows(values_only=True))
            assert tuple(header) == required, sheet
        assert isinstance(wb["Dashboard"]["E51"].value, float)
    finally:
        wb.close()


def test_example_imports_cleanly(session: Session, tmp_path: Path) -> None:
    seed_codebook(session, load_catalog())
    session.commit()
    path = tmp_path / "example.xlsx"
    path.write_bytes(build_example_workbook(DAY, line="L01"))
    result = import_excel(session, path, now=datetime(2026, 12, 8))
    hours = len(build_shift_plan(load_example_settings().config, DAY).slots)  # z príkladového modelu (D8)
    assert (result.shifts_added, result.hours_added) == (1, hours)
    assert result.issues_added == 1 and result.quality_added == 1
    assert all(check.ok for check in result.checks), result.checks
    # importér odvodí pracovné dni z dátumov v súbore — vzor má jednu zmenu (pondelok)
    expected = replace(load_example_settings().config, working_days=frozenset({DAY.weekday()}))
    assert result.models["L01-20261207-M"] == expected

"""P0-06 (golden): všetky kódy datasetu (6 ST, 4 Q) sú v Top-10 a číselník katalógu = `Ciselnik_chyb`.

Excel sa iba číta (`read_only=True, data_only=True`), nikdy neukladá (CLAUDE.md pravidlo 9).
"""

from __future__ import annotations

from pathlib import Path

import openpyxl
import pytest

from oee.catalog.loader import load_catalog
from oee.config import PROJECT_ROOT

DATASET = PROJECT_ROOT / "data" / "raw" / "dummy_data.xlsx"

pytestmark = [
    pytest.mark.golden,
    pytest.mark.skipif(not DATASET.is_file(), reason="dataset data/raw/dummy_data.xlsx missing"),
]


def sheet_rows(path: Path, sheet: str) -> list[dict[str, object]]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        rows = list(wb[sheet].iter_rows(values_only=True))
    finally:
        wb.close()
    header = [str(h) for h in rows[0]]
    return [dict(zip(header, r, strict=False)) for r in rows[1:] if any(v is not None for v in r)]


def test_dataset_codes_are_in_top10() -> None:
    cat = load_catalog()
    stops = {r["Kod_chyby"] for r in sheet_rows(DATASET, "Prestoje")}
    defects = {r["Kod_chyby"] for r in sheet_rows(DATASET, "NOK_detail")}
    assert (len(stops), len(defects)) == (6, 4)
    assert stops <= set(cat.top10_stop)
    assert defects <= set(cat.top10_defect)


def test_codebook_matches_excel() -> None:
    cat = load_catalog()
    rows = sheet_rows(DATASET, "Ciselnik_chyb")
    assert {r["Kod_chyby"] for r in rows} == set(cat.codes)
    for r in rows:
        code = cat.codes[str(r["Kod_chyby"])]
        assert (code.name_sk, code.name_en) == (r["Popis_SK"], r["Popis_EN"])
        assert code.kind == {"Prestoj": "stop", "Kvalita": "defect"}[str(r["Typ"])]

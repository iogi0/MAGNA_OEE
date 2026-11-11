"""Jednorazová extrakcia číselníka chýb z Excelu do `src/oee/catalog/codes.yaml` (PLANNING P0-06).

Excel sa iba ČÍTA (`read_only=True, data_only=True`) a nikdy neukladá (CLAUDE.md pravidlo 9).

Použitie:
    .venv/Scripts/python scripts/extract_codebook.py [cesta_k_xlsx]
"""

from __future__ import annotations

import sys
from pathlib import Path

import openpyxl
import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_XLSX = ROOT / "data" / "raw" / "dummy_data.xlsx"
OUTPUT = ROOT / "src" / "oee" / "catalog" / "codes.yaml"

KIND = {"Prestoj": "stop", "Kvalita": "defect"}
# Kategória v Exceli je „SK / EN"; kľúč = id kategórie v katalógu (top10.yaml → categories).
CATEGORY = {
    "General": "general",
    "Camera": "camera",
    "Robot": "robot",
    "Pressing": "pressing",
    "Screwdriving": "screwdriving",
    "Leak test": "leak_test",
    "Other": "other",
}

HEADER = """\
# Celý číselník chýb (48 ST + 34 Q) z hárku `Ciselnik_chyb` opraveného datasetu (ST-016 = Camera).
# Vygenerované skriptom scripts/extract_codebook.py — neupravovať ručne.
# category = kategória číselníka; kategória kódov Top-10 v top10.yaml má prednosť (PLANNING D9).
"""


def read_codebook(path: Path) -> list[dict[str, str]]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        rows = list(wb["Ciselnik_chyb"].iter_rows(values_only=True))
    finally:
        wb.close()
    header = [str(h) for h in rows[0]]
    codes: list[dict[str, str]] = []
    for raw in rows[1:]:
        r = dict(zip(header, raw, strict=False))
        if not r.get("Kod_chyby"):
            continue
        category_en = str(r["Kategoria"]).split("/")[-1].strip()
        codes.append(
            {
                "code": str(r["Kod_chyby"]).strip(),
                "kind": KIND[str(r["Typ"]).strip()],
                "category": CATEGORY[category_en],
                "name_en": str(r["Popis_EN"]).strip(),
                "name_sk": str(r["Popis_SK"]).strip(),
            }
        )
    return codes


def main(argv: list[str]) -> int:
    source = Path(argv[1]) if len(argv) > 1 else DEFAULT_XLSX
    codes = read_codebook(source)
    body = yaml.safe_dump({"codes": codes}, allow_unicode=True, sort_keys=False, width=200)
    OUTPUT.write_text(HEADER + body, encoding="utf-8")
    stops = sum(c["kind"] == "stop" for c in codes)
    print(f"{OUTPUT.relative_to(ROOT)}: {len(codes)} codes ({stops} ST, {len(codes) - stops} Q)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

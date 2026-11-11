"""Pripraví demo podľa TASK §14 (P0-25). Spúšťa sa z koreňa projektu pred `uvicorn`.

Použitie:
    .venv/Scripts/python scripts/demo_seed.py                 # import + model + celá demo zmena 01.12.2026
    .venv/Scripts/python scripts/demo_seed.py --hours 3       # prvé 3 hodiny, zvyšok operátor zadá naživo
    .venv/Scripts/python scripts/demo_seed.py --no-demo-shift # iba import a model (celú zmenu zadať naživo)
    .venv/Scripts/python scripts/demo_seed.py --date 2026-12-02

Kroky:
1. číselník (seed) a import datasetu (`OEE_DATASET_PATH`, Excel iba na čítanie; opakovaný import
   bez duplicít);
2. ak linka nemá aktívny model zmeny, aktivuje príklad `catalog/example_shift_model.yaml` (D8);
   model, ktorý nastavil manažér v Settings, ostáva;
3. demo zmena: ST-038 a hneď po ňom Q-030 → väzba v Problem Links za mesiac zmeny (TASK §12.8).
Databáza = `OEE_DB_PATH` (predvolene `data/local/oee.db`). Nič nesťahuje, nepotrebuje sieť ani Ollama.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, date, datetime

from oee.catalog.loader import load_catalog
from oee.config import get_settings
from oee.persistence.db import init_db, make_engine, make_session_factory
from oee.persistence.seed import seed_codebook
from oee.services.demo import DemoError, build_demo_shift, ensure_active_model
from oee.services.importer import DatasetError, import_excel

DEMO_DATE = "2026-12-01"  # TASK §14.4 (deň bez existujúcej zmeny)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # konzola cp1251
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--date", default=DEMO_DATE, type=date.fromisoformat, help="demo shift date (YYYY-MM-DD)"
    )
    parser.add_argument("--hours", type=int, default=None, help="fill only the first N hours (default: all)")
    parser.add_argument(
        "--no-demo-shift", action="store_true", help="only import the dataset and set the model"
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    now = datetime.now(UTC).replace(tzinfo=None)  # audit v naivnom UTC (ARCHITECTURE §10.3)
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = make_engine(settings.db_path)
    init_db(engine)
    factory = make_session_factory(engine)
    print(f"Database: {settings.db_path}")
    with factory() as session:
        seed_codebook(session, load_catalog())
        session.commit()
        try:
            result = import_excel(session, settings.dataset_path, now=now)
        except DatasetError as exc:
            print(f"[FAIL] import {settings.dataset_path}: {exc}")
            return 1
        failed = [c for c in result.checks if not c.ok]
        print(
            f"[OK] import: +{result.shifts_added} shifts, +{result.hours_added} hours, "
            f"+{result.issues_added} problems ({result.hours_skipped} hours already there); "
            f"checks failed: {len(failed)}"
        )
        if ensure_active_model(session, line=settings.line_id, now=now):
            print("[OK] no active shift model — activated the example from catalog/example_shift_model.yaml")
        else:
            print("[OK] the line already has an active shift model — kept unchanged")
        if args.no_demo_shift:
            return 0
        try:
            shift_id = build_demo_shift(
                session, line=settings.line_id, day=args.date, now=now, hours=args.hours
            )
        except (DemoError, LookupError, ValueError) as exc:  # aj NoActiveShiftModel, nepracovný deň
            print(f"[FAIL] demo shift: {exc}")
            return 1
        print(
            f"[OK] demo shift {shift_id}: open /shift/{shift_id} and /history/links?month={args.date:%Y-%m}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

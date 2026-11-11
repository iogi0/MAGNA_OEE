"""P0-09: import Excelu na syntetických zošitoch (iná konfigurácia zmeny, poškodené dáta, transakcia).

Zošity vytvára test do `tmp_path`; dataset organizátorov sa tu nepoužíva
(golden test: tests/golden/test_import.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from pathlib import Path

import openpyxl
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from oee.catalog.loader import load_catalog
from oee.persistence.models import HourlyReportRow, IssueEvent, ProductionRecord, QualityRecord, Shift
from oee.persistence.seed import seed_codebook
from oee.services.importer import DatasetError, import_excel

NOW = datetime(2026, 12, 1, 8, 0)

VYROBA_COLS = [
    "Hodina_ID", "Datum", "Linka", "Produkt", "Hodina_zmeny", "Cas_od", "Cas_do", "Interval_min", "AM_min",
    "Pauza_min", "Ideal_cyklus_s", "Vyrobene_ks", "NOK_ks",
]  # fmt: skip


@dataclass
class Book:
    """Minimálny zošit vo formáte datasetu (iba povinné stĺpce)."""

    vyroba: list[list[object]] = field(default_factory=list)
    prestoje: list[list[object]] = field(default_factory=list)
    nok: list[list[object]] = field(default_factory=list)
    target_oee: float | None = 0.8
    drop_column: str | None = None

    def add_shift(
        self,
        day: datetime,
        *,
        start: time,
        hours: int,
        cycle_s: float,
        am: tuple[int, int],
        pauza: tuple[int, int],
        produced: list[int],
        nok: list[int] | None = None,
    ) -> None:
        nok = nok or [0] * hours
        t0 = datetime.combine(day.date(), start)
        for h in range(1, hours + 1):
            slot = t0 + timedelta(hours=h - 1)
            self.vyroba.append(
                [
                    f"L01-{day:%Y%m%d}-{h:02d}",
                    day,
                    "L01",
                    "P01",
                    h,
                    slot,
                    slot + timedelta(hours=1),
                    60,
                    am[1] if h == am[0] else 0,
                    pauza[1] if h == pauza[0] else 0,
                    cycle_s,
                    produced[h - 1],
                    nok[h - 1],
                ]  # fmt: skip
            )

    def save(self, path: Path) -> Path:
        wb = openpyxl.Workbook()
        ws = wb.active
        assert ws is not None
        ws.title = "Vyroba_hodiny"
        cols = [c for c in VYROBA_COLS if c != self.drop_column]
        ws.append(cols)
        for row in self.vyroba:
            ws.append([v for c, v in zip(VYROBA_COLS, row, strict=True) if c != self.drop_column])
        p = wb.create_sheet("Prestoje")
        p.append(["Kod_chyby", "Hodina_ID", "Cas_od", "Cas_do"])
        for r in self.prestoje:
            p.append(r)
        n = wb.create_sheet("NOK_detail")
        n.append(["NOK_ID", "Hodina_ID", "NOK_ks", "Kod_chyby"])
        for r in self.nok:
            n.append(r)
        d = wb.create_sheet("Dashboard")
        d["E51"] = self.target_oee
        wb.save(path)
        return path


def six_hour_book() -> Book:
    """Dve 6-h zmeny od 14:00, takt 80 s (45 ks/h), AM 15 min v 1. hod., prestávka 20 min v 3. hod."""
    b = Book()
    for day in (datetime(2026, 12, 7), datetime(2026, 12, 9)):  # pondelok, streda
        b.add_shift(
            day,
            start=time(14, 0),
            hours=6,
            cycle_s=80,
            am=(1, 15),
            pauza=(3, 20),
            produced=[30, 40, 25, 41, 42, 40],
            nok=[0, 1, 0, 2, 0, 0],
        )
    b.prestoje.append(
        ["ST-038", "L01-20261207-02", datetime(2026, 12, 7, 15, 10), datetime(2026, 12, 7, 15, 15, 30)]
    )
    b.nok += [["X1", "L01-20261207-02", 1, "Q-030"], ["X2", "L01-20261207-04", 2, "Q-031"]]
    b.nok += [["X3", "L01-20261209-02", 1, "Q-030"], ["X4", "L01-20261209-04", 2, "Q-020"]]
    return b


@pytest.fixture
def db(session: Session) -> Session:
    seed_codebook(session, load_catalog())
    session.commit()
    return session


def count(s: Session, model: type) -> int:
    return int(s.scalar(select(func.count()).select_from(model)) or 0)


# --- iná konfigurácia zmeny ---------------------------------------------------------------------


def test_derives_shift_model_from_file(db: Session, tmp_path: Path) -> None:
    result = import_excel(db, six_hour_book().save(tmp_path / "six.xlsx"), now=NOW)
    model = result.models["L01-20261207-M"]
    assert model.rate_per_hour == pytest.approx(45)
    assert model.start == time(14, 0)
    assert model.duration_min == 360
    assert (model.am.minutes, model.am.hour_no, model.am.offset_min) == (15, 1, 0)
    assert (model.break_.minutes, model.break_.hour_no) == (20, 3)
    assert model.target_oee == 0.8
    assert model.working_days == frozenset({0, 2})  # dni prítomné v súbore


def test_imports_rows_and_snapshot(db: Session, tmp_path: Path) -> None:
    result = import_excel(db, six_hour_book().save(tmp_path / "six.xlsx"), now=NOW)
    assert (result.shifts_added, result.hours_added, result.issues_added, result.quality_added) == (
        2,
        12,
        1,
        4,
    )
    shift = db.get(Shift, "L01-20261207-M")
    assert shift is not None and shift.status == "completed"
    assert shift.model_snapshot["duration_min"] == 360
    hour = db.get(HourlyReportRow, "L01-20261207-03")
    assert hour is not None and hour.planned_min == 40 and hour.slot_start == datetime(2026, 12, 7, 16, 0)
    issue = db.scalars(select(IssueEvent)).one()
    assert issue.start_at == datetime(2026, 12, 7, 15, 10)
    assert issue.duration_min == pytest.approx(5.5)  # trvanie z Cas_do − Cas_od, na sekundy
    assert issue.source == "import" and issue.client_key is None
    assert all(c.ok for c in result.checks)


def test_reimport_adds_nothing(db: Session, tmp_path: Path) -> None:
    path = six_hour_book().save(tmp_path / "six.xlsx")
    import_excel(db, path, now=NOW)
    again = import_excel(db, path, now=NOW)
    assert (again.shifts_added, again.hours_added, again.issues_added, again.quality_added) == (0, 0, 0, 0)
    assert again.hours_skipped == 12
    assert (
        count(db, Shift),
        count(db, HourlyReportRow),
        count(db, IssueEvent),
        count(db, QualityRecord),
    ) == (
        2,
        12,
        1,
        4,
    )


def test_rejects_without_detail_become_unspecified(db: Session, tmp_path: Path) -> None:
    book = six_hour_book()
    book.nok = [r for r in book.nok if r[0] != "X2"]  # hodina 4 dňa 7.12. má NOK 2 bez rozpisu
    import_excel(db, book.save(tmp_path / "b.xlsx"), now=NOW)
    rows = db.scalars(select(QualityRecord).where(QualityRecord.hour_id == "L01-20261207-04")).all()
    assert [(r.defect_type_code, r.qty) for r in rows] == [(None, 2)]


def test_night_shift_crosses_midnight(db: Session, tmp_path: Path) -> None:
    b = Book()
    b.add_shift(
        datetime(2026, 12, 7),
        start=time(22, 0),
        hours=8,
        cycle_s=60,
        am=(1, 10),
        pauza=(5, 30),
        produced=[45, 55, 45, 55, 28, 55, 55, 55],  # hodina 3: 10 min prestoja → max 50
    )
    b.prestoje.append(
        ["ST-016", "L01-20261207-03", datetime(2026, 12, 8, 0, 10), datetime(2026, 12, 8, 0, 20)]
    )
    result = import_excel(db, b.save(tmp_path / "night.xlsx"), now=NOW)
    assert result.models["L01-20261207-M"].start == time(22, 0)
    hour = db.get(HourlyReportRow, "L01-20261207-08")
    assert hour is not None and hour.slot_end == datetime(2026, 12, 8, 6, 0)
    assert all(c.ok for c in result.checks)


# --- kontroly a poškodené dáta ------------------------------------------------------------------


def test_check_flags_rejects_mismatch(db: Session, tmp_path: Path) -> None:
    book = six_hour_book()
    book.nok.append(["X9", "L01-20261209-06", 1, "Q-030"])  # hodina má NOK 0, detail 1
    with pytest.raises(DatasetError, match="L01-20261209-06"):
        import_excel(db, book.save(tmp_path / "b.xlsx"), now=NOW)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda b: setattr(b, "drop_column", "Vyrobene_ks"), "Vyrobene_ks"),
        (
            lambda b: b.prestoje.append(
                ["ST-999", "L01-20261207-02", datetime(2026, 12, 7, 15, 30), datetime(2026, 12, 7, 15, 35)]
            ),
            "ST-999",
        ),  # fmt: skip
        (
            lambda b: b.prestoje.append(
                ["ST-038", "L01-20991231-01", datetime(2099, 12, 31, 6, 0), datetime(2099, 12, 31, 6, 5)]
            ),
            "L01-20991231-01",
        ),  # fmt: skip
        (lambda b: b.nok.append(["X5", "L01-20261207-01", 1, "Q-999"]), "Q-999"),
        (lambda b: b.vyroba[0].__setitem__(11, -5), "Vyrobene_ks"),
        (lambda b: b.vyroba[0].__setitem__(10, 0), "Ideal_cyklus_s"),
        (lambda b: setattr(b, "target_oee", None), "E51"),
        (lambda b: b.vyroba.pop(2), "hour"),  # chýba 3. hodina zmeny
    ],
    ids=[
        "missing_column",
        "unknown_stop",
        "unknown_hour",
        "unknown_defect",
        "negative",
        "zero_cycle",
        "no_goal",
        "gap",
    ],  # fmt: skip
)
def test_corrupted_file_rolls_back(db: Session, tmp_path: Path, mutate: object, message: str) -> None:
    book = six_hour_book()
    mutate(book)  # type: ignore[operator]
    with pytest.raises(DatasetError, match=message):
        import_excel(db, book.save(tmp_path / "bad.xlsx"), now=NOW)
    assert (count(db, Shift), count(db, HourlyReportRow), count(db, ProductionRecord)) == (0, 0, 0)


def test_missing_file_is_dataset_error(db: Session, tmp_path: Path) -> None:
    with pytest.raises(DatasetError):
        import_excel(db, tmp_path / "nope.xlsx", now=NOW)


def test_existing_manual_hour_is_not_overwritten(db: Session, tmp_path: Path) -> None:
    path = six_hour_book().save(tmp_path / "six.xlsx")
    import_excel(db, path, now=NOW)
    prod = db.get(ProductionRecord, "L01-20261207-01")
    assert prod is not None
    prod.produced_qty = 33  # ručná oprava
    db.commit()
    import_excel(db, path, now=NOW)
    assert db.get(ProductionRecord, "L01-20261207-01").produced_qty == 33  # type: ignore[union-attr]


# --- doplnky z revízie --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("index", "value"), [(8, "ten"), (4, "first"), (7, None)], ids=["am", "hour_no", "interval"]
)
def test_non_numeric_cell_is_dataset_error(db: Session, tmp_path: Path, index: int, value: object) -> None:
    book = six_hour_book()
    book.vyroba[0][index] = value
    with pytest.raises(DatasetError):
        import_excel(db, book.save(tmp_path / "bad.xlsx"), now=NOW)
    assert count(db, Shift) == 0


def test_import_does_not_touch_settings_shift_model(db: Session, tmp_path: Path) -> None:
    from oee.persistence.models import ShiftModelRow

    import_excel(db, six_hour_book().save(tmp_path / "six.xlsx"), now=NOW)
    assert count(db, ShiftModelRow) == 0  # model zmeny zo súboru ide iba do snapshotu zmeny (D8)


def test_completing_missing_hours_completes_shift(db: Session, tmp_path: Path) -> None:
    path = six_hour_book().save(tmp_path / "six.xlsx")
    import_excel(db, path, now=NOW)
    for hour_id in ("L01-20261207-05", "L01-20261207-06"):
        db.delete(db.get(HourlyReportRow, hour_id))
    shift = db.get(Shift, "L01-20261207-M")
    assert shift is not None
    shift.status, shift.completed_at = "in_progress", None
    db.commit()
    again = import_excel(db, path, now=NOW)
    assert again.hours_added == 2
    shift = db.get(Shift, "L01-20261207-M")
    assert shift is not None and shift.status == "completed" and shift.completed_at == NOW


def test_existing_shift_with_other_model_is_reported(db: Session, tmp_path: Path) -> None:
    path = six_hour_book().save(tmp_path / "six.xlsx")
    import_excel(db, path, now=NOW)
    shift = db.get(Shift, "L01-20261207-M")
    assert shift is not None
    shift.model_snapshot = {**shift.model_snapshot, "target_oee": 0.9}
    db.commit()
    checks = {c.shift_id: c for c in import_excel(db, path, now=NOW).checks}
    assert checks["L01-20261207-M"].checks["model_snapshot"] is False
    assert checks["L01-20261209-M"].checks["model_snapshot"] is True


def test_issue_external_ref_has_seconds(db: Session, tmp_path: Path) -> None:
    import_excel(db, six_hour_book().save(tmp_path / "six.xlsx"), now=NOW)
    assert db.scalars(select(IssueEvent.external_ref)).one() == "L01-20261207-02|ST-038|15:10:00"

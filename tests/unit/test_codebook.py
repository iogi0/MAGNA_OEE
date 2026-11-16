"""Číselník problémov: všetky kódy sú voliteľné, nový kód sa dá doplniť (TASK §5.4, PLANNING D15)."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from oee.catalog.loader import load_catalog
from oee.persistence.models import DefectType, IssueType
from oee.persistence.seed import seed_codebook
from oee.services.codebook import CodeError, add_code, get_active_codes, list_codes

CATALOG = load_catalog()


@pytest.fixture
def db(session: Session) -> Session:
    seed_codebook(session, CATALOG)
    session.commit()
    return session


def test_all_codes_are_selectable_in_reporting(db: Session) -> None:
    codes = get_active_codes(db)
    assert len(codes.stop_codes) == 47 and len(codes.defect_codes) == 33  # 82 kódov bez dvoch „Other"
    assert set(CATALOG.top10_stop) <= codes.stop_codes and "ST-002" in codes.stop_codes
    assert (codes.other_stop_code, codes.other_defect_code) == (CATALOG.other_stop, CATALOG.other_defect)
    assert codes.other_stop_code not in codes.stop_codes


def test_list_codes_returns_full_codebook_without_other(db: Session) -> None:
    stops, defects = list_codes(db)
    assert len(stops) == 47 and len(defects) == 33
    assert [c.code for c in stops] == sorted(c.code for c in stops)
    st001 = next(c for c in stops if c.code == "ST-001")
    assert st001.category == "material_shortage"  # kategória z Top-10 má prednosť (D9)


def test_add_stop_code_gets_next_number_and_is_selectable(db: Session) -> None:
    new = add_code(db, kind="stop", name="Conveyor belt jammed", category="general")
    db.commit()
    assert new.code == "ST-049"  # posledný kód číselníka je ST-048 (Other)
    row = db.get(IssueType, "ST-049")
    assert row is not None and (row.name_en, row.category, row.is_other) == (
        "Conveyor belt jammed",
        "general",
        False,
    )
    assert "ST-049" in get_active_codes(db).stop_codes


def test_add_defect_code_numbering_is_independent(db: Session) -> None:
    first = add_code(db, kind="defect", name="Scratch on housing", category="general")
    second = add_code(db, kind="defect", name="Wrong label", category="general")
    db.commit()
    assert (first.code, second.code) == ("Q-035", "Q-036")
    assert db.get(DefectType, "Q-036") is not None


@pytest.mark.parametrize(
    ("kind", "name", "category", "message"),
    [
        ("stop", "  ", "general", "name"),
        ("stop", "x" * 201, "general", "name"),
        ("stop", "Belt jam", "unknown", "category"),
        ("stop", "Belt jam", "other", "category"),
        ("alarm", "Belt jam", "general", "kind"),
        ("stop", "Part unavailable at station", "general", "already exists"),
    ],
)
def test_invalid_new_code_is_rejected(db: Session, kind: str, name: str, category: str, message: str) -> None:
    with pytest.raises(CodeError, match=message):
        add_code(db, kind=kind, name=name, category=category)
    db.rollback()
    assert len(list_codes(db)[0]) == 47

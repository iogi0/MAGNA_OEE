"""P0-08: perzistencia — modely, engine/session, invarianty a seed (ARCHITECTURE §5, §10.2)."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest
from sqlalchemy import Engine, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from oee.catalog.loader import load_catalog
from oee.persistence.db import init_db, make_engine, make_session_factory
from oee.persistence.models import (
    AiOutput,
    DefectType,
    HourlyReportRow,
    IssueEvent,
    IssueType,
    ProductionRecord,
    QualityRecord,
    Shift,
    ShiftModelRow,
)
from oee.persistence.repositories import (
    QualityInvariantError,
    active_issues,
    find_issue_by_client_key,
    replace_hour_quality,
    soft_delete_issue,
)
from oee.persistence.seed import seed_codebook

NOW = datetime(2026, 11, 25, 14, 0)
SNAPSHOT = {"rate_per_hour": 60, "start": "06:00", "duration_min": 480}


# --- pomocné ------------------------------------------------------------------------------------


def add_shift(s: Session, shift_id: str = "L01-20261125-M", day: date = date(2026, 11, 25)) -> Shift:
    shift = Shift(
        shift_id=shift_id,
        line_id="L01",
        product_id="P01",
        date=day,
        shift_code="M",
        model_snapshot=SNAPSHOT,
        status="open",
        revision=0,
        created_at=NOW,
        updated_at=NOW,
    )
    s.add(shift)
    s.flush()
    return shift


def add_hour(
    s: Session, shift_id: str = "L01-20261125-M", hour_no: int = 1, hour_id: str | None = None
) -> HourlyReportRow:
    hour = HourlyReportRow(
        hour_id=hour_id or f"{shift_id[:12]}-{hour_no:02d}",
        shift_id=shift_id,
        hour_no=hour_no,
        slot_start=datetime(2026, 11, 25, 5 + hour_no, 0),
        slot_end=datetime(2026, 11, 25, 6 + hour_no, 0),
        planned_min=60,
        status="submitted",
        updated_at=NOW,
    )
    s.add(hour)
    s.flush()
    return hour


def add_issue(s: Session, hour_id: str, client_key: str | None, **kw: object) -> IssueEvent:
    event = IssueEvent(
        hour_id=hour_id,
        client_key=client_key,
        issue_type_code=kw.pop("code", "ST-038"),
        duration_min=kw.pop("duration_min", 10),
        source=kw.pop("source", "manual"),
        created_at=NOW,
        updated_at=NOW,
        **kw,
    )
    s.add(event)
    s.flush()
    return event


@pytest.fixture
def seeded(session: Session) -> Session:
    seed_codebook(session, load_catalog())
    session.flush()
    return session


# --- engine -------------------------------------------------------------------------------------


def test_foreign_keys_are_on(engine: Engine) -> None:
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_in_memory_database_is_shared_across_sessions(engine: Engine) -> None:
    factory = make_session_factory(engine)
    with factory() as s1:
        add_shift(s1)
        s1.commit()
    with factory() as s2:
        assert s2.scalar(select(func.count()).select_from(Shift)) == 1


def test_file_database_creates_folder_and_uses_wal(tmp_path: Path) -> None:
    db = tmp_path / "nested" / "dir" / "oee.db"
    eng = make_engine(db)
    try:
        init_db(eng)
        assert db.is_file()
        with eng.connect() as conn:
            assert conn.execute(text("PRAGMA journal_mode")).scalar() == "wal"
            assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1
            assert conn.execute(text("PRAGMA busy_timeout")).scalar() > 0
    finally:
        eng.dispose()  # Windows: zamknutý súbor inak blokuje zmazanie tmp_path


# --- obmedzenia ---------------------------------------------------------------------------------


def test_hour_with_unknown_shift_violates_foreign_key(session: Session) -> None:
    with pytest.raises(IntegrityError):
        add_hour(session, shift_id="L01-20991231-M")


def test_hour_no_unique_per_shift(session: Session) -> None:
    add_shift(session)
    add_hour(session, hour_no=1)
    with pytest.raises(IntegrityError):
        add_hour(session, hour_no=1, hour_id="other-id")


def test_shift_unique_per_line_date_code(session: Session) -> None:
    add_shift(session)
    with pytest.raises(IntegrityError):
        add_shift(session, shift_id="L01-20261125-M-dup")


def test_negative_production_rejected(session: Session) -> None:
    add_shift(session)
    hour = add_hour(session)
    session.add(ProductionRecord(hour_id=hour.hour_id, produced_qty=-1, rejects_qty=0, source="manual"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_client_key_unique_but_null_allowed_many_times(seeded: Session) -> None:
    add_shift(seeded)
    hour = add_hour(seeded)
    add_issue(seeded, hour.hour_id, None, source="import", external_ref="a")
    add_issue(seeded, hour.hour_id, None, source="import", external_ref="b")  # import nemá client_key
    add_issue(seeded, hour.hour_id, "ck-1")
    with pytest.raises(IntegrityError):
        add_issue(seeded, hour.hour_id, "ck-1")


def test_issue_type_code_must_exist(seeded: Session) -> None:
    add_shift(seeded)
    hour = add_hour(seeded)
    with pytest.raises(IntegrityError):
        add_issue(seeded, hour.hour_id, "ck", code="ST-999")


def test_issue_duration_must_be_positive(seeded: Session) -> None:
    add_shift(seeded)
    hour = add_hour(seeded)
    with pytest.raises(IntegrityError):
        add_issue(seeded, hour.hour_id, "ck", duration_min=0)


def test_continuation_references_existing_issue(seeded: Session) -> None:
    add_shift(seeded)
    h1, h2 = add_hour(seeded, hour_no=1), add_hour(seeded, hour_no=2)
    root = add_issue(seeded, h1.hour_id, "ck-1", start_at=datetime(2026, 11, 25, 6, 50))
    cont = add_issue(seeded, h2.hour_id, "ck-2", continues_issue_id=root.issue_id)
    assert cont.continues_issue_id == root.issue_id
    assert len(root.issue_id) == 36  # uuid
    with pytest.raises(IntegrityError):
        add_issue(seeded, h2.hour_id, "ck-3", continues_issue_id="missing")


def test_only_one_active_shift_model_per_line(session: Session) -> None:
    def model(version: int, active: bool) -> ShiftModelRow:
        return ShiftModelRow(
            version=version,
            line_id="L01",
            product_id="P01",
            line_rate_pcs_per_hour=45,
            shift_start="14:00",
            shift_length_min=360,
            break_min=20,
            break_hour_no=3,
            break_offset_min=10,
            am_min=15,
            am_hour_no=1,
            am_offset_min=0,
            target_oee=0.8,
            working_days=[0, 2, 4],
            grace_min=60,
            active=active,
            created_at=NOW,
        )

    session.add_all([model(1, False), model(2, True)])
    session.flush()
    session.add(model(3, True))
    with pytest.raises(IntegrityError):
        session.flush()


def test_ai_output_unique_by_facts_hash_key(session: Session) -> None:
    def out(facts_hash: str) -> AiOutput:
        return AiOutput(
            kind="shift_summary",
            subject_key="L01-20261125-M",
            facts_hash=facts_hash,
            model="qwen2.5:3b",
            lang="en",
            prompt_version="1",
            status="pending",
            created_at=NOW,
            updated_at=NOW,
        )

    session.add_all([out("a" * 64), out("b" * 64)])  # zmenené fakty = nový kľúč
    session.flush()
    session.add(out("a" * 64))
    with pytest.raises(IntegrityError):
        session.flush()


def test_ai_output_status_is_checked(session: Session) -> None:
    session.add(
        AiOutput(
            kind="shift_summary",
            subject_key="x",
            facts_hash="c" * 64,
            model="m",
            lang="en",
            prompt_version="1",
            status="weird",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


# --- soft delete a client_key -------------------------------------------------------------------


def test_soft_delete_hides_issue_but_keeps_row(seeded: Session) -> None:
    add_shift(seeded)
    hour = add_hour(seeded)
    a = add_issue(seeded, hour.hour_id, "ck-a")
    add_issue(seeded, hour.hour_id, "ck-b")
    soft_delete_issue(seeded, a.issue_id, NOW)
    assert [e.client_key for e in active_issues(seeded, hour.hour_id)] == ["ck-b"]
    assert seeded.get(IssueEvent, a.issue_id) is not None
    assert seeded.get(IssueEvent, a.issue_id).deleted_at == NOW  # type: ignore[union-attr]


def test_find_by_client_key_includes_soft_deleted(seeded: Session) -> None:
    add_shift(seeded)
    hour = add_hour(seeded)
    a = add_issue(seeded, hour.hour_id, "ck-a")
    soft_delete_issue(seeded, a.issue_id, NOW)
    found = find_issue_by_client_key(seeded, "ck-a")
    assert found is not None and found.issue_id == a.issue_id
    assert find_issue_by_client_key(seeded, "nope") is None


# --- invariant Σ quality_record.qty = rejects_qty ----------------------------------------------


def quality(s: Session, hour_id: str) -> list[tuple[str | None, int]]:
    rows = s.scalars(select(QualityRecord).where(QualityRecord.hour_id == hour_id)).all()
    return sorted((r.defect_type_code, r.qty) for r in rows)  # type: ignore[arg-type]


def test_quality_breakdown_must_sum_to_rejects(seeded: Session) -> None:
    add_shift(seeded)
    hour = add_hour(seeded)
    seeded.add(ProductionRecord(hour_id=hour.hour_id, produced_qty=50, rejects_qty=3, source="manual"))
    seeded.flush()
    with pytest.raises(QualityInvariantError):
        replace_hour_quality(seeded, hour.hour_id, [("Q-030", 1)], source="manual", now=NOW)


def test_quality_breakdown_replaces_previous_records(seeded: Session) -> None:
    add_shift(seeded)
    hour = add_hour(seeded)
    seeded.add(ProductionRecord(hour_id=hour.hour_id, produced_qty=50, rejects_qty=3, source="manual"))
    seeded.flush()
    replace_hour_quality(seeded, hour.hour_id, [("Q-030", 2), ("Q-031", 1)], source="manual", now=NOW)
    assert quality(seeded, hour.hour_id) == [("Q-030", 2), ("Q-031", 1)]
    replace_hour_quality(seeded, hour.hour_id, [("Q-020", 3)], source="manual", now=NOW)
    assert quality(seeded, hour.hour_id) == [("Q-020", 3)]


def test_rejects_without_breakdown_become_unspecified(seeded: Session) -> None:
    add_shift(seeded)
    hour = add_hour(seeded)
    seeded.add(ProductionRecord(hour_id=hour.hour_id, produced_qty=50, rejects_qty=4, source="manual"))
    seeded.flush()
    replace_hour_quality(seeded, hour.hour_id, [], source="manual", now=NOW)
    assert quality(seeded, hour.hour_id) == [(None, 4)]  # „Unspecified defect"


def test_zero_rejects_have_no_quality_records(seeded: Session) -> None:
    add_shift(seeded)
    hour = add_hour(seeded)
    seeded.add(ProductionRecord(hour_id=hour.hour_id, produced_qty=50, rejects_qty=0, source="manual"))
    seeded.flush()
    replace_hour_quality(seeded, hour.hour_id, [], source="manual", now=NOW)
    assert quality(seeded, hour.hour_id) == []


def test_quality_requires_production_record(seeded: Session) -> None:
    add_shift(seeded)
    hour = add_hour(seeded)
    with pytest.raises(QualityInvariantError):
        replace_hour_quality(seeded, hour.hour_id, [], source="manual", now=NOW)


def test_quality_qty_must_be_positive(seeded: Session) -> None:
    add_shift(seeded)
    hour = add_hour(seeded)
    seeded.add(
        QualityRecord(hour_id=hour.hour_id, defect_type_code="Q-030", qty=0, source="manual", created_at=NOW)
    )
    with pytest.raises(IntegrityError):
        seeded.flush()


# --- seed číselníka -----------------------------------------------------------------------------


def test_seed_inserts_full_codebook(seeded: Session) -> None:
    assert seeded.scalar(select(func.count()).select_from(IssueType)) == 48
    assert seeded.scalar(select(func.count()).select_from(DefectType)) == 34


def test_seed_active_top10_and_other(seeded: Session) -> None:
    active_st = seeded.scalars(select(IssueType.code).where(IssueType.active_top10)).all()
    active_q = seeded.scalars(select(DefectType.code).where(DefectType.active_top10)).all()
    assert len(active_st) == 11 and "ST-048" in active_st
    assert len(active_q) == 11 and "Q-034" in active_q
    other = seeded.get(IssueType, "ST-048")
    assert other is not None and other.is_other
    assert seeded.get(IssueType, "ST-038").is_other is False  # type: ignore[union-attr]


def test_seed_uses_effective_category(seeded: Session) -> None:
    assert seeded.get(IssueType, "ST-001").category == "material_shortage"  # type: ignore[union-attr]
    assert seeded.get(IssueType, "ST-017").category == "tool"  # type: ignore[union-attr]
    assert seeded.get(IssueType, "ST-016").category == "camera"  # type: ignore[union-attr]
    assert seeded.get(IssueType, "ST-002").category == "general"  # type: ignore[union-attr]
    assert seeded.get(DefectType, "Q-031").name_sk == "Okruh výrobku prepúšťa médium"  # type: ignore[union-attr]


def test_seed_is_idempotent_and_keeps_manager_choice(seeded: Session) -> None:
    st038 = seeded.get(IssueType, "ST-038")
    st002 = seeded.get(IssueType, "ST-002")
    assert st038 is not None and st002 is not None
    st038.active_top10, st002.active_top10 = False, True  # manažér v Settings vymenil kód
    seeded.flush()
    seed_codebook(seeded, load_catalog())
    seeded.flush()
    assert seeded.scalar(select(func.count()).select_from(IssueType)) == 48
    assert seeded.get(IssueType, "ST-038").active_top10 is False  # type: ignore[union-attr]
    assert seeded.get(IssueType, "ST-002").active_top10 is True  # type: ignore[union-attr]


def test_seed_does_not_create_shift_model(seeded: Session) -> None:
    assert seeded.scalar(select(func.count()).select_from(ShiftModelRow)) == 0  # D8


# --- doplnky z revízie --------------------------------------------------------------------------


def test_rejects_cannot_exceed_produced(session: Session) -> None:
    add_shift(session)
    hour = add_hour(session)
    session.add(ProductionRecord(hour_id=hour.hour_id, produced_qty=3, rejects_qty=4, source="manual"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_external_ref_is_unique(seeded: Session) -> None:
    add_shift(seeded)
    hour = add_hour(seeded)
    add_issue(seeded, hour.hour_id, None, source="import", external_ref="L01-20261125-04|ST-038|09:08")
    with pytest.raises(IntegrityError):
        add_issue(seeded, hour.hour_id, None, source="import", external_ref="L01-20261125-04|ST-038|09:08")


def test_deleting_hour_cascades_and_unlinks_continuation(seeded: Session) -> None:
    add_shift(seeded)
    h1, h2 = add_hour(seeded, hour_no=1), add_hour(seeded, hour_no=2)
    seeded.add(ProductionRecord(hour_id=h1.hour_id, produced_qty=40, rejects_qty=1, source="manual"))
    seeded.flush()
    replace_hour_quality(seeded, h1.hour_id, [("Q-030", 1)], source="manual", now=NOW)
    root = add_issue(seeded, h1.hour_id, "ck-1")
    cont = add_issue(seeded, h2.hour_id, "ck-2", continues_issue_id=root.issue_id)
    root_id, cont_id, h1_id = root.issue_id, cont.issue_id, h1.hour_id
    seeded.execute(text("DELETE FROM hourly_report WHERE hour_id = :h"), {"h": h1_id})
    seeded.expunge_all()
    assert seeded.get(IssueEvent, root_id) is None
    assert seeded.scalar(select(func.count()).select_from(QualityRecord)) == 0
    assert seeded.get(ProductionRecord, h1_id) is None
    assert seeded.get(IssueEvent, cont_id).continues_issue_id is None  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("field", "value"),
    [("break_min", -1), ("am_min", -1), ("break_hour_no", 0), ("am_hour_no", 0), ("grace_min", -1)],
)
def test_shift_model_row_basic_checks(session: Session, field: str, value: int) -> None:
    row = ShiftModelRow(
        version=1,
        line_id="L01",
        product_id="P01",
        line_rate_pcs_per_hour=45,
        shift_start="14:00",
        shift_length_min=360,
        break_min=20,
        break_hour_no=3,
        break_offset_min=10,
        am_min=15,
        am_hour_no=1,
        am_offset_min=0,
        target_oee=0.8,
        working_days=[0],
        grace_min=60,
        active=False,
        created_at=NOW,
    )
    setattr(row, field, value)
    session.add(row)
    with pytest.raises(IntegrityError):
        session.flush()


def test_new_code_in_existing_database_is_inactive(seeded: Session) -> None:
    seeded.execute(
        text("DELETE FROM issue_type WHERE code = 'ST-020'")
    )  # simulácia: kód pribudol do katalógu
    seeded.expire_all()
    assert seed_codebook(seeded, load_catalog()) == 1
    st020 = seeded.get(IssueType, "ST-020")
    assert st020 is not None and st020.active_top10 is False  # Top-10 z Settings sa nerozšíri na 11
    assert st020.category == "robot"

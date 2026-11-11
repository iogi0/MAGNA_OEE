"""P0-14: zmena a hodinové hlásenie (TASK §4.3, §5.3–5.6, PLANNING D8, D10)."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from oee.catalog.loader import load_catalog
from oee.contracts.hourly_report import HourlyReport
from oee.domain.shift_model import Allowance, ShiftModelConfig
from oee.persistence.models import IssueEvent, ProductionRecord, QualityRecord, Shift
from oee.persistence.seed import seed_codebook
from oee.services.reporting import (
    NoActiveShiftModel,
    effective_status,
    open_shift,
    save_hour,
)
from oee.services.shift_models import activate_shift_model, get_active_model

NOW = datetime(2026, 12, 9, 10, 0)  # audit (UTC)
DAY = date(2026, 12, 9)
CATALOG = load_catalog()
CODES = CATALOG.active_codes()
EIGHT = ShiftModelConfig(  # príklad z prezentácie (8 h, 60 ks/h)
    rate_per_hour=60,
    start=time(6, 0),
    duration_min=480,
    break_=Allowance(minutes=30, hour_no=5),
    am=Allowance(minutes=10, hour_no=1),
    target_oee=0.85,
    working_days=frozenset({0, 1, 2, 3, 4}),
)
SIX = ShiftModelConfig(  # iná konfigurácia (D8): 6 h od 14:00, 45 ks/h
    rate_per_hour=45,
    start=time(14, 0),
    duration_min=360,
    break_=Allowance(minutes=20, hour_no=3, offset_min=10),
    am=Allowance(minutes=15, hour_no=1),
    target_oee=0.8,
    working_days=frozenset({0, 2, 4}),
)


@pytest.fixture
def db(session: Session) -> Session:
    seed_codebook(session, CATALOG)
    session.commit()
    return session


def with_model(db: Session, config: ShiftModelConfig = EIGHT, grace_min: int = 60) -> Session:
    activate_shift_model(db, config, line="L01", product="P01", grace_min=grace_min, now=NOW)
    db.commit()
    return db


def report(hour_no: int, produced: int, rejects: int = 0, **kw: Any) -> HourlyReport:
    return HourlyReport.model_validate(
        {
            "hour_id": f"L01-20261209-{hour_no:02d}",
            "shift_id": "L01-20261209-M",
            "date": "2026-12-09",
            "hour_no": hour_no,
            "produced": produced,
            "rejects": rejects,
            **kw,
        }
    )


def issue(
    key: str, code: str = "ST-038", minutes: float = 10, start: str | None = None, **kw: Any
) -> dict[str, Any]:
    return {"client_key": key, "issue_type_code": code, "duration_min": minutes, "start_time": start, **kw}


def count(db: Session, model: type) -> int:
    return int(db.scalar(select(func.count()).select_from(model)) or 0)


def fill(db: Session, shift_id: str, hours: range, produced: int = 25) -> None:  # ≤ target každej hodiny
    for h in hours:
        result = save_hour(db, shift_id, report(h, produced), codes=CODES, now=NOW)
        assert result.saved, result.messages


# --- model zmeny a otvorenie zmeny --------------------------------------------------------------


def test_no_active_model_means_no_shift(db: Session) -> None:
    with pytest.raises(NoActiveShiftModel, match="Settings"):
        open_shift(db, line="L01", day=DAY, now=NOW)
    assert count(db, Shift) == 0


def test_new_model_version_deactivates_previous(db: Session) -> None:
    with_model(db, EIGHT)
    with_model(db, SIX)
    active = get_active_model(db, line="L01")
    assert active is not None and active.config == SIX and active.version == 2


def test_open_shift_snapshots_active_model(db: Session) -> None:
    shift = open_shift(with_model(db, SIX), line="L01", day=DAY, now=NOW)
    assert (shift.shift_id, shift.status, shift.revision) == ("L01-20261209-M", "open", 0)
    assert shift.model_snapshot["duration_min"] == 360
    with_model(db, EIGHT)  # zmena nastavení nemení snapshot existujúcej zmeny
    again = open_shift(db, line="L01", day=DAY, now=NOW)
    assert again.shift_id == shift.shift_id and again.model_snapshot["duration_min"] == 360
    assert count(db, Shift) == 1


def test_open_shift_reuses_imported_shift_without_active_model(db: Session) -> None:
    from tests.builders import add_shift

    add_shift(db, EIGHT, DAY, {1: (40, 0)}, status="in_progress")  # napr. importovaná zmena
    assert open_shift(db, line="L01", day=DAY, now=NOW).shift_id == "L01-20261209-M"
    assert count(db, Shift) == 1


# --- uloženie hodiny ----------------------------------------------------------------------------


def test_clean_hour_is_saved(db: Session) -> None:
    shift = open_shift(with_model(db), line="L01", day=DAY, now=NOW)
    result = save_hour(db, shift.shift_id, report(2, 58), codes=CODES, now=NOW)
    assert result.saved and result.messages == []
    assert (result.hour_status, result.shift_status, result.hours_submitted) == (
        "submitted",
        "in_progress",
        1,
    )
    assert db.get(ProductionRecord, "L01-20261209-02").produced_qty == 58  # type: ignore[union-attr]


def test_errors_block_saving(db: Session) -> None:
    shift = open_shift(with_model(db), line="L01", day=DAY, now=NOW)
    bad = report(2, 30, issues=[issue("k1", code="ST-048")])  # Other bez komentára (V11)
    result = save_hour(db, shift.shift_id, bad, codes=CODES, now=NOW)
    assert not result.saved
    assert any(m.rule == "V11" and m.level == "error" for m in result.messages)
    assert count(db, ProductionRecord) == 0 and count(db, IssueEvent) == 0


def test_warnings_save_with_needs_attention(db: Session) -> None:
    shift = open_shift(with_model(db), line="L01", day=DAY, now=NOW)
    result = save_hour(db, shift.shift_id, report(2, 0), codes=CODES, now=NOW)  # V12
    assert result.saved and result.hour_status == "needs_attention"


def test_issues_quality_and_start_time(db: Session) -> None:
    shift = open_shift(with_model(db), line="L01", day=DAY, now=NOW)
    r = report(
        4,
        31,
        rejects=2,
        rejects_by_defect=[
            {"defect_type_code": "Q-030", "qty": 1},
            {"defect_type_code": "Q-034", "qty": 1, "comment": "dent"},
        ],
        issues=[issue("k1", minutes=25, start="09:08"), issue("k2", code="ST-048", minutes=3, comment="jam")],
    )
    assert save_hour(db, shift.shift_id, r, codes=CODES, now=NOW).saved
    events = {e.client_key: e for e in db.scalars(select(IssueEvent))}
    assert events["k1"].start_at == datetime(2026, 12, 9, 9, 8)
    assert events["k2"].comment == "jam" and events["k2"].start_at is None
    quality = sorted((q.defect_type_code, q.qty, q.comment) for q in db.scalars(select(QualityRecord)))
    assert quality == [("Q-030", 1, None), ("Q-034", 1, "dent")]


def test_resubmission_is_idempotent(db: Session) -> None:
    shift = open_shift(with_model(db), line="L01", day=DAY, now=NOW)
    r = report(2, 40, issues=[issue("k1"), issue("k2", code="ST-016", minutes=5)])
    for _ in range(3):
        assert save_hour(db, shift.shift_id, r, codes=CODES, now=NOW).saved
    assert count(db, IssueEvent) == 2 and count(db, ProductionRecord) == 1


def test_missing_issue_is_soft_deleted_and_can_be_restored(db: Session) -> None:
    shift = open_shift(with_model(db), line="L01", day=DAY, now=NOW)
    save_hour(
        db,
        shift.shift_id,
        report(2, 40, issues=[issue("k1"), issue("k2", code="ST-016")]),
        codes=CODES,
        now=NOW,
    )
    save_hour(db, shift.shift_id, report(2, 40, issues=[issue("k1")]), codes=CODES, now=NOW)
    k2 = db.scalar(select(IssueEvent).where(IssueEvent.client_key == "k2"))
    assert k2 is not None and k2.deleted_at == NOW
    save_hour(
        db,
        shift.shift_id,
        report(2, 40, issues=[issue("k1"), issue("k2", code="ST-016")]),
        codes=CODES,
        now=NOW,
    )
    db.refresh(k2)
    assert k2.deleted_at is None
    assert count(db, IssueEvent) == 2  # obnovená, nie zduplikovaná


def test_edit_issue_by_issue_id(db: Session) -> None:
    shift = open_shift(with_model(db), line="L01", day=DAY, now=NOW)
    save_hour(db, shift.shift_id, report(2, 40, issues=[issue("k1", minutes=10)]), codes=CODES, now=NOW)
    issue_id = db.scalar(select(IssueEvent.issue_id))
    edited = report(2, 40, issues=[issue("k1-new-key", minutes=12, issue_id=issue_id)])
    assert save_hour(db, shift.shift_id, edited, codes=CODES, now=NOW).saved
    e = db.get(IssueEvent, issue_id)
    assert e is not None and e.duration_min == 12 and count(db, IssueEvent) == 1


def test_continuation_across_hours(db: Session) -> None:
    shift = open_shift(with_model(db), line="L01", day=DAY, now=NOW)
    save_hour(
        db,
        shift.shift_id,
        report(3, 40, issues=[issue("k1", minutes=10, start="08:50")]),
        codes=CODES,
        now=NOW,
    )
    root = db.scalar(select(IssueEvent.issue_id))
    cont = report(4, 40, issues=[issue("k2", minutes=15, start="09:00", continues_issue_id=root)])
    assert save_hour(db, shift.shift_id, cont, codes=CODES, now=NOW).saved
    e = db.scalar(select(IssueEvent).where(IssueEvent.client_key == "k2"))
    assert e is not None and e.continues_issue_id == root


def test_overlap_with_other_hour_is_rejected(db: Session) -> None:
    shift = open_shift(with_model(db), line="L01", day=DAY, now=NOW)
    save_hour(
        db,
        shift.shift_id,
        report(3, 40, issues=[issue("k1", minutes=30, start="08:50")]),
        codes=CODES,
        now=NOW,
    )
    result = save_hour(
        db,
        shift.shift_id,
        report(4, 40, issues=[issue("k2", minutes=5, start="09:05")]),
        codes=CODES,
        now=NOW,
    )
    assert not result.saved and any(m.rule == "V7" for m in result.messages)


def test_shift_id_mismatch_is_rejected(db: Session) -> None:
    shift = open_shift(with_model(db), line="L01", day=DAY, now=NOW)
    r = report(2, 40).model_copy(update={"shift_id": "L01-20261210-M"})
    with pytest.raises(ValueError, match="shift"):
        save_hour(db, shift.shift_id, r, codes=CODES, now=NOW)


# --- stavy zmeny --------------------------------------------------------------------------------


@pytest.mark.parametrize(("config", "hours"), [(EIGHT, 8), (SIX, 6)], ids=["8h", "6h"])
def test_all_hours_complete_the_shift(db: Session, config: ShiftModelConfig, hours: int) -> None:
    shift = open_shift(with_model(db, config), line="L01", day=DAY, now=NOW)
    fill(db, shift.shift_id, range(1, hours))
    assert db.get(Shift, shift.shift_id).status == "in_progress"  # type: ignore[union-attr]
    result = save_hour(db, shift.shift_id, report(hours, 30), codes=CODES, now=NOW)
    assert (result.shift_status, result.hours_submitted) == ("completed", hours)
    s = db.get(Shift, shift.shift_id)
    assert s is not None and s.completed_at == NOW and s.revision == 0


def test_edit_after_completion_increments_revision(db: Session) -> None:
    shift = open_shift(with_model(db, SIX), line="L01", day=DAY, now=NOW)
    fill(db, shift.shift_id, range(1, 7))
    save_hour(db, shift.shift_id, report(2, 35), codes=CODES, now=NOW)
    save_hour(db, shift.shift_id, report(3, 30), codes=CODES, now=NOW)
    s = db.get(Shift, shift.shift_id)
    assert s is not None and (s.status, s.revision) == ("completed", 2)


def test_incomplete_after_grace_is_evaluated_at_read(db: Session) -> None:
    shift = open_shift(with_model(db, EIGHT, grace_min=60), line="L01", day=DAY, now=NOW)
    fill(db, shift.shift_id, range(1, 4))
    s = db.get(Shift, shift.shift_id)
    assert s is not None
    # koniec zmeny 14:00 + grace 60 min → incomplete od 15:00 lokálneho času
    assert effective_status(s, now_local=datetime(2026, 12, 9, 15, 0), grace_min=60) == "in_progress"
    assert effective_status(s, now_local=datetime(2026, 12, 9, 15, 1), grace_min=60) == "incomplete"
    assert s.status == "in_progress"  # v DB sa nemení (žiadny plánovač, D10)


def test_open_shift_after_grace_is_incomplete_but_completed_never(db: Session) -> None:
    shift = open_shift(with_model(db, SIX), line="L01", day=DAY, now=NOW)
    later = datetime(2026, 12, 10, 12, 0)
    assert effective_status(shift, now_local=later, grace_min=0) == "incomplete"
    fill(db, shift.shift_id, range(1, 7))
    assert effective_status(shift, now_local=later, grace_min=0) == "completed"


def test_late_fill_turns_incomplete_into_completed(db: Session) -> None:
    shift = open_shift(with_model(db, SIX), line="L01", day=DAY, now=NOW)
    fill(db, shift.shift_id, range(1, 3))
    later = datetime(2026, 12, 12, 9, 0)
    assert effective_status(shift, now_local=later, grace_min=60) == "incomplete"
    fill(db, shift.shift_id, range(3, 7))  # dozapĺňanie neskôr (TASK §4.3)
    assert effective_status(shift, now_local=later, grace_min=60) == "completed"


# --- doplnky z revízie --------------------------------------------------------------------------


def test_invalid_model_is_not_saved(db: Session) -> None:
    from oee.domain.shift_model import ShiftModelError
    from oee.persistence.models import ShiftModelRow

    with pytest.raises(ShiftModelError):
        activate_shift_model(
            db,
            SIX.__class__(**{**SIX.__dict__, "rate_per_hour": 0}),
            line="L01",
            product="P01",
            grace_min=60,
            now=NOW,
        )
    assert count(db, ShiftModelRow) == 0


def test_grace_is_part_of_shift_snapshot(db: Session) -> None:
    shift = open_shift(with_model(db, EIGHT, grace_min=30), line="L01", day=DAY, now=NOW)
    with_model(db, EIGHT, grace_min=240)  # neskoršia zmena nastavení nemení starú zmenu
    assert shift.model_snapshot["grace_min"] == 30
    assert effective_status(shift, now_local=datetime(2026, 12, 9, 14, 31)) == "incomplete"


def test_old_shift_keeps_snapshot_after_new_model_version(db: Session) -> None:
    old = open_shift(with_model(db, EIGHT), line="L01", day=DAY, now=NOW)
    with_model(db, SIX)
    new = open_shift(db, line="L01", day=date(2026, 12, 10), now=NOW)
    assert (old.model_snapshot["duration_min"], new.model_snapshot["duration_min"]) == (480, 360)


def test_client_key_kept_when_matched_by_issue_id(db: Session) -> None:
    shift = open_shift(with_model(db), line="L01", day=DAY, now=NOW)
    save_hour(db, shift.shift_id, report(2, 40, issues=[issue("k1")]), codes=CODES, now=NOW)
    issue_id = db.scalar(select(IssueEvent.issue_id))
    save_hour(
        db, shift.shift_id, report(2, 40, issues=[issue("other", issue_id=issue_id)]), codes=CODES, now=NOW
    )
    assert db.get(IssueEvent, issue_id).client_key == "k1"  # type: ignore[union-attr]


@pytest.mark.parametrize(
    "case", ["foreign_issue_id", "foreign_client_key", "unknown_continuation", "duplicate_id"]
)
def test_inconsistent_request_rolls_back(db: Session, case: str) -> None:
    shift = open_shift(with_model(db), line="L01", day=DAY, now=NOW)
    save_hour(db, shift.shift_id, report(2, 40, issues=[issue("k1")]), codes=CODES, now=NOW)
    issue_id = db.scalar(select(IssueEvent.issue_id))
    items = {
        "foreign_issue_id": [issue("x", issue_id=issue_id)],
        "foreign_client_key": [issue("k1")],
        "unknown_continuation": [issue("x", continues_issue_id="missing")],
        "duplicate_id": [],
    }[case]
    hour_no = 2 if case == "duplicate_id" else 3
    if case == "duplicate_id":
        items = [issue("a", issue_id=issue_id), issue("b", code="ST-016", issue_id=issue_id)]
    with pytest.raises(ValueError):
        save_hour(db, shift.shift_id, report(hour_no, 33, issues=items), codes=CODES, now=NOW)
    assert db.get(ProductionRecord, "L01-20261209-03") is None
    assert db.get(ProductionRecord, "L01-20261209-02").produced_qty == 40  # type: ignore[union-attr]
    assert count(db, IssueEvent) == 1


def test_start_time_after_midnight_in_night_shift(db: Session) -> None:
    night = ShiftModelConfig(**{**EIGHT.__dict__, "start": time(22, 0)})
    shift = open_shift(with_model(db, night), line="L01", day=DAY, now=NOW)
    r = HourlyReport.model_validate(
        {
            "hour_id": "L01-20261209-03",
            "shift_id": shift.shift_id,
            "date": "2026-12-09",
            "hour_no": 3,  # 00:00–01:00 nasledujúceho dňa
            "produced": 40,
            "rejects": 0,
            "issues": [issue("k1", minutes=5, start="00:10")],
        }
    )
    assert save_hour(db, shift.shift_id, r, codes=CODES, now=NOW).saved
    assert db.scalar(select(IssueEvent.start_at)) == datetime(2026, 12, 10, 0, 10)

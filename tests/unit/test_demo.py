"""Demo seed (P0-25, TASK §14, §12.8): príkladový model iba bez aktívneho, demo zmena ST-038 → Q-030."""

from __future__ import annotations

from datetime import date, datetime, time

import pytest
from sqlalchemy.orm import Session

from oee.catalog.loader import load_catalog, load_example_settings
from oee.domain.shift_model import Allowance, ShiftModelConfig
from oee.persistence.models import Shift
from oee.persistence.seed import seed_codebook
from oee.services.analytics import build_period
from oee.services.demo import DemoError, build_demo_shift, ensure_active_model
from oee.services.shift_models import activate_shift_model, get_active_model

NOW = datetime(2026, 12, 9, 18, 0)
DAY = date(2026, 12, 1)


@pytest.fixture
def db(session: Session) -> Session:
    seed_codebook(session, load_catalog())
    session.commit()
    return session


def _six_hours() -> ShiftModelConfig:
    """Iná konfigurácia než príklad (D8): 6 h, 45 ks/h, bez prestávky."""
    return ShiftModelConfig(
        rate_per_hour=45,
        start=time(14, 0),
        duration_min=360,
        break_=Allowance(0, 1, 0),
        am=Allowance(10, 1, 0),
        target_oee=0.8,
        working_days=frozenset(range(7)),
    )


def test_example_model_activated_only_without_active_model(db: Session) -> None:
    assert ensure_active_model(db, line="L01", now=NOW) is True
    active = get_active_model(db, line="L01")
    assert active is not None
    assert active.config == load_example_settings().config

    assert ensure_active_model(db, line="L01", now=NOW) is False
    assert get_active_model(db, line="L01").version == active.version  # type: ignore[union-attr]


def test_manager_model_is_kept(db: Session) -> None:
    activate_shift_model(db, _six_hours(), line="L01", product="P9", grace_min=30, now=NOW)
    db.commit()
    assert ensure_active_model(db, line="L01", now=NOW) is False
    assert get_active_model(db, line="L01").config == _six_hours()  # type: ignore[union-attr]


@pytest.mark.parametrize("custom", [False, True])
def test_demo_shift_completes_and_shows_link(db: Session, custom: bool) -> None:
    if custom:
        activate_shift_model(db, _six_hours(), line="L01", product="P9", grace_min=30, now=NOW)
        db.commit()
    else:
        ensure_active_model(db, line="L01", now=NOW)

    shift_id = build_demo_shift(db, line="L01", day=DAY, now=NOW)

    shift = db.get(Shift, shift_id)
    assert shift is not None and shift.status == "completed"
    period = build_period(
        db, DAY, date(2026, 12, 31), line="L01", period_type="month", catalog=load_catalog(), now=NOW
    )
    links = {(x.cause, x.effect): x for x in period.problem_links}
    link = links[("ST-038", "Q-030")]
    assert link.link_type == "same_process"
    assert link.lift is not None and link.lift >= 2.0


def test_partial_demo_shift_leaves_hours_for_live_entry(db: Session) -> None:
    ensure_active_model(db, line="L01", now=NOW)
    shift_id = build_demo_shift(db, line="L01", day=DAY, now=NOW, hours=3)
    shift = db.get(Shift, shift_id)
    assert shift is not None and shift.status == "in_progress"


def test_existing_shift_is_not_overwritten(db: Session) -> None:
    ensure_active_model(db, line="L01", now=NOW)
    build_demo_shift(db, line="L01", day=DAY, now=NOW, hours=2)
    with pytest.raises(DemoError, match="already"):
        build_demo_shift(db, line="L01", day=DAY, now=NOW)


def test_too_short_shift_is_rejected(db: Session) -> None:
    config = ShiftModelConfig(
        rate_per_hour=45,
        start=time(14, 0),
        duration_min=240,
        break_=Allowance(0, 1, 0),
        am=Allowance(0, 1, 0),
        target_oee=0.8,
        working_days=frozenset(range(7)),
    )
    activate_shift_model(db, config, line="L01", product="P9", grace_min=30, now=NOW)
    db.commit()
    with pytest.raises(DemoError, match="at least"):
        build_demo_shift(db, line="L01", day=DAY, now=NOW)

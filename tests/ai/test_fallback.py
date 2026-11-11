"""P0-23: fakty pre AI (domain/facts) a fallback šablóny (TASK §7.F, §8.6, PLANNING D1, D8)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime, time

import pytest
from sqlalchemy.orm import Session

from oee.ai.fallback import link_explanation, shift_summary_text
from oee.ai.validator import validate_payload, validate_text
from oee.catalog.loader import load_catalog
from oee.config import PROJECT_ROOT
from oee.contracts.shift_analytics import ShiftAnalytics
from oee.domain.facts import link_facts, shift_summary_facts
from oee.domain.shift_model import Allowance, ShiftModelConfig
from oee.persistence.db import init_db, make_engine, make_session_factory
from oee.persistence.seed import seed_codebook
from oee.services.analytics import build_period, build_shift
from oee.services.importer import import_excel
from tests.builders import add_issue, add_shift

DATASET = PROJECT_ROOT / "data" / "raw" / "dummy_data.xlsx"
CATALOG = load_catalog()
NOW = datetime(2026, 12, 1, 9, 0)
CODES = frozenset({*CATALOG.top10_stop, *CATALOG.top10_defect})


@pytest.fixture(scope="module")
def dataset_db() -> Iterator[Session]:
    if not DATASET.is_file():
        pytest.skip("dataset data/raw/dummy_data.xlsx missing")
    engine = make_engine(None)
    init_db(engine)
    session = make_session_factory(engine)()
    seed_codebook(session, CATALOG)
    session.commit()
    import_excel(session, DATASET, now=NOW)
    yield session
    session.close()
    engine.dispose()


@pytest.fixture(scope="module")
def s25(dataset_db: Session) -> ShiftAnalytics:
    return build_shift(dataset_db, "L01-20261125-M", catalog=CATALOG, now=NOW)


# --- fakty ---------------------------------------------------------------------------------------


@pytest.mark.golden
def test_shift_facts_25_11(s25: ShiftAnalytics) -> None:
    f = shift_summary_facts(s25)
    assert (f["shift_id"], f["date"], f["weekday"]) == ("L01-20261125-M", "2026-11-25", "Wed")
    assert f["oee_pct"] == pytest.approx(78.18, abs=0.01) and f["goal_pct"] == pytest.approx(85)
    assert f["gap_pp"] == pytest.approx(-6.82, abs=0.01) and f["oee_status"] == "below_goal"
    assert (f["target_pcs"], f["produced_pcs"], f["good_pcs"]) == (440, 350, 344)
    assert f["production_vs_target_pct"] == pytest.approx(79.55, abs=0.01)
    assert (f["shortfall_pcs"], f["downtime_pcs"], f["speed_loss_pcs"], f["rejects_pcs"]) == pytest.approx(
        (96, 48, 42, 6)
    )
    assert (f["downtime_min"], f["downtime_events"]) == (pytest.approx(48), 3)
    assert f["reject_rate_pct"] == pytest.approx(1.71, abs=0.01)
    assert f["longest"] == {
        "code": "ST-038",
        "name": "Camera light module interrupted operation",
        "category": "Camera malfunction",
        "minutes": pytest.approx(25),
        "start": "09:08",
        "hour_no": 4,
    }


# --- Shift Summary fallback (§7.F) ---------------------------------------------------------------


@pytest.mark.golden
def test_fallback_summary_25_11_contains_task_7f_facts(s25: ShiftAnalytics) -> None:
    text = shift_summary_text(shift_summary_facts(s25), "en")
    for part in (
        "L01-20261125-M (Wed, 25.11.2026)",
        "OEE 78.2 %",
        "below the 85 % OEE goal by 6.8 p.p.",
        "350 of 440 target pieces (79.5 %)",
        "344 of them good",
        "Shortfall 96 pcs",
        "technical issues 48 pcs (48 min in 3 events)",
        "speed losses 42 pcs",
        "rejects 6 pcs (1.7 %)",
        "Camera malfunction / ST-038, 25 min at 09:08 (hour 4)",
    ):
        assert part in text, part


@pytest.mark.golden
@pytest.mark.parametrize("lang", ["en", "sk"])
def test_fallback_summary_passes_the_validator(s25: ShiftAnalytics, lang: str) -> None:
    facts = shift_summary_facts(s25)
    result = validate_text(shift_summary_text(facts, lang), facts, allowed_codes=CODES, lang=lang)  # type: ignore[arg-type]
    assert result.ok, result.problems


@pytest.mark.golden
def test_fallback_summary_in_slovak_uses_slovak_numbers(s25: ShiftAnalytics) -> None:
    text = shift_summary_text(shift_summary_facts(s25), "sk")
    assert "OEE 78,2 %" in text and "350 z 440" in text and "(79,5 %)" in text


def _six_hour_shift(session: Session, *, complete: bool) -> ShiftAnalytics:
    six = ShiftModelConfig(  # iná konfigurácia než príklad (D8): 6 h od 14:00, 45 ks/h
        rate_per_hour=45,
        start=time(14, 0),
        duration_min=360,
        break_=Allowance(minutes=20, hour_no=3, offset_min=10),
        am=Allowance(minutes=15, hour_no=1),
        target_oee=0.8,
        working_days=frozenset({0, 2, 4}),
    )
    day = date(2026, 12, 9)
    hours = {h: (40, 1) for h in range(1, 7 if complete else 3)}
    seed_codebook(session, CATALOG)
    add_shift(session, six, day, hours, status="completed" if complete else "in_progress")
    if complete:
        add_issue(session, day, 2, "ST-046", 7, datetime(2026, 12, 9, 15, 20))
    return build_shift(session, "L01-20261209-M", catalog=CATALOG, now=NOW)


def test_fallback_summary_other_configuration_goal_met_or_not(session: Session) -> None:
    a = _six_hour_shift(session, complete=True)
    facts = shift_summary_facts(a)
    text = shift_summary_text(facts, "en")
    assert "L01-20261209-M (Wed, 9.12.2026)" in text and "80 % OEE goal" in text
    assert "Leak test issue / ST-046, 7 min at 15:20 (hour 2)" in text
    assert validate_text(text, facts, allowed_codes=CODES, lang="en").ok


def test_fallback_summary_provisional_and_without_problems(session: Session) -> None:
    a = _six_hour_shift(session, complete=False)
    facts = shift_summary_facts(a)
    text = shift_summary_text(facts, "en")
    assert text.startswith("Provisional (2/6 hours submitted).")
    assert "No downtime was reported." in text and "Longest problem" not in text
    assert validate_text(text, facts, allowed_codes=CODES, lang="en").ok


# --- vysvetlenie väzby (§8.6, D1: bez odporúčaní) -----------------------------------------------


@pytest.mark.golden
def test_link_explanation_st038_q030(dataset_db: Session) -> None:
    month = build_period(
        dataset_db,
        date(2026, 11, 1),
        date(2026, 11, 30),
        line="L01",
        period_type="month",
        catalog=CATALOG,
        now=NOW,
    )
    link = next(x for x in month.problem_links if (x.cause, x.effect) == ("ST-038", "Q-030"))
    facts = link_facts(
        link,
        cause_name="Camera light module interrupted operation",
        effect_name="Product failed image-based check",
    )
    text = link_explanation(facts, "en")
    assert set(text) == {"fact", "link", "hypothesis", "impact"}
    assert (
        "4 stops of ST-038" in text["fact"]
        and "3 pcs of Q-030" in text["fact"]
        and "228 parts" in text["fact"]
    )
    assert "1.32 % vs 0.27 %" in text["fact"]
    assert (
        "lift 4.8×" in text["link"]
        and "same process (Camera)" in text["link"]
        and "confidence low" in text["link"]
    )
    assert (
        "to be verified" in text["hypothesis"].lower() and "not a proven cause" in text["hypothesis"].lower()
    )
    assert "102.4 pcs" in text["impact"] and "100 pcs" in text["impact"] and "2.4 pcs" in text["impact"]
    assert not any(
        word in " ".join(text.values()).lower() for word in ("recommend", "should ", "action")
    )  # D1
    assert validate_payload(text, facts, allowed_codes=CODES, lang="en").ok
    assert validate_payload(link_explanation(facts, "sk"), facts, allowed_codes=CODES, lang="sk").ok

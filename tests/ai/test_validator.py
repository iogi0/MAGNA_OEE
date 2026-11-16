"""P0-23: validátor textu AI — čísla a kódy iba z faktov (CLAUDE.md bod 1, ARCHITECTURE §10.6)."""

from __future__ import annotations

import pytest

from oee.ai.validator import extract_numbers, validate_text

FACTS = {  # výrez faktov zmeny 25.11.2026 (TASK §7.F, §12.3), podiely v %
    "shift_id": "L01-20261125-M",
    "date": "2026-11-25",
    "weekday": "Wed",
    "oee_pct": 78.18,
    "goal_pct": 85.0,
    "gap_pp": -6.82,
    "target_pcs": 440,
    "produced_pcs": 350,
    "production_vs_target_pct": 79.55,
    "good_pcs": 344,
    "shortfall_pcs": 96,
    "downtime_pcs": 48,
    "downtime_min": 48,
    "downtime_events": 3,
    "speed_loss_pcs": 42,
    "rejects_pcs": 6,
    "reject_rate_pct": 1.71,
    "month_target_pcs": 9240,
    "longest": {
        "code": "ST-038",
        "category": "Camera malfunction",
        "minutes": 25,
        "start": "09:08",
        "hour_no": 4,
    },
}
ALLOWED = frozenset({"ST-038", "ST-046", "Q-030"})


# --- čítanie čísel podľa jazyka --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "lang", "values"),
    [
        ("Target 9,240 pcs and OEE 78.2 %", "en", [9240, 78.2]),
        ("Target 9 240 ks a OEE 78,2 %", "sk", [9240, 78.2]),
        ("Target 9 240 ks", "sk", [9240]),  # nezlomiteľná medzera
        ("Shortfall −96 pcs, gap -6.8 p.p.", "en", [-96, -6.8]),
        ("1,234,567 and 0.5", "en", [1234567, 0.5]),
    ],
)
def test_extract_numbers_by_language(text: str, lang: str, values: list[float]) -> None:
    assert [n.value for n in extract_numbers(text, lang)] == pytest.approx(values)


def test_times_dates_codes_and_ids_are_not_numbers() -> None:
    text = "Shift L01-20261125-M (Wed, 25.11.2026, 2026-11-25): ST-038 at 09:08, hour 4, Q-030."
    assert [n.value for n in extract_numbers(text, "en")] == [4]


# --- prijaté texty ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "lang"),
    [
        (
            "Shift L01-20261125-M (Wed, 25.11.2026): OEE 78.2 % — below the 85 % goal by 6.8 p.p. "
            "The line produced 350 of 440 target pieces (79.5 %), 344 of them good. Shortfall 96 pcs: "
            "technical issues 48 pcs (48 min in 3 events), speed losses 42 pcs, rejects 6 pcs (1.7 %). "
            "Longest problem — Camera malfunction / ST-038, 25 min at 09:08 (hour 4).",
            "en",
        ),
        ("Mesačný target 9 240 ks; OEE zmeny 78,2 % (cieľ 85 %).", "sk"),
        ("Monthly target 9,240 pcs; OEE 78.18 %.", "en"),  # presnejšie zaokrúhlenie
        ("OEE 78 %.", "en"),  # 78 zodpovedá 78,18 pri zobrazení bez desatín
    ],
)
def test_correct_texts_pass(text: str, lang: str) -> None:
    result = validate_text(text, FACTS, allowed_codes=ALLOWED, lang=lang)
    assert result.ok, result.problems


# --- zamietnuté texty ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ("OEE 81.4 % today.", "81.4"),  # vymyslené číslo
        ("OEE 78.3 %.", "78.3"),  # zlé zaokrúhlenie (78,18 → 78,2)
        ("Target 9,250 pcs.", "9,250"),
        ("Main issue ST-099.", "ST-099"),  # neznámy kód
        ("Rejects of Q-031 rose.", "Q-031"),  # kód mimo faktov a Top-10
        ("It started at 10:15.", "10:15"),  # čas, ktorý vo faktoch nie je
        ("Shift of 26.11.2026 was weak.", "26.11.2026"),  # dátum mimo faktov
    ],
)
def test_invented_values_are_rejected(text: str, problem: str) -> None:
    result = validate_text(text, FACTS, allowed_codes=ALLOWED, lang="en")
    assert not result.ok
    assert any(problem in p for p in result.problems), result.problems


def test_sk_number_read_as_en_would_be_rejected() -> None:
    # „78,2" v angličtine = 782 (tisíce) → nie je vo faktoch; jazyk rozhoduje o čítaní
    assert validate_text("OEE 78,2 %", FACTS, allowed_codes=ALLOWED, lang="sk").ok
    assert not validate_text("OEE 78,2 %", FACTS, allowed_codes=ALLOWED, lang="en").ok


def test_validator_checks_nested_strings_of_a_json_payload() -> None:
    from oee.ai.validator import validate_payload

    payload = {
        "fact": "4 events of ST-038",
        "link": "lift 4.8",
        "hypothesis": "unstable light",
        "impact": "102.4 pcs",
    }
    facts = {"support": 4, "lift": 4.84, "combined_impact_pcs": 102.37, "cause": "ST-038"}
    assert validate_payload(payload, facts, allowed_codes=ALLOWED, lang="en").ok
    bad = {**payload, "impact": "150 pcs"}
    assert not validate_payload(bad, facts, allowed_codes=ALLOWED, lang="en").ok


# --- regresie z revízie P0-23 ---------------------------------------------------------------------


def test_en_two_decimals_at_sentence_end_is_a_number_not_a_date() -> None:
    facts = {"rate_in_window_pct": 10.53}
    assert validate_text("The rate in the window was 10.53.", facts, allowed_codes=ALLOWED, lang="en").ok


def test_time_must_match_exactly_not_as_substring() -> None:
    facts = {"start": "11:00"}
    result = validate_text("It started at 1:00.", facts, allowed_codes=ALLOWED, lang="en")
    assert not result.ok and any("1:00" in p for p in result.problems)
    assert validate_text("It started at 11:00.", facts, allowed_codes=ALLOWED, lang="en").ok
    assert validate_text("Start 9:08.", {"start": "09:08"}, allowed_codes=ALLOWED, lang="en").ok


def test_sk_adjacent_numbers_are_not_merged_into_thousands() -> None:
    facts = {"support": 3, "produced_in_window": 120}
    assert validate_text("Po 3 120 kusoch.", facts, allowed_codes=ALLOWED, lang="sk").ok  # 3 a 120
    assert validate_text("Target 9 240 ks.", {"t": 9240}, allowed_codes=ALLOWED, lang="sk").ok
    assert not validate_text("Target 9 250 ks.", {"t": 9240}, allowed_codes=ALLOWED, lang="sk").ok


def test_sk_short_date_still_checked() -> None:
    assert validate_text("Zmena 25.11. bola slabá.", FACTS, allowed_codes=ALLOWED, lang="sk").ok
    assert not validate_text("Zmena 26.11. bola slabá.", FACTS, allowed_codes=ALLOWED, lang="sk").ok

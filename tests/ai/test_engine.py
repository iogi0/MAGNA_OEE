"""P0-23: prompty s verziou a beh úlohy AI — validácia, 1 opakovanie, fallback (TASK §13.4)."""

from __future__ import annotations

import json

import pytest

from oee.ai.client import AiInvalidOutput, AiTimeout, AiUnavailable, FakeGenerator
from oee.ai.engine import run_task
from oee.ai.prompting import SCHEMAS, load_prompt

FACTS = {
    "shift_id": "L01-20261125-M",
    "date": "2026-11-25",
    "oee_pct": 78.18,
    "goal_pct": 85.0,
    "target_pcs": 440,
    "longest": {"code": "ST-038", "minutes": 25, "start": "09:08", "hour_no": 4},
}
CODES = frozenset({"ST-038", "Q-030"})
FALLBACK = {"text": "Template: OEE 78.2 %."}


def task(generator: object, lang: str = "en"):  # type: ignore[no-untyped-def]
    return run_task(
        generator,  # type: ignore[arg-type]
        load_prompt("shift_summary"),
        FACTS,
        lang=lang,  # type: ignore[arg-type]
        allowed_codes=CODES,
        fallback=lambda: FALLBACK,
    )


# --- prompty ------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["shift_summary", "link_explanation"])
def test_prompts_have_version_system_and_user_parts(name: str) -> None:
    prompt = load_prompt(name)
    assert prompt.name == name and prompt.version.startswith("v")
    assert "only" in prompt.system.lower() and "facts" in prompt.system.lower()
    assert "not a proven cause" in prompt.system.lower() or name == "shift_summary"
    user = prompt.render(FACTS, lang="sk")
    assert json.loads(user.split("FACTS:\n", 1)[1].split("\n\n", 1)[0]) == FACTS
    assert "Slovak" in user
    assert prompt.schema == SCHEMAS[name] and prompt.schema["type"] == "object"


def test_link_prompt_forbids_recommendations() -> None:
    assert "do not recommend" in load_prompt("link_explanation").system.lower()  # D1: odporúčania sú P2


def test_unknown_prompt() -> None:
    with pytest.raises(FileNotFoundError):
        load_prompt("improvement_plan")


# --- beh úlohy ----------------------------------------------------------------------------------


def test_valid_answer_is_used() -> None:
    fake = FakeGenerator([{"text": "OEE 78.2 % on L01-20261125-M; longest ST-038, 25 min at 09:08."}])
    result = task(fake)
    assert result.source == "local_ai" and result.attempts == 1
    assert result.payload == {"text": "OEE 78.2 % on L01-20261125-M; longest ST-038, 25 min at 09:08."}
    call = fake.calls[0]
    assert call.schema == SCHEMAS["shift_summary"] and "78.18" in call.user


def test_invented_number_retries_once_then_falls_back() -> None:
    fake = FakeGenerator([{"text": "OEE 81.4 %."}, {"text": "OEE 90 %."}])
    result = task(fake)
    assert (result.source, result.attempts, result.payload) == ("template", 2, FALLBACK)
    assert any("81.4" in p for p in result.problems)
    assert "81.4" in fake.calls[1].user  # druhý pokus dostane zoznam chýb


def test_invented_number_then_correct_answer() -> None:
    fake = FakeGenerator([{"text": "OEE 81.4 %."}, {"text": "OEE 78.2 %."}])
    result = task(fake)
    assert (result.source, result.attempts, result.payload) == ("local_ai", 2, {"text": "OEE 78.2 %."})


def test_invalid_json_shape_counts_as_failed_attempt() -> None:
    fake = FakeGenerator([AiInvalidOutput("no json"), {"wrong": "shape"}])
    result = task(fake)
    assert (result.source, result.attempts) == ("template", 2)


@pytest.mark.parametrize("error", [AiTimeout("slow"), AiUnavailable("down")])
def test_timeout_or_unavailable_falls_back_without_retry(error: Exception) -> None:
    fake = FakeGenerator([error, {"text": "OEE 78.2 %."}])
    result = task(fake)
    assert (result.source, result.attempts) == ("template", 1)  # nečakať 2 × timeout


def test_without_generator_is_template() -> None:
    result = task(None)
    assert (result.source, result.attempts, result.payload) == ("template", 0, FALLBACK)

"""Beh jednej úlohy lokálneho AI s validáciou a fallbackom (TASK §13.4, ARCHITECTURE §8).

Postup: prompt s faktmi → `Generator` (Ollama / FakeGenerator) → kontrola tvaru podľa schémy → validátor
(čísla a kódy iba z faktov) → pri neplatnom výstupe 1 opakovanie so zoznamom chýb → inak fallback šablóna.
Timeout alebo nedostupná Ollama → hneď fallback (bez druhého čakania). Bez generátora → vždy fallback.
"""

from __future__ import annotations

from collections.abc import Callable, Set
from dataclasses import dataclass, field
from typing import Any, Literal

from oee.ai.client import AiInvalidOutput, AiTimeout, AiUnavailable, Generator
from oee.ai.prompting import Prompt
from oee.ai.validator import Lang, validate_payload

MAX_ATTEMPTS = 2  # TASK §13.4: 1 opakovanie, potom fallback
Source = Literal["local_ai", "template"]


@dataclass
class TaskResult:
    payload: dict[str, Any]
    source: Source
    attempts: int
    problems: list[str] = field(default_factory=list)
    unavailable: bool = False
    """Fallback pre nedostupnú / pomalú Ollama (nie pre zlý text) — oplatí sa neskôr skúsiť znova."""


def _shape_problems(payload: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    problems = []
    for name in schema.get("required", []):
        value = payload.get(name)
        if not isinstance(value, str) or not value.strip():
            problems.append(f"field '{name}' must be a non-empty string")
    return problems


def _feedback(problems: list[str]) -> str:
    listed = "\n".join(f"- {p}" for p in problems)
    return f"Your previous answer was rejected:\n{listed}\nUse only values from the FACTS."


def run_task(
    generator: Generator | None,
    prompt: Prompt,
    facts: dict[str, Any],
    *,
    lang: Lang,
    allowed_codes: Set[str],
    fallback: Callable[[], dict[str, Any]],
) -> TaskResult:
    if generator is None:
        return TaskResult(fallback(), "template", 0)
    problems: list[str] = []
    seen: list[str] = []  # problémy všetkých pokusov (pre log a ladenie promptu)
    attempts = 0
    while attempts < MAX_ATTEMPTS:
        attempts += 1
        try:
            payload = generator.generate(
                system=prompt.render_system(lang),
                user=prompt.render(facts, lang=lang, feedback=_feedback(problems) if problems else ""),
                schema=prompt.schema,
            )
        except AiInvalidOutput as exc:
            problems = [str(exc)]
            seen += problems
            continue
        except (AiTimeout, AiUnavailable) as exc:  # druhý pokus by len predĺžil čakanie
            return TaskResult(fallback(), "template", attempts, [*seen, str(exc)], unavailable=True)
        problems = _shape_problems(payload, prompt.schema)
        if not problems:
            problems = validate_payload(
                payload, facts, allowed_codes=frozenset(allowed_codes), lang=lang
            ).problems
        if not problems:
            return TaskResult(payload, "local_ai", attempts, seen)
        seen += problems
    return TaskResult(fallback(), "template", attempts, seen)

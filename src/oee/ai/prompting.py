"""Prompty s verziou (`ai/prompts/*.md`) a JSON schémy výstupu pre Ollama `format` (TASK §13.4).

Súbor promptu: prvý riadok `<!-- version: vN -->`, potom sekcie `## system` a `## user`. Zástupné symboly
`{language}`, `{facts}`, `{feedback}` sa nahrádzajú textovo (prompt obsahuje aj JSON so zloženými zátvorkami).
Verzia je súčasťou kľúča cache `ai_output` — zmena promptu = nové generovanie.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from oee.ai.validator import Lang

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
LANGUAGE_NAMES: dict[str, str] = {"en": "English", "sk": "Slovak"}
VERSION = re.compile(r"<!--\s*version:\s*(v[\w.]+)\s*-->")

SCHEMAS: dict[str, dict[str, Any]] = {
    "shift_summary": {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    },
    "link_explanation": {
        "type": "object",
        "properties": {
            "fact": {"type": "string"},
            "link": {"type": "string"},
            "hypothesis": {"type": "string"},
            "impact": {"type": "string"},
        },
        "required": ["fact", "link", "hypothesis", "impact"],
    },
}


@dataclass(frozen=True)
class Prompt:
    name: str
    version: str
    system_template: str
    user_template: str

    @property
    def schema(self) -> dict[str, Any]:
        return SCHEMAS[self.name]

    @property
    def system(self) -> str:
        return self.system_template

    def render_system(self, lang: Lang) -> str:
        return self.system_template.replace("{language}", LANGUAGE_NAMES[lang])

    def render(self, facts: dict[str, Any], *, lang: Lang, feedback: str = "") -> str:
        """Používateľská časť promptu: fakty ako kanonický JSON + prípadná spätná väzba validátora."""
        return (
            self.user_template.replace("{language}", LANGUAGE_NAMES[lang])
            .replace("{facts}", json.dumps(facts, ensure_ascii=False, sort_keys=True, indent=1))
            .replace("{feedback}", feedback)
            .strip()
        )


def _section(text: str, name: str) -> str:
    match = re.search(rf"^## {name}\s*$(.*?)(?=^## |\Z)", text, flags=re.M | re.S)
    if not match:
        raise ValueError(f"prompt section '## {name}' is missing")
    return match.group(1).strip()


def load_prompt(name: str) -> Prompt:
    """Prompt podľa mena súboru (`shift_summary`, `link_explanation`).

    Raises:
        FileNotFoundError: prompt neexistuje.
        ValueError: chýba verzia alebo sekcia.
    """
    path = PROMPTS_DIR / f"{name}.md"
    if name not in SCHEMAS or not path.is_file():
        raise FileNotFoundError(f"unknown prompt {name!r}")
    text = path.read_text(encoding="utf-8")
    version = VERSION.search(text)
    if not version:
        raise ValueError(f"prompt {name} has no version header")
    return Prompt(name, version.group(1), _section(text, "system"), _section(text, "user"))

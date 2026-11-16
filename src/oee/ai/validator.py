"""Validátor textu lokálneho AI (CLAUDE.md bod 1, TASK §13.4, ARCHITECTURE §10.6).

AI nesmie počítať ani vymýšľať: každé číslo v texte musí zodpovedať niektorému faktu a každý kód
(ST-xxx / Q-xxx) musí byť vo faktoch alebo v povolenom zozname (Top-10 / číselník). Pravidlá:
- čísla sa čítajú podľa jazyka: `en` „9,240" a „78.2", `sk` „9 240" (aj NBSP) a „78,2";
- zhoda = rozdiel ≤ polovica poslednej zobrazenej číslice (78.2 ≈ 78,18; 78 ≈ 78,18; 78.3 ≠ 78,18);
- znamienko sa nehodnotí („−96" aj „96" pre nedobór 96), text ho vyjadruje slovami;
- časy (09:08), dátumy (25.11.2026, 2026-11-25, 25.11.) a ID zmeny sa kontrolujú osobitne.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

Lang = Literal["en", "sk"]
EPS = 1e-9

SHIFT_ID = re.compile(r"\b[A-Z]\d{2}-\d{8}-[A-Z0-9]{1,3}\b")
CODE = re.compile(r"\b(?:ST|Q)-\d{3}\b")
TIME = re.compile(r"\b\d{1,2}:\d{2}\b")
ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
DOT_DATE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b|\b(\d{2})\.(\d{2})\.(?!\d)")
# krátky tvar „25.11." iba v slovenčine — v angličtine je „10.53." číslo na konci vety
DATE_PATTERN = {
    "en": re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b"),
    "sk": DOT_DATE,
}
MINUS = "-−"
NUMBER = {
    "en": re.compile(
        rf"(?<![\w.,])[{MINUS}]?\d{{1,3}}(?:,\d{{3}})+(?:\.\d+)?|(?<![\w.,])[{MINUS}]?\d+(?:\.\d+)?"
    ),
    "sk": re.compile(
        rf"(?<![\w.,])[{MINUS}]?\d{{1,3}}(?:[   ]\d{{3}})+(?:,\d+)?|(?<![\w.,])[{MINUS}]?\d+(?:,\d+)?"
    ),
}


# desatinné číslo v tvare druhého jazyka (en „78,2", sk „78.2") je nejednoznačné → zamietnuť
WRONG_DECIMAL = {
    "en": re.compile(r"(?<![\w.,])\d+,\d{1,2}(?![\d,])"),
    "sk": re.compile(r"(?<![\w.,])\d+\.\d+(?![\d.])"),
}


@dataclass(frozen=True)
class FoundNumber:
    raw: str
    value: float
    decimals: int


@dataclass
class ValidationResult:
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


# --- čítanie textu --------------------------------------------------------------------------------


def _mask(text: str, pattern: re.Pattern[str]) -> str:
    """Nahradí zhody medzerami (rovnaká dĺžka), aby sa ich číslice nečítali ako čísla."""
    return pattern.sub(lambda m: " " * len(m.group(0)), text)


def _strip_special(text: str, lang: Lang = "sk") -> str:
    for pattern in (SHIFT_ID, CODE, TIME, ISO_DATE, DATE_PATTERN[lang]):
        text = _mask(text, pattern)
    return text


def _parse(raw: str, lang: Lang) -> FoundNumber:
    negative = raw[0] in MINUS
    body = raw[1:] if negative else raw
    if lang == "en":
        body = body.replace(",", "")
        decimals = len(body.split(".")[1]) if "." in body else 0
    else:
        body = re.sub(r"[   ]", "", body).replace(",", ".")
        decimals = len(body.split(".")[1]) if "." in body else 0
    value = float(body)
    return FoundNumber(raw, -value if negative else value, decimals)


def extract_numbers(text: str, lang: Lang) -> list[FoundNumber]:
    """Čísla v texte bez časov, dátumov, kódov a ID zmeny."""
    return [_parse(m.group(0), lang) for m in NUMBER[lang].finditer(_strip_special(text, lang))]


# --- fakty ----------------------------------------------------------------------------------------


def _walk(value: Any) -> Iterator[Any]:
    if isinstance(value, Mapping):
        for v in value.values():
            yield from _walk(v)
    elif isinstance(value, list | tuple | set | frozenset):
        for v in value:
            yield from _walk(v)
    else:
        yield value


def _fact_numbers(facts: Mapping[str, Any]) -> list[float]:
    return [float(v) for v in _walk(facts) if isinstance(v, int | float) and not isinstance(v, bool)]


def _fact_strings(facts: Mapping[str, Any]) -> set[str]:
    return {v for v in _walk(facts) if isinstance(v, str)}


def _fact_dates(strings: set[str]) -> set[tuple[int, int, int]]:
    dates = set()
    for s in strings:
        for m in ISO_DATE.finditer(s):
            dates.add((int(m.group(1)), int(m.group(2)), int(m.group(3))))
    return dates


def _parts_match(number: FoundNumber, lang: Lang, facts: list[float]) -> bool:
    """sk „3 120" môžu byť dve čísla (3 a 120), nielen tisíce — prijme sa, ak sedia všetky časti."""
    parts = re.split(r"[   ]", number.raw)
    return len(parts) > 1 and all(_matches(_parse(part, lang), facts) for part in parts if part)


def _matches(number: FoundNumber, facts: list[float]) -> bool:
    tolerance = 0.5 * 10 ** (-number.decimals) + EPS
    return any(abs(abs(number.value) - abs(f)) <= tolerance for f in facts)


# --- validácia ------------------------------------------------------------------------------------


def validate_text(
    text: str, facts: Mapping[str, Any], *, allowed_codes: frozenset[str] | set[str], lang: Lang
) -> ValidationResult:
    result = ValidationResult()
    strings = _fact_strings(facts)
    joined = " ".join(strings)

    known_codes = set(CODE.findall(joined)) | set(allowed_codes)
    for code in CODE.findall(text):
        if code not in known_codes:
            result.problems.append(f"code {code} is not in the facts")
    for shift_id in SHIFT_ID.findall(text):
        if shift_id not in joined:
            result.problems.append(f"shift id {shift_id} is not in the facts")
    fact_times = {(int(h), int(m)) for h, m in (t.split(":") for t in TIME.findall(joined))}
    for time_ in TIME.findall(text):
        hours, minutes = time_.split(":")
        if (int(hours), int(minutes)) not in fact_times:
            result.problems.append(f"time {time_} is not in the facts")

    dates = _fact_dates(strings)
    for m in ISO_DATE.finditer(text):
        if (int(m.group(1)), int(m.group(2)), int(m.group(3))) not in dates:
            result.problems.append(f"date {m.group(0)} is not in the facts")
    for m in DATE_PATTERN[lang].finditer(text):
        if m.group(3):  # plný dátum (v oboch jazykoch); krátky „25.11." iba sk
            key = (int(m.group(3)), int(m.group(2)), int(m.group(1)))
            found = key in dates
        else:
            found = any((d, mth) == (int(m.group(4)), int(m.group(5))) for _, mth, d in dates)
        if not found:
            result.problems.append(f"date {m.group(0)} is not in the facts")

    for m in WRONG_DECIMAL[lang].finditer(_strip_special(text, lang)):
        result.problems.append(f"number {m.group(0)} uses the wrong decimal separator for '{lang}'")
    numbers = _fact_numbers(facts)
    for number in extract_numbers(text, lang):
        if not (_matches(number, numbers) or _parts_match(number, lang, numbers)):
            result.problems.append(f"number {number.raw.strip()} is not in the facts")
    return result


def validate_payload(
    payload: Mapping[str, Any],
    facts: Mapping[str, Any],
    *,
    allowed_codes: frozenset[str] | set[str],
    lang: Lang,
) -> ValidationResult:
    """Overí všetky textové polia JSON výstupu AI."""
    result = ValidationResult()
    for value in _walk(payload):
        if isinstance(value, str):
            result.problems += validate_text(value, facts, allowed_codes=allowed_codes, lang=lang).problems
    return result


def iso_to_dot(day: date) -> str:
    """Pomocník pre šablóny: dátum v tvare 25.11.2026 (validátor ho porovná s ISO dátumom faktov)."""
    return f"{day.day}.{day.month}.{day.year}"

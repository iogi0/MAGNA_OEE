"""Číselník problémov (TASK §5.4, PLANNING D15).

- V hodinovom hlásení sú voliteľné **všetky** kódy číselníka (ST aj Q) a „Other" s povinným komentárom.
- V Settings sa číselník iba zobrazuje a dá sa doň doplniť nový kód (ďalšie číslo v rade ST-xxx / Q-xxx).
- Top-10 sa nevyberá ručne: v analytike sa počíta z frekvencie (týždeň, mesiac). Príznak `active_top10`
  zo seedu je iba štartovací zoznam pre prázdne dáta (TASK §5.4).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from oee.catalog.loader import OTHER_CATEGORY
from oee.domain.validation import ActiveCodes
from oee.persistence.models import DefectType, IssueType

Kind = Literal["stop", "defect"]
PREFIX: dict[str, str] = {"stop": "ST", "defect": "Q"}
NAME_MAX = 200  # dĺžka stĺpca name_en
CODE_NUMBER = re.compile(r"^[A-Z]+-(\d+)$")


class CodeError(ValueError):
    """Nový kód sa nedá pridať (nič sa neuloží)."""


@dataclass(frozen=True)
class CodeChoice:
    code: str
    name_en: str
    category: str


def _other_code[T: (IssueType, DefectType)](session: Session, model: type[T]) -> str:
    code = session.scalar(select(model.code).where(model.is_other))
    if code is None:
        raise LookupError(f"codebook has no Other code in {model.__tablename__} (seed missing?)")
    return code


def _codes[T: (IssueType, DefectType)](session: Session, model: type[T]) -> list[T]:
    return list(session.scalars(select(model).where(model.is_other.is_(False)).order_by(model.code)))


def get_active_codes(session: Session) -> ActiveCodes:
    """Kódy, ktoré smie hodinové hlásenie použiť: celý číselník + „Other"."""
    return ActiveCodes(
        stop_codes=frozenset(r.code for r in _codes(session, IssueType)),
        defect_codes=frozenset(r.code for r in _codes(session, DefectType)),
        other_stop_code=_other_code(session, IssueType),
        other_defect_code=_other_code(session, DefectType),
    )


def list_codes(session: Session) -> tuple[list[CodeChoice], list[CodeChoice]]:
    """Celý číselník bez „Other", zoradený podľa kódu: (ST, Q)."""

    def rows[T: (IssueType, DefectType)](model: type[T]) -> list[CodeChoice]:
        return [CodeChoice(r.code, r.name_en, r.category) for r in _codes(session, model)]

    return rows(IssueType), rows(DefectType)


def code_categories(session: Session) -> list[str]:
    """Kategórie, do ktorých sa dá zaradiť nový kód (všetky použité v číselníku okrem „Other")."""
    used = {*session.scalars(select(IssueType.category)), *session.scalars(select(DefectType.category))}
    return sorted(used - {OTHER_CATEGORY})


def _insert[T: (IssueType, DefectType)](
    session: Session, model: type[T], *, prefix: str, kind: str, name: str, category: str
) -> CodeChoice:
    if name.casefold() in {n.casefold() for n in session.scalars(select(model.name_en))}:
        raise CodeError(f"A {kind} code named {name!r} already exists.")
    existing = list(session.scalars(select(model.code)))
    numbers = [int(m.group(1)) for c in existing if (m := CODE_NUMBER.match(c))]
    width = max((len(m.group(1)) for c in existing if (m := CODE_NUMBER.match(c))), default=3)
    code = f"{prefix}-{max(numbers, default=0) + 1:0{width}d}"
    session.add(
        model(code=code, name_en=name, name_sk=name, category=category, active_top10=False, is_other=False)
    )
    session.flush()
    return CodeChoice(code, name, category)


def add_code(session: Session, *, kind: str, name: str, category: str) -> CodeChoice:
    """Pridá nový kód s ďalším číslom v rade ST-xxx / Q-xxx (iba flush; commit robí volajúci).

    Raises:
        CodeError: neznámy druh, prázdny / príliš dlhý / duplicitný názov alebo neznáma kategória.
    """
    if kind not in PREFIX:
        raise CodeError(f"Unknown code kind {kind!r} (expected stop or defect).")
    name = name.strip()
    if not name or len(name) > NAME_MAX:
        raise CodeError(f"Enter a name of 1–{NAME_MAX} characters.")
    if category not in code_categories(session):
        raise CodeError(f"Unknown category {category!r}.")
    args = {"prefix": PREFIX[kind], "kind": kind, "name": name, "category": category}
    if kind == "stop":
        return _insert(session, IssueType, **args)
    return _insert(session, DefectType, **args)

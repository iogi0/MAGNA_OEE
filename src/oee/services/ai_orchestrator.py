"""Orchestrácia lokálneho AI (ARCHITECTURE §6, §10.6; TASK §7.F, §8.6; PLANNING D1).

- Úloha (`AiJob`) = fakty z kódu + prompt s verziou + kľúč cache `ai_output`.
- `lookup` (v požiadavke): hotový výstup pre aktuálny `facts_hash` → zobraziť; inak rezervovať `pending`
  (UNIQUE kľúč = zámok proti dvojitému generovaniu) a povedať volajúcemu, aby spustil `run_job` na pozadí.
  Medzitým sa zobrazí fallback text. Zaseknutý `pending` (starší ako `stale_after`) sa prevezme.
- `run_job` (na pozadí): vlastná DB session, globálny zámok (sekvenčná fronta), `run_task` (validácia,
  1 opakovanie, fallback), uloženie `ok` / `fallback`.
- AI vypnuté (`OEE_AI_ENABLED=false`) → hneď fallback, nič sa neukladá.
Shift Summary a vysvetlenia väzieb neobsahujú odporúčania (D1).
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from oee.ai.client import AiError, Generator, facts_hash
from oee.ai.engine import run_task
from oee.ai.fallback import link_explanation, shift_summary_text
from oee.ai.prompting import load_prompt
from oee.ai.validator import Lang
from oee.catalog.loader import Catalog
from oee.domain.facts import link_facts, shift_summary_facts
from oee.persistence.models import DefectType, IssueType
from oee.persistence.repositories import AiKey, claim_ai_output, finish_ai_output, get_ai_output
from oee.services.analytics import build_period, build_shift

Kind = Literal["shift_summary", "link_explanation"]
KINDS: tuple[Kind, ...] = ("shift_summary", "link_explanation")
_QUEUE = threading.Lock()  # ARCHITECTURE §10.6: AI úlohy sekvenčne


@dataclass(frozen=True)
class AiConfig:
    model: str
    lang: Lang
    stale_after: timedelta
    """Pending starší ako toto (2 × timeout) = zlyhané generovanie → nový pokus."""


@dataclass(frozen=True)
class AiJob:
    kind: Kind
    key: AiKey
    facts: dict[str, Any]
    allowed_codes: frozenset[str]

    def fallback(self, lang: Lang) -> dict[str, Any]:
        if self.kind == "shift_summary":
            return {"text": shift_summary_text(self.facts, lang)}
        return dict(link_explanation(self.facts, lang))


@dataclass
class AiState:
    status: Literal["ready", "pending", "start"]
    """`start` = volajúci rezervoval generovanie a má spustiť `run_job`."""
    payload: dict[str, Any]
    source: Literal["local_ai", "template"]
    pending: bool = field(init=False)

    def __post_init__(self) -> None:
        self.pending = self.status != "ready"


def _codes(session: Session) -> frozenset[str]:
    """Kódy, ktoré smie text obsahovať: celý číselník (D15), vrátane kódov pridaných v Settings."""
    return frozenset([*session.scalars(select(IssueType.code)), *session.scalars(select(DefectType.code))])


def _key(kind: Kind, subject: str, facts: dict[str, Any], config: AiConfig) -> AiKey:
    return AiKey(kind, subject, facts_hash(facts), config.model, config.lang, load_prompt(kind).version)


def shift_summary_job(
    session: Session, shift_id: str, *, catalog: Catalog, config: AiConfig, now: datetime
) -> AiJob:
    """Úloha Shift Summary (§7.F) pre zmenu; fakty zo `ShiftAnalytics`.

    Raises:
        services.analytics.ShiftNotFound: zmena neexistuje.
    """
    facts = shift_summary_facts(build_shift(session, shift_id, catalog=catalog, now=now))
    return AiJob("shift_summary", _key("shift_summary", shift_id, facts, config), facts, _codes(session))


def link_job(
    session: Session,
    *,
    start: date,
    end: date,
    period_key: str,
    cause: str,
    effect: str,
    line: str,
    catalog: Catalog,
    config: AiConfig,
    now: datetime,
) -> AiJob | None:
    """Úloha vysvetlenia väzby (§8.6) za obdobie; None, ak pár v období nie je väzbou."""
    period = build_period(session, start, end, line=line, period_type="month", catalog=catalog, now=now)
    link = next((x for x in period.problem_links if (x.cause, x.effect) == (cause, effect)), None)
    if link is None:
        return None
    names = {code: name for code, name in session.execute(select(IssueType.code, IssueType.name_en))}
    names |= {code: name for code, name in session.execute(select(DefectType.code, DefectType.name_en))}
    facts = link_facts(link, cause_name=names.get(cause, cause), effect_name=names.get(effect, effect))
    subject = f"{period_key}:{cause}>{effect}"
    return AiJob("link_explanation", _key("link_explanation", subject, facts, config), facts, _codes(session))


def lookup(session: Session, job: AiJob, *, config: AiConfig, now: datetime, ai_enabled: bool) -> AiState:
    """Stav AI výstupu pre aktuálne fakty; chýbajúci výstup rezervuje (commit robí volajúci)."""
    fallback = job.fallback(config.lang)
    if not ai_enabled:
        return AiState("ready", fallback, "template")
    row = get_ai_output(session, job.key)
    if row is not None and row.status in ("ok", "fallback") and row.payload:
        source: Literal["local_ai", "template"] = "local_ai" if row.status == "ok" else "template"
        return AiState("ready", dict(row.payload), source)
    if row is not None and row.status == "pending" and now - row.updated_at <= config.stale_after:
        return AiState("pending", fallback, "template")
    if row is not None and row.status == "error" and now - row.updated_at <= config.stale_after:
        return AiState("ready", fallback, "template")
    claimed = claim_ai_output(session, job.key, now=now, stale_after=config.stale_after)
    return AiState("start" if claimed is not None else "pending", fallback, "template")


def run_job(
    factory: sessionmaker[Session],
    job: AiJob,
    generator: Generator | None,
    *,
    config: AiConfig,
    now: Callable[[], datetime],
) -> None:
    """Vygeneruje text pre rezervovaný kľúč a uloží ho (beží na pozadí, vlastná session)."""
    with _QUEUE, factory() as session:
        row = get_ai_output(session, job.key)
        if row is None or row.status != "pending":
            return  # medzitým hotové alebo zmazané
        try:
            result = run_task(
                generator,
                load_prompt(job.kind),
                job.facts,
                lang=config.lang,
                allowed_codes=job.allowed_codes,
                fallback=lambda: job.fallback(config.lang),
            )
        except AiError:  # poistka — run_task chyby AI sám mení na fallback
            payload, status = job.fallback(config.lang), "fallback"
        else:
            payload = {**result.payload}
            # nedostupnosť AI sa nekešuje natrvalo: `error` sa po `stale_after` skúsi znova
            status = "ok" if result.source == "local_ai" else "error" if result.unavailable else "fallback"
        finish_ai_output(session, row, status=status, payload=payload, now=now())
        session.commit()

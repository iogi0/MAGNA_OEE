"""Seed číselníka (PLANNING D8, D9).

- vloží celý číselník (ST aj Q) s efektívnou kategóriou a príznakom `active_top10` podľa `top10.yaml`;
- je idempotentný a **existujúce kódy nemení** — výber Top-10 z Settings sa reštartom neprepíše;
- kód, ktorý pribudne do už naplnenej DB, je neaktívny (Top-10 z Settings sa nerozšíri nad 10);
- `station_id` sa neseeduje — väzba stanica ↔ kód je iba predpoklad (TASK §2), MVP ju nepotrebuje;
- model zmeny sa neseeduje (zadáva ho manažér, D8).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from oee.catalog.loader import Catalog
from oee.persistence.models import DefectType, IssueType


def seed_codebook(session: Session, catalog: Catalog) -> int:
    """Doplní chýbajúce kódy; vráti počet nových."""
    existing_st = set(session.scalars(select(IssueType.code)))
    existing_q = set(session.scalars(select(DefectType.code)))
    first_seed = not existing_st and not existing_q
    active_st = {*catalog.top10_stop, catalog.other_stop} if first_seed else {catalog.other_stop}
    active_q = {*catalog.top10_defect, catalog.other_defect} if first_seed else {catalog.other_defect}

    added = 0
    for code in catalog.codes.values():
        common = {
            "code": code.code,
            "name_en": code.name_en,
            "name_sk": code.name_sk,
            "category": catalog.category_of(code.code),
        }
        if code.kind == "stop" and code.code not in existing_st:
            session.add(
                IssueType(
                    **common, active_top10=code.code in active_st, is_other=code.code == catalog.other_stop
                )
            )
            added += 1
        elif code.kind == "defect" and code.code not in existing_q:
            session.add(
                DefectType(
                    **common, active_top10=code.code in active_q, is_other=code.code == catalog.other_defect
                )
            )
            added += 1
    session.flush()
    return added

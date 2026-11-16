"""Problem Links — matica a časová os výskytov (TASK §8.6, §12.8)."""

from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlalchemy.orm import Session

from oee.catalog.loader import load_catalog
from oee.persistence.seed import seed_codebook
from oee.services.analytics import build_period
from oee.services.demo import build_demo_shift, ensure_active_model
from oee.services.link_view import link_matrix, link_occurrences

NOW = datetime(2026, 12, 9, 18, 0)
DAY = date(2026, 12, 1)


@pytest.fixture
def links(session: Session) -> list:  # type: ignore[type-arg]
    seed_codebook(session, load_catalog())
    session.commit()
    ensure_active_model(session, line="L01", now=NOW)
    build_demo_shift(session, line="L01", day=DAY, now=NOW)
    period = build_period(
        session, DAY, date(2026, 12, 31), line="L01", period_type="month", catalog=load_catalog(), now=NOW
    )
    return list(period.problem_links)


def test_matrix_has_link_cells_and_selects_requested_or_first(links: list) -> None:  # type: ignore[type-arg]
    m = link_matrix(links, None, None)
    assert "ST-038" in m.causes and "Q-030" in m.effects
    assert m.selected is links[0]
    chosen = link_matrix(links, "ST-038", "Q-030")
    assert chosen.selected is not None and (chosen.selected.cause, chosen.selected.effect) == (
        "ST-038",
        "Q-030",
    )
    assert link_matrix(links, "ST-999", "Q-030").selected is links[0]  # neznámy pár → prvá väzba
    assert link_matrix([], None, None).selected is None


def test_occurrences_show_stop_and_defects_in_next_hour(session: Session, links: list) -> None:  # type: ignore[type-arg]
    link = next(x for x in links if (x.cause, x.effect) == ("ST-038", "Q-030"))
    occ = link_occurrences(session, link)
    assert len(occ) == link.support == 3
    for o in occ:
        assert o.stop_time_known and o.stop_min > 0
        assert o.window_start <= o.stop_start < o.stop_end <= o.window_end
        assert (o.window_end - o.window_start).total_seconds() == 2 * 3600  # hodina prestoja + nasledujúca
        assert o.defect_qty > 0
        assert all(0 <= o.pos(b.start) < o.pos(b.end) <= 100 for b in o.defects)
    # zmätky v okne = q_in_window (okná demo zmeny sa prekrývajú, preto zjednotenie hodín)
    unique = {(b.start, b.qty) for o in occ for b in o.defects}
    assert sum(q for _, q in unique) == link.q_in_window
    assert [o.stop_start for o in occ] == sorted(o.stop_start for o in occ)

"""Fallback texty bez AI (TASK §7.F, §8.6, §13.4; PLANNING D1).

Používajú sa, keď Ollama nebeží, nestihne odpovedať alebo jej text neprejde validátorom. Texty sa skladajú iba
z faktov (`domain.facts`) a samy prejdú validátorom. Vysvetlenie väzby neobsahuje odporúčané akcie (D1, P2).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from oee.ai.validator import Lang

TEXTS: dict[str, dict[str, str]] = {
    "en": {
        "provisional": "Provisional ({done}/{total} hours submitted). ",
        "head": "Shift {shift_id} ({weekday}, {date}): OEE {oee} % — {goal_part}.",
        "below": "below the {goal} % OEE goal by {gap} p.p.",
        "met": "meets the {goal} % OEE goal (+{gap} p.p.)",
        "no_oee": "OEE not available yet",
        "output": " The line produced {produced} of {target} target pieces ({pvt} %), {good} of them good.",
        "shortfall": (
            " Shortfall {shortfall} pcs: technical issues {down_pcs} pcs ({down_min} min in {events}"
            " {event_word}),"
            " speed losses {speed} pcs, rejects {rejects} pcs ({reject_rate} %)."
        ),
        "surplus": " Good output exceeds the target by {surplus} pcs.",
        "event": "event",
        "events": "events",
        "longest": " Longest problem — {category} / {code}, {minutes} min{at} (hour {hour}).",
        "at": " at {start}",
        "no_downtime": " No downtime was reported.",
        "fact": (
            "After {support} stops of {cause} there were {q} pcs of {effect} in the window on {produced}"
            " parts"
            " ({rate} % vs {base} % elsewhere)."
        ),
        "link": "Correlation: lift {lift}×, {kind}, confidence {confidence}.",
        "same": "same process ({process})",
        "cross": "different processes",
        "hyp_same": (
            "Hypothesis (to be verified): the {process} problem {cause} may also produce {effect} rejects."
            " This is a correlation, not a proven cause."
        ),
        "hyp_cross": (
            "Hypothesis (to be verified): {cause} and {effect} belong to different processes, the link may"
            " be weak"
            " or random. This is a correlation, not a proven cause."
        ),
        "impact": (
            "Combined impact ≈ {combined} pcs in the period (downtime {lost} pcs + extra rejects {extra}"
            " pcs);"
            " it is not added to the problem ranking."
        ),
    },
    "sk": {
        "provisional": "Predbežné ({done}/{total} hodín odoslaných). ",
        "head": "Zmena {shift_id} ({weekday}, {date}): OEE {oee} % — {goal_part}.",
        "below": "pod cieľom OEE {goal} % o {gap} p. b.",
        "met": "cieľ OEE {goal} % splnený (+{gap} p. b.)",
        "no_oee": "OEE zatiaľ nie je k dispozícii",
        "output": " Linka vyrobila {produced} z {target} kusov targetu ({pvt} %), z toho {good} dobrých.",
        "shortfall": (
            " Nedobór {shortfall} ks: technické problémy {down_pcs} ks ({down_min} min v {events}"
            " {event_word}),"
            " straty rýchlosti {speed} ks, zmätky {rejects} ks ({reject_rate} %)."
        ),
        "surplus": " Dobrých kusov je o {surplus} viac než target.",
        "event": "udalosti",
        "events": "udalostiach",
        "longest": " Najdlhší problém — {category} / {code}, {minutes} min{at} (hodina {hour}).",
        "at": " o {start}",
        "no_downtime": " Žiadny prestoj nebol nahlásený.",
        "fact": (
            "Po {support} prestojoch {cause} bolo v okne {q} ks zmätku {effect} na {produced} kusov"
            " ({rate} % oproti {base} % inde)."
        ),
        "link": "Korelácia: lift {lift}×, {kind}, istota {confidence}.",
        "same": "rovnaký proces ({process})",
        "cross": "rôzne procesy",
        "hyp_same": (
            "Hypotéza (overiť): problém procesu {process} {cause} môže spôsobovať aj zmätky {effect}."
            " Je to korelácia, nie dokázaná príčina."
        ),
        "hyp_cross": (
            "Hypotéza (overiť): {cause} a {effect} patria do rôznych procesov, väzba môže byť slabá alebo"
            " náhodná."
            " Je to korelácia, nie dokázaná príčina."
        ),
        "impact": (
            "Súhrnný vplyv ≈ {combined} ks za obdobie (prestoj {lost} ks + zmätky navyše {extra} ks);"
            " do rebríčka problémov sa nepripočítava."
        ),
    },
}
WEEKDAYS_SK = {"Mon": "po", "Tue": "ut", "Wed": "st", "Thu": "št", "Fri": "pi", "Sat": "so", "Sun": "ne"}


def fmt(value: float, decimals: int, lang: Lang) -> str:
    """Číslo v tvare jazyka: en 9,240 / 78.2; sk 9 240 / 78,2 (bez záporného znamienka — vyjadrí ho text)."""
    text = f"{abs(value):,.{decimals}f}"
    if decimals:
        text = text.rstrip("0").rstrip(".") if decimals > 1 else text
    if lang == "sk":
        text = text.replace(",", " ").replace(".", ",")
    return text


def _day(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day}.{d.month}.{d.year}"


def shift_summary_text(facts: dict[str, Any], lang: Lang) -> str:
    """Shift Summary podľa vzoru TASK §7.F."""
    t = TEXTS[lang]
    weekday = facts["weekday"] if lang == "en" else WEEKDAYS_SK.get(facts["weekday"], facts["weekday"])
    parts: list[str] = []
    if facts["provisional"]:
        parts.append(t["provisional"].format(done=facts["hours_submitted"], total=facts["hours_total"]))
    goal = fmt(facts["goal_pct"], 0, lang) if facts["goal_pct"] % 1 == 0 else fmt(facts["goal_pct"], 1, lang)
    if facts["oee_pct"] is None:
        goal_part = t["no_oee"]
        oee = "—"
    else:
        oee = fmt(facts["oee_pct"], 1, lang)
        key = "met" if facts["oee_status"] == "goal_met" else "below"
        goal_part = t[key].format(goal=goal, gap=fmt(facts["gap_pp"], 1, lang))
    parts.append(
        t["head"].format(
            shift_id=facts["shift_id"],
            weekday=weekday,
            date=_day(facts["date"]),
            oee=oee,
            goal_part=goal_part,
        )
    )
    pvt = facts["production_vs_target_pct"]
    parts.append(
        t["output"].format(
            produced=fmt(facts["produced_pcs"], 0, lang),
            target=fmt(facts["target_pcs"], 0, lang),
            pvt=fmt(pvt, 1, lang) if pvt is not None else "—",
            good=fmt(facts["good_pcs"], 0, lang),
        )
    )
    if facts["shortfall_pcs"] >= 0:
        rate = facts["reject_rate_pct"]
        parts.append(
            t["shortfall"].format(
                shortfall=fmt(facts["shortfall_pcs"], 0, lang),
                down_pcs=fmt(facts["downtime_pcs"], 0, lang),
                down_min=fmt(facts["downtime_min"], 0, lang),
                events=facts["downtime_events"],
                event_word=t["event"] if facts["downtime_events"] == 1 else t["events"],
                speed=fmt(facts["speed_loss_pcs"], 0, lang),
                rejects=fmt(facts["rejects_pcs"], 0, lang),
                reject_rate=fmt(rate, 1, lang) if rate is not None else "—",
            )
        )
    else:
        parts.append(t["surplus"].format(surplus=fmt(facts["shortfall_pcs"], 0, lang)))
    longest = facts["longest"]
    if longest is None:
        parts.append(t["no_downtime"])
    else:
        at = t["at"].format(start=longest["start"]) if longest["start"] else ""
        parts.append(
            t["longest"].format(
                category=longest["category"],
                code=longest["code"],
                minutes=fmt(longest["minutes"], 0, lang),
                at=at,
                hour=longest["hour_no"],
            )
        )
    return "".join(parts)


def link_explanation(facts: dict[str, Any], lang: Lang) -> dict[str, str]:
    """Vysvetlenie väzby §8.6: fakt, korelácia, hypotéza a súhrnný vplyv — bez odporúčaní (D1)."""
    t = TEXTS[lang]
    same = facts["link_type"] == "same_process"
    lift = facts["lift"]
    return {
        "fact": t["fact"].format(
            support=facts["support"],
            cause=facts["cause"],
            q=facts["q_in_window"],
            effect=facts["effect"],
            produced=fmt(facts["produced_in_window"], 0, lang),
            rate=fmt(facts["rate_in_window_pct"], 2, lang),
            base=fmt(facts["base_rate_pct"], 2, lang),
        ),
        "link": t["link"].format(
            lift=fmt(lift, 1, lang) if lift is not None else "—",
            kind=t["same"].format(process=facts["process"]) if same else t["cross"],
            confidence=facts["confidence"],
        ),
        "hypothesis": (t["hyp_same"] if same else t["hyp_cross"]).format(
            process=facts["process"], cause=facts["cause"], effect=facts["effect"]
        ),
        "impact": t["impact"].format(
            combined=fmt(facts["combined_impact_pcs"], 1, lang),
            lost=fmt(facts["cause_lost_pcs"], 0, lang),
            extra=fmt(facts["extra_rejects"], 1, lang),
        ),
    }

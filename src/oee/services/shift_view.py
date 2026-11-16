"""Podklady pre Shift Dashboard (TASK §7) nad hotovým `ShiftAnalytics`.

Žiadne KPI sa tu nepočítajú — iba výber, triedenie, zoskupenie bez zlúčenia (§7D) a Pareto podľa kategórie
(súčty vedier cez `domain.losses.group_by_category`, §7E). Grafy dostanú tie isté čísla ako `ShiftAnalytics`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from oee.contracts.shift_analytics import IssueRow, ParetoBucket, ShiftAnalytics
from oee.domain.losses import UNATTRIBUTED, UNSPECIFIED, LossBucket, group_by_category

IssueSort = Literal["time", "duration", "impact"]
ParetoMode = Literal["type", "category"]
BUCKET_LABELS = {UNATTRIBUTED: "Unattributed speed loss", UNSPECIFIED: "Unspecified defect"}


@dataclass(frozen=True)
class IssueGroup:
    """Zoskupenie udalostí jedného typu — udalosti zostávajú samostatné (§7D „nezlučovať")."""

    code: str
    name: str
    category: str
    rows: tuple[IssueRow, ...]

    @property
    def events(self) -> int:
        return len(self.rows)

    @property
    def total_min(self) -> float:
        return sum(r.duration_min for r in self.rows)


def status_label(analytics: ShiftAnalytics, effective_status: str) -> str:
    """Stav do hlavičky: `completed` / `in_progress n/N — provisional` / `incomplete` / „edited" (§7)."""
    h = analytics.shift
    if effective_status == "incomplete":
        return f"incomplete {h.hours_submitted}/{h.hours_total}"
    if h.status == "completed":
        return f"completed · edited (rev. {h.revision})" if h.revision else "completed"
    return f"{h.status} {h.hours_submitted}/{h.hours_total} — provisional"


def sorted_issues(issues: Sequence[IssueRow], sort: IssueSort) -> list[IssueRow]:
    """Čas (predvolene; bez času na koniec hodiny), dĺžka ↓, vplyv ↓."""
    if sort == "duration":
        return sorted(issues, key=lambda i: (-i.duration_min, i.hour_no))
    if sort == "impact":
        return sorted(issues, key=lambda i: (-i.lost_pcs, i.hour_no))
    return sorted(issues, key=lambda i: (i.hour_no, i.start_time is None, str(i.start_time or "")))


def group_issues(issues: Sequence[IssueRow]) -> list[IssueGroup]:
    """Skupiny podľa typu v poradí prvého výskytu v `issues` (ktoré už sú zoradené)."""
    groups: dict[str, list[IssueRow]] = {}
    for issue in issues:
        groups.setdefault(issue.issue_type, []).append(issue)
    return [IssueGroup(code, rows[0].name, rows[0].category, tuple(rows)) for code, rows in groups.items()]


def _bucket(b: ParetoBucket) -> LossBucket:
    return LossBucket(b.bucket, b.kind, b.pcs, b.share_of_losses, b.category)


def pareto(analytics: ShiftAnalytics, mode: ParetoMode) -> list[LossBucket]:
    buckets = [_bucket(b) for b in analytics.loss_pareto]
    return group_by_category(buckets) if mode == "category" else buckets


def bucket_label(bucket: str) -> str:
    return BUCKET_LABELS.get(bucket, bucket)


def _pareto_json(buckets: Sequence[LossBucket]) -> list[dict[str, object]]:
    return [
        {
            "bucket": b.bucket,
            "label": bucket_label(b.bucket),
            "kind": b.kind,
            "pcs": b.pcs,
            "share_of_losses": b.share_of_losses,
            "category": b.category,
        }
        for b in buckets
    ]


def waterfall_steps(analytics: ShiftAnalytics) -> list[dict[str, object]]:
    """Stĺpce waterfallu §7B ako [od, do] z kaskády C − D − S − R = G (JS ich iba kreslí)."""
    w, produced = analytics.waterfall_pcs, analytics.target_vs_actual.produced_pcs
    after_downtime = w.target - w.technical_losses
    steps = (  # (popis, druh, od, do, zobrazená hodnota — straty so záporným znamienkom)
        ("Target", "total", 0.0, w.target, w.target),
        ("Technical losses", "loss", after_downtime, w.target, -w.technical_losses),
        ("Speed loss", "loss", float(produced), after_downtime, -w.speed_loss),
        ("Produced", "total", 0.0, float(produced), float(produced)),
        ("Rejects", "loss", w.good, float(produced), -w.quality_loss),
        ("Good", "result", 0.0, w.good, w.good),
    )
    # spojnica do ďalšieho kroku: úroveň, na ktorej krok končí (Target → C−D → Produced → Produced → Good)
    connect = (w.target, after_downtime, float(produced), float(produced), w.good, None)
    return [
        {"label": label, "kind": kind, "range": [low, high], "value": value, "connect": level}
        for (label, kind, low, high, value), level in zip(steps, connect, strict=True)
    ]


def charts_payload(analytics: ShiftAnalytics) -> dict[str, object]:
    """Dáta grafov (§7B, §7C, §7E) — hodnoty priamo zo `ShiftAnalytics`, JS ich iba kreslí."""
    return {
        "shift_id": analytics.shift.shift_id,
        "target_oee": analytics.model.target_oee,
        "oee_goal_pcs": analytics.target_vs_actual.oee_goal_pcs,
        "produced_pcs": analytics.target_vs_actual.produced_pcs,
        "waterfall": analytics.waterfall_pcs.model_dump(mode="json"),
        "waterfall_steps": waterfall_steps(analytics),
        "hourly": [
            {
                "hour_no": h.hour_no,
                "slot": h.slot,
                "oee": h.oee,
                "target_pcs": h.target_pcs,
                "produced": h.produced,
                "rejects": h.rejects,
                "downtime_min": h.downtime_min,
                "flags": list(h.flags),
            }
            for h in analytics.hourly
        ],
        "pareto": {
            "type": _pareto_json(pareto(analytics, "type")),
            "category": _pareto_json(pareto(analytics, "category")),
        },
    }

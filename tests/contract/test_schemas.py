"""P0-07: Pydantic kontrakty podľa TASK §10.1–10.3 s úpravami D1, D5, D8, D10."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from oee.contracts.hourly_report import HourlyReport, HourlyReportResponse
from oee.contracts.period_analytics import PeriodAnalytics
from oee.contracts.shift_analytics import ShiftAnalytics

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

CASES: list[tuple[str, type[BaseModel]]] = [
    ("hourly_report.json", HourlyReport),
    ("hourly_report_response.json", HourlyReportResponse),
    ("shift_analytics.json", ShiftAnalytics),
    ("period_analytics.json", PeriodAnalytics),
]


def load(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return data


# --- príklady z TASK §10 ------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "model"), CASES, ids=[c[0] for c in CASES])
def test_task_examples_validate(name: str, model: type[BaseModel]) -> None:
    model.model_validate_json((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize(("name", "model"), CASES, ids=[c[0] for c in CASES])
def test_round_trip_keeps_json_names(name: str, model: type[BaseModel]) -> None:
    obj = model.model_validate(load(name))
    dumped = obj.model_dump(mode="json")
    assert model.model_validate(dumped) == obj
    assert set(dumped) == set(load(name))  # rovnaké kľúče ako v JSON (aliasy `from`, `class`)


def test_aliases_for_python_keywords() -> None:
    period = PeriodAnalytics.model_validate(load("period_analytics.json"))
    assert str(period.period.from_) == "2026-11-01"
    assert period.problem_ranking[0].class_ == "A"
    dumped = period.model_dump(mode="json")
    assert dumped["period"]["from"] == "2026-11-01"
    assert dumped["weekly"][0]["from"] == "2026-11-02"
    assert dumped["problem_ranking"][0]["class"] == "A"


def test_hourly_report_parses_types() -> None:
    report = HourlyReport.model_validate(load("hourly_report.json"))
    issue = report.issues[0]
    assert str(issue.start_time) == "09:08:00"
    assert issue.issue_type_code == "ST-038"
    assert report.rejects == 0  # hodina 4 zmeny 25.11. (TASK §12.3)
    assert issue.model_dump(mode="json")["start_time"] == "09:08"


def test_other_defect_with_comment_is_accepted() -> None:
    data = load("hourly_report.json")
    data["rejects"] = 2
    data["rejects_by_defect"] = [
        {"defect_type_code": "Q-030", "qty": 1},
        {"defect_type_code": "Q-034", "qty": 1, "comment": "scratch on housing"},
    ]
    report = HourlyReport.model_validate(data)
    assert report.rejects_by_defect[1].comment == "scratch on housing"


def test_contracts_are_immutable() -> None:
    report = HourlyReport.model_validate(load("hourly_report.json"))
    with pytest.raises(ValidationError):
        report.produced = 5  # type: ignore[misc]


# --- hourly_report: nevalidné vstupy ------------------------------------------------------------


def mutate(data: dict[str, Any], path: str, value: object) -> dict[str, Any]:
    """`path` napr. "issues.0.duration_min"; hodnota DELETE odstráni kľúč."""
    out = copy.deepcopy(data)
    *parents, last = path.split(".")
    node: Any = out
    for key in parents:
        node = node[int(key)] if key.isdigit() else node[key]
    if value is DELETE:
        del node[last]
    elif last.isdigit():
        node[int(last)] = value
    else:
        node[last] = value
    return out


DELETE = object()


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("produced", DELETE),  # V1 povinné
        ("produced", -1),
        ("produced", 31.5),  # V1 celé číslo
        ("produced", True),
        ("rejects", DELETE),  # TASK §5.3 povinné každú hodinu
        ("rejects", -1),
        ("hour_no", 0),
        ("date", "25.11.2026"),
        ("unknown_field", 1),
        ("issues.0.category_id", "camera_malfunction"),  # D5: kategória sa neposiela
        ("issues.0.name", "free text"),  # D10: voľný text iba ako komentár pri Other
        ("issues.0.issue_type_code", DELETE),  # D10: kód povinný
        ("issues.0.issue_type_code", None),
        ("issues.0.issue_type_code", "ST-38"),
        ("issues.0.issue_type_code", "Q-030"),
        ("issues.0.client_key", ""),  # V9
        ("issues.0.client_key", DELETE),
        ("issues.0.duration_min", 0),  # V4
        ("issues.0.duration_min", "NaN"),
        ("issues.0.start_time", "25:00"),
        ("issues.0.start_time", "09:08:30"),  # iba HH:MM
        ("issues.0.start_time", "9:08"),
        ("issues.0.start_time", 908),
        ("rejects_by_defect.0.qty", 0),
        ("rejects_by_defect.0.qty", 1.5),
        ("rejects_by_defect.0.defect_type_code", "ST-038"),
        ("retests", -1),
    ],
)
def test_invalid_hourly_report_rejected(path: str, value: object) -> None:
    base = load("hourly_report.json")
    base["rejects"] = 1
    base["rejects_by_defect"] = [{"defect_type_code": "Q-030", "qty": 1}]
    HourlyReport.model_validate(base)  # základ je platný
    with pytest.raises(ValidationError):
        HourlyReport.model_validate(mutate(base, path, value))


def test_hourly_report_minimal_hour_without_problems() -> None:
    report = HourlyReport.model_validate(
        {
            "hour_id": "L01-20261125-02",
            "shift_id": "L01-20261125-M",
            "date": "2026-11-25",
            "hour_no": 2,
            "produced": 58,
            "rejects": 0,
        }
    )
    assert report.issues == () and report.rejects_by_defect == ()


@pytest.mark.parametrize(
    ("path", "value"),
    [("hour_status", "ok"), ("shift_status", "done"), ("messages.0.level", "info"), ("hours_submitted", -1)],
)
def test_invalid_response_rejected(path: str, value: object) -> None:
    with pytest.raises(ValidationError):
        HourlyReportResponse.model_validate(mutate(load("hourly_report_response.json"), path, value))


# --- shift_analytics ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("shift.status", "done"),
        ("kpi.oee_status", "ok"),
        ("summary.text_source", "openai"),
        ("loss_pareto.1.kind", "speed"),
        ("hourly.0.hour_no", 0),
        ("target_vs_actual.good_pcs", 344.5),
        ("target_vs_actual.good_pcs", -1),
        ("issues.0.start_time", "07:08:00"),
        ("unknown", 1),
    ],
)
def test_invalid_shift_analytics_rejected(path: str, value: object) -> None:
    with pytest.raises(ValidationError):
        ShiftAnalytics.model_validate(mutate(load("shift_analytics.json"), path, value))


def test_provisional_shift_has_unsubmitted_hours_as_null() -> None:
    data = load("shift_analytics.json")
    data["shift"].update(status="in_progress", provisional=True, hours_submitted=3)
    data["hourly"].append(
        {
            "hour_no": 4,
            "slot": "09:00-10:00",
            "planned_min": 60,
            "target_pcs": 60,
            "produced": None,
            "rejects": None,
            "downtime_min": None,
            "speed_loss_pcs": None,
            "availability": None,
            "performance": None,
            "quality": None,
            "oee": None,
            "flags": ["not_submitted"],
        }
    )
    sa = ShiftAnalytics.model_validate(data)
    assert sa.hourly[-1].produced is None  # „not submitted", nie 0
    assert sa.shift.provisional is True


def test_undefined_kpis_are_null() -> None:
    data = mutate(load("shift_analytics.json"), "kpi.performance", None)
    assert ShiftAnalytics.model_validate(data).kpi.performance is None


def test_other_shift_length_is_allowed() -> None:
    data = load("shift_analytics.json")
    data["shift"].update(hours_submitted=6, hours_total=6)
    data["model"].update(calendar_min=360, planned_min=325, ideal_cycle_s=80, target_oee=0.8)
    data["quality"]["by_hour"] = [0, 1, 1, 0, 1, 3]
    assert ShiftAnalytics.model_validate(data).shift.hours_total == 6


def test_hours_submitted_cannot_exceed_total() -> None:
    with pytest.raises(ValidationError):
        ShiftAnalytics.model_validate(mutate(load("shift_analytics.json"), "shift.hours_submitted", 9))


def test_ai_recommendations_default_empty_in_p0() -> None:
    data = load("shift_analytics.json")
    del data["ai_recommendations"]
    assert ShiftAnalytics.model_validate(data).ai_recommendations == ()


# --- period_analytics ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("period.type", "year"),
        ("problem_ranking.0.class", "D"),
        ("problem_ranking.0.kind", "speed"),
        ("problem_ranking.0.trend", "rising"),
        ("problem_ranking.0.kpi_impact.kpi", "performance"),
        ("problem_links.0.link_type", "same_station"),
        ("problem_links.0.confidence", "certain"),
        ("problem_links.0.explanation_source", "cloud"),
        ("shift_series.0.status", "ok"),
        ("weekly.0.iso_week", 54),
    ],
)
def test_invalid_period_analytics_rejected(path: str, value: object) -> None:
    with pytest.raises(ValidationError):
        PeriodAnalytics.model_validate(mutate(load("period_analytics.json"), path, value))


def test_period_from_after_to_rejected() -> None:
    data = mutate(load("period_analytics.json"), "period.from", "2026-12-01")
    with pytest.raises(ValidationError):
        PeriodAnalytics.model_validate(data)


@pytest.mark.parametrize("trend", ["up", "down", "stable", "n/a"])
def test_ranking_trend_values(trend: str) -> None:
    data = mutate(load("period_analytics.json"), "problem_ranking.0.trend", trend)
    if trend == "n/a":
        data = mutate(data, "problem_ranking.0.trend_change", None)
    assert PeriodAnalytics.model_validate(data).problem_ranking[0].trend == trend

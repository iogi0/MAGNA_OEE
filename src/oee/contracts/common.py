"""Spoločný základ kontraktov: prísna Pydantic trieda a zdieľané typy."""

from __future__ import annotations

import re
from datetime import time
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, PlainSerializer, StringConstraints

STOP_CODE_PATTERN = r"^ST-\d{3}$"
DEFECT_CODE_PATTERN = r"^Q-\d{3}$"


class Contract(BaseModel):
    """Prísny, nemenný kontrakt.

    - `extra="forbid"`: neznáme pole = chyba (napr. `category_id`, ktoré sa neposiela — D5);
    - aliasy pre kľúčové slová Pythonu (`from`, `class`): vstup aj výstup používa názvy z JSON.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_by_name=True,
        validate_by_alias=True,
        serialize_by_alias=True,
    )


StopCode = Annotated[str, StringConstraints(pattern=STOP_CODE_PATTERN)]
DefectCode = Annotated[str, StringConstraints(pattern=DEFECT_CODE_PATTERN)]
NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

Count = Annotated[int, Field(strict=True, ge=0)]
"""Celé kusy / počty (bool ani 31.5 sa neprijmú — V1, V10)."""
PositiveCount = Annotated[int, Field(strict=True, gt=0)]
HourNo = Annotated[int, Field(strict=True, ge=1)]
Minutes = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Ratio = Annotated[float, Field(allow_inf_nan=False)]
"""Podiel 0–1 (môže byť > 1, napr. Performance pri zápornej S); None = nedefinované."""

_HHMM_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _parse_hhmm(value: object) -> object:
    """Vstup iba ako reťazec „HH:MM" (alebo už hotový `time` bez sekúnd)."""
    if isinstance(value, time):
        if value.second or value.microsecond:
            raise ValueError("time must not have seconds")
        return value
    if isinstance(value, str) and _HHMM_RE.match(value):
        return time.fromisoformat(value)
    raise ValueError("time must be in HH:MM format")


HHMM = Annotated[
    time,
    BeforeValidator(_parse_hhmm),
    PlainSerializer(lambda t: t.strftime("%H:%M"), return_type=str, when_used="json"),
]
"""Čas „HH:MM" (lokálny čas linky)."""

Level = Literal["error", "warning"]
ShiftStatus = Literal["open", "in_progress", "completed", "incomplete"]
OeeStatus = Literal["goal_met", "below_goal"]
LossKind = Literal["downtime", "quality"]
TextSource = Literal["local_ai", "template"]
ExplanationSource = Literal["local_ai", "rule_template"]


class Alert(Contract):
    """Upozornenie (P1, TASK §6.6) — v P0 prázdny zoznam."""

    kind: NonEmptyStr
    level: Level
    message: NonEmptyStr
    hour_no: HourNo | None = None


class DataQualityIssue(Contract):
    rule: NonEmptyStr
    level: Level
    message: NonEmptyStr
    subject: str | None = None

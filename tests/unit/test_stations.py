"""Line X-Ray: úroveň stanice a mapovanie staníc z katalógu."""

from __future__ import annotations

import pytest

from oee.catalog.loader import load_catalog, load_stations
from oee.domain.stations import LevelThresholds, Threshold, station_level

T = LevelThresholds(Threshold(1, 0), Threshold(2, 15), Threshold(3, 25))


@pytest.mark.parametrize(
    ("events", "minutes", "level"),
    [
        (0, 0, "none"),
        (1, 5, "low"),
        (1, 14.9, "low"),
        (1, 15, "elevated"),
        (2, 3, "elevated"),
        (1, 25, "high"),
        (3, 4, "high"),
        (2, 24, "elevated"),
    ],
)
def test_station_level(events: int, minutes: float, level: str) -> None:
    assert station_level(events, minutes, T) == level


def test_other_thresholds_are_respected() -> None:
    strict = LevelThresholds(Threshold(1, 0), Threshold(5, 60), Threshold(10, 120))
    assert station_level(3, 30, strict) == "low"
    assert station_level(1, 60, strict) == "elevated"


def test_stations_catalog() -> None:
    s = load_stations(load_catalog())
    assert [x.no for x in s.stations] == list(range(1, 11))
    assert s.stations_for("camera") == (3,)
    assert s.stations_for("screwdriving") == (4, 5, 8)
    assert s.stations_for("material_shortage") == ()
    assert s.off_line_for("material_shortage") == "Material supply"
    assert s.levels.high == Threshold(3, 25)

"""Input loading and validation. Any violation raises SurveyError (batch abort)."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from .errors import SurveyError


@dataclass(frozen=True)
class Station:
    md: float
    inclination_deg: float
    azimuth_deg: float


@dataclass(frozen=True)
class Hole:
    hole_id: str
    east: float
    north: float
    elevation: float
    stations: list[Station]


def _finite_number(value, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SurveyError(f"{what} must be a number, got {value!r}")
    result = float(value)
    if not math.isfinite(result):
        raise SurveyError(f"{what} must be finite, got {value!r}")
    return result


def _parse_station(raw, hole_id: str, index: int) -> Station:
    where = f"hole {hole_id!r} station[{index}]"
    if not isinstance(raw, dict):
        raise SurveyError(f"{where} must be an object")
    try:
        md = _finite_number(raw["md"], f"{where} md")
        inc = _finite_number(raw["inclination"], f"{where} inclination")
        az = _finite_number(raw["azimuth"], f"{where} azimuth")
    except KeyError as exc:
        raise SurveyError(f"{where} missing field {exc}") from exc
    if not 0.0 <= inc <= 180.0:
        raise SurveyError(f"{where} inclination {inc} out of [0, 180]")
    if not 0.0 <= az < 360.0:
        raise SurveyError(f"{where} azimuth {az} out of [0, 360)")
    return Station(md=md, inclination_deg=inc, azimuth_deg=az)


def _parse_hole(raw, index: int) -> Hole:
    if not isinstance(raw, dict):
        raise SurveyError(f"holes[{index}] must be an object")
    hole_id = raw.get("id")
    if not isinstance(hole_id, str) or not hole_id:
        raise SurveyError(f"holes[{index}] id must be a non-empty string")
    collar = raw.get("collar")
    if not isinstance(collar, dict):
        raise SurveyError(f"hole {hole_id!r} collar must be an object")
    try:
        east = _finite_number(collar["east"], f"hole {hole_id!r} collar east")
        north = _finite_number(collar["north"], f"hole {hole_id!r} collar north")
        elev = _finite_number(collar["elevation"], f"hole {hole_id!r} collar elevation")
    except KeyError as exc:
        raise SurveyError(f"hole {hole_id!r} collar missing field {exc}") from exc
    raw_stations = raw.get("stations")
    if not isinstance(raw_stations, list) or len(raw_stations) < 2:
        raise SurveyError(f"hole {hole_id!r} needs at least two stations")
    stations = [_parse_station(s, hole_id, i) for i, s in enumerate(raw_stations)]
    if stations[0].md != 0.0:
        raise SurveyError(f"hole {hole_id!r} first station md must be 0")
    for prev, cur in zip(stations, stations[1:]):
        if not cur.md > prev.md:
            raise SurveyError(
                f"hole {hole_id!r} md must be strictly increasing "
                f"({prev.md} then {cur.md})"
            )
    return Hole(hole_id=hole_id, east=east, north=north, elevation=elev,
                stations=stations)


def load_survey(path: str | Path) -> list[Hole]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SurveyError(f"cannot read input: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("holes"), list):
        raise SurveyError("input must be an object with a 'holes' array")
    holes = [_parse_hole(h, i) for i, h in enumerate(data["holes"])]
    seen: set[str] = set()
    for hole in holes:
        if hole.hole_id in seen:
            raise SurveyError(f"duplicate hole id {hole.hole_id!r}")
        seen.add(hole.hole_id)
    return holes

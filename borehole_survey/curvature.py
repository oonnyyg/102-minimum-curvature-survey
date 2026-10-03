"""Minimum-curvature trajectory reconstruction (see docs/coordinates.md)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .errors import SurveyError
from .validation import Hole

BETA_LIMIT = math.pi - 1e-8


def unit_vector(inclination_deg: float, azimuth_deg: float) -> tuple[float, float, float]:
    inc = math.radians(inclination_deg)
    az = math.radians(azimuth_deg)
    sin_inc = math.sin(inc)
    return (sin_inc * math.sin(az), sin_inc * math.cos(az), math.cos(inc))


def included_angle(u1, u2) -> float:
    dot = u1[0] * u2[0] + u1[1] * u2[1] + u1[2] * u2[2]
    dot = max(-1.0, min(1.0, dot))
    return math.acos(dot)


def ratio_factor(beta: float) -> float:
    """RF = 2*tan(beta/2)/beta; 1 at beta == 0; series for tiny beta."""
    if beta == 0.0:
        return 1.0
    if beta < 1e-6:
        b2 = beta * beta
        return 1.0 + b2 / 12.0 + b2 * b2 / 120.0
    return 2.0 * math.tan(beta / 2.0) / beta


@dataclass(frozen=True)
class StationResult:
    md: float
    east: float
    north: float
    elevation: float
    tvd: float
    horizontal_offset: float
    closure_azimuth_deg: float | None
    dogleg_deg: float | None
    dogleg_per_30m_deg: float | None


@dataclass(frozen=True)
class HoleResult:
    hole_id: str
    stations: list[StationResult]
    bottom_east: float
    bottom_north: float
    bottom_elevation: float
    bottom_md: float
    max_dogleg_per_30m_deg: float


def compute_hole(hole: Hole) -> HoleResult:
    vectors = [unit_vector(s.inclination_deg, s.azimuth_deg) for s in hole.stations]
    results: list[StationResult] = [
        StationResult(md=hole.stations[0].md, east=hole.east, north=hole.north,
                      elevation=hole.elevation, tvd=0.0, horizontal_offset=0.0,
                      closure_azimuth_deg=None, dogleg_deg=None,
                      dogleg_per_30m_deg=None)
    ]
    cum_e = cum_n = cum_d = 0.0
    max_dls = 0.0
    for i in range(1, len(hole.stations)):
        prev, cur = hole.stations[i - 1], hole.stations[i]
        dmd = cur.md - prev.md
        beta = included_angle(vectors[i - 1], vectors[i])
        if beta >= BETA_LIMIT:
            raise SurveyError(
                f"hole {hole.hole_id!r} segment {i}: included angle "
                f"{math.degrees(beta)} deg too close to 180; batch rejected")
        rf = ratio_factor(beta)
        factor = dmd * rf / 2.0
        cum_e += factor * (vectors[i - 1][0] + vectors[i][0])
        cum_n += factor * (vectors[i - 1][1] + vectors[i][1])
        cum_d += factor * (vectors[i - 1][2] + vectors[i][2])
        offset = math.hypot(cum_e, cum_n)
        if offset <= 1e-9:
            closure_az = None
        else:
            closure_az = math.degrees(math.atan2(cum_e, cum_n)) % 360.0
        dogleg_deg = math.degrees(beta)
        dls = dogleg_deg * 30.0 / dmd
        max_dls = max(max_dls, dls)
        results.append(StationResult(
            md=cur.md, east=hole.east + cum_e, north=hole.north + cum_n,
            elevation=hole.elevation - cum_d, tvd=cum_d,
            horizontal_offset=offset, closure_azimuth_deg=closure_az,
            dogleg_deg=dogleg_deg, dogleg_per_30m_deg=dls))
    last = results[-1]
    return HoleResult(hole_id=hole.hole_id, stations=results,
                      bottom_east=last.east, bottom_north=last.north,
                      bottom_elevation=last.elevation, bottom_md=last.md,
                      max_dogleg_per_30m_deg=max_dls)

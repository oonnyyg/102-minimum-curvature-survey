"""Input validation, minimum curvature computation, and report writing."""

import csv
import json
import math
import os

DOGLEG_INTERVAL_M = 30.0
BETA_REJECT_RAD = math.pi - 1e-8
OFFSET_NULL_AZIMUTH_M = 1e-9


class SurveyError(Exception):
    """Raised when the input batch is invalid and must be rejected."""


def _finite_number(value, what):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SurveyError(f"{what} must be a number, got {value!r}")
    if not math.isfinite(value):
        raise SurveyError(f"{what} must be finite, got {value!r}")
    return float(value)


def _validate_well(raw, index):
    if not isinstance(raw, dict):
        raise SurveyError(f"well #{index} must be an object")
    well_id = raw.get("id")
    if not isinstance(well_id, str) or not well_id:
        raise SurveyError(f"well #{index} has a missing or invalid 'id'")

    collar = raw.get("collar")
    if not isinstance(collar, dict):
        raise SurveyError(f"well {well_id!r}: 'collar' must be an object")
    collar = {
        key: _finite_number(collar.get(key), f"well {well_id!r} collar.{key}")
        for key in ("east", "north", "elevation")
    }

    stations = raw.get("stations")
    if not isinstance(stations, list) or len(stations) < 2:
        raise SurveyError(f"well {well_id!r}: at least two stations are required")

    parsed = []
    prev_md = None
    for i, st in enumerate(stations):
        if not isinstance(st, dict):
            raise SurveyError(f"well {well_id!r} station #{i} must be an object")
        md = _finite_number(st.get("md"), f"well {well_id!r} station #{i} md")
        inc = _finite_number(
            st.get("inclination"), f"well {well_id!r} station #{i} inclination"
        )
        az = _finite_number(
            st.get("azimuth"), f"well {well_id!r} station #{i} azimuth"
        )
        if not 0.0 <= inc <= 180.0:
            raise SurveyError(
                f"well {well_id!r} station #{i}: inclination {inc} out of [0, 180]"
            )
        if not 0.0 <= az < 360.0:
            raise SurveyError(
                f"well {well_id!r} station #{i}: azimuth {az} out of [0, 360)"
            )
        if prev_md is None:
            if md != 0.0:
                raise SurveyError(
                    f"well {well_id!r}: first station md must be 0, got {md}"
                )
        elif md <= prev_md:
            raise SurveyError(
                f"well {well_id!r}: md must be strictly increasing "
                f"(station #{i}: {md} after {prev_md})"
            )
        prev_md = md
        parsed.append((md, inc, az))

    return {"id": well_id, "collar": collar, "stations": parsed}


def load_input(path):
    with open(path, "r", encoding="utf-8") as fh:
        try:
            data = json.load(fh)
        except json.JSONDecodeError as exc:
            raise SurveyError(f"invalid JSON: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("wells"), list):
        raise SurveyError("input must be an object with a 'wells' array")
    if not data["wells"]:
        raise SurveyError("'wells' must not be empty")

    wells = []
    seen = set()
    for i, raw in enumerate(data["wells"]):
        well = _validate_well(raw, i)
        if well["id"] in seen:
            raise SurveyError(f"duplicate well id {well['id']!r}")
        seen.add(well["id"])
        wells.append(well)
    return wells


def _direction(inc_deg, az_deg):
    """Unit vector (east, north, down) for inclination/azimuth in degrees."""
    inc = math.radians(inc_deg)
    az = math.radians(az_deg)
    sin_inc = math.sin(inc)
    return (sin_inc * math.sin(az), sin_inc * math.cos(az), math.cos(inc))


def _ratio_factor(beta):
    """RF = 2*tan(beta/2)/beta, stable for small beta."""
    if beta == 0.0:
        return 1.0
    if beta < 1e-4:
        # tan(x)/x = 1 + x^2/3 + 2x^4/15 + ... with x = beta/2
        b2 = beta * beta
        return 1.0 + b2 / 12.0 + b2 * b2 / 120.0
    return 2.0 * math.tan(beta / 2.0) / beta


def compute_well(well):
    """Compute per-station results and the well summary."""
    collar = well["collar"]
    stations = []
    cum_east = cum_north = cum_down = 0.0
    prev_dir = None
    prev_md = None
    max_dogleg = None

    for md, inc, az in well["stations"]:
        direction = _direction(inc, az)
        beta = None
        dogleg = None
        if prev_dir is not None:
            dot = sum(a * b for a, b in zip(prev_dir, direction))
            dot = max(-1.0, min(1.0, dot))
            beta = math.acos(dot)
            if beta >= BETA_REJECT_RAD:
                raise SurveyError(
                    f"well {well['id']!r}: direction reversal at md {md} "
                    f"(beta={math.degrees(beta)} deg); batch rejected"
                )
            dmd = md - prev_md
            rf = _ratio_factor(beta)
            factor = dmd * rf / 2.0
            cum_east += factor * (prev_dir[0] + direction[0])
            cum_north += factor * (prev_dir[1] + direction[1])
            cum_down += factor * (prev_dir[2] + direction[2])
            dogleg = math.degrees(beta) * DOGLEG_INTERVAL_M / dmd
            if max_dogleg is None or dogleg > max_dogleg:
                max_dogleg = dogleg

        offset = math.hypot(cum_east, cum_north)
        if offset <= OFFSET_NULL_AZIMUTH_M:
            closure_az = None
        else:
            closure_az = math.degrees(math.atan2(cum_east, cum_north)) % 360.0

        stations.append(
            {
                "md": md,
                "inclination": inc,
                "azimuth": az,
                "east": cum_east,
                "north": cum_north,
                "tvd": cum_down,
                "elevation": collar["elevation"] - cum_down,
                "horizontal_offset": offset,
                "closure_azimuth": closure_az,
                "beta_deg": None if beta is None else math.degrees(beta),
                "dogleg_per_30m": dogleg,
            }
        )
        prev_dir = direction
        prev_md = md

    bottom = stations[-1]
    summary = {
        "id": well["id"],
        "collar": collar,
        "bottom": {
            "md": bottom["md"],
            "east": bottom["east"],
            "north": bottom["north"],
            "tvd": bottom["tvd"],
            "elevation": bottom["elevation"],
            "horizontal_offset": bottom["horizontal_offset"],
            "closure_azimuth": bottom["closure_azimuth"],
        },
        "max_dogleg_per_30m": max_dogleg,
    }
    return stations, summary


CSV_FIELDS = [
    "well_id",
    "md",
    "inclination",
    "azimuth",
    "east",
    "north",
    "tvd",
    "elevation",
    "horizontal_offset",
    "closure_azimuth",
    "beta_deg",
    "dogleg_per_30m",
]


def _fmt(value):
    if value is None:
        return ""
    if isinstance(value, float):
        return repr(value)
    return value


def write_reports(results, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, "stations.csv")
    with open(csv_path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(CSV_FIELDS)
        for stations, _summary in results:
            for st in stations:
                writer.writerow(
                    [st["well_id"]] + [_fmt(st[key]) for key in CSV_FIELDS[1:]]
                )
    for _stations, summary in results:
        path = os.path.join(out_dir, f"{summary['id']}.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2, ensure_ascii=False)
            fh.write("\n")


def run(input_path, out_dir):
    wells = load_input(input_path)
    results = []
    for well in wells:
        stations, summary = compute_well(well)
        for st in stations:
            st["well_id"] = well["id"]
        results.append((stations, summary))
    write_reports(results, out_dir)

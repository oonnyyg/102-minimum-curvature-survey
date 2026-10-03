"""Write per-station CSV and per-hole JSON reports."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .curvature import HoleResult

CSV_FIELDS = [
    "md_m", "east_m", "north_m", "elevation_m", "tvd_m",
    "horizontal_offset_m", "closure_azimuth_deg",
    "dogleg_deg", "dogleg_per_30m_deg",
]


def _fmt(value: float | None) -> str:
    if value is None:
        return ""
    return repr(value)


def write_hole_reports(result: HoleResult, out_dir: Path) -> tuple[Path, Path]:
    csv_path = out_dir / f"{result.hole_id}_stations.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(CSV_FIELDS)
        for s in result.stations:
            writer.writerow([
                _fmt(s.md), _fmt(s.east), _fmt(s.north), _fmt(s.elevation),
                _fmt(s.tvd), _fmt(s.horizontal_offset),
                _fmt(s.closure_azimuth_deg), _fmt(s.dogleg_deg),
                _fmt(s.dogleg_per_30m_deg),
            ])
    summary = {
        "hole_id": result.hole_id,
        "units": {"distance": "m", "angle": "deg"},
        "bottom": {
            "md_m": result.bottom_md,
            "east_m": result.bottom_east,
            "north_m": result.bottom_north,
            "elevation_m": result.bottom_elevation,
        },
        "max_dogleg_per_30m_deg": result.max_dogleg_per_30m_deg,
        "stations": [
            {
                "md_m": s.md,
                "east_m": s.east,
                "north_m": s.north,
                "elevation_m": s.elevation,
                "tvd_m": s.tvd,
                "horizontal_offset_m": s.horizontal_offset,
                "closure_azimuth_deg": s.closure_azimuth_deg,
                "dogleg_deg": s.dogleg_deg,
                "dogleg_per_30m_deg": s.dogleg_per_30m_deg,
            }
            for s in result.stations
        ],
    }
    json_path = out_dir / f"{result.hole_id}.json"
    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    return csv_path, json_path

"""CLI: python -m borehole_survey input.json --out output_dir"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .curvature import compute_hole
from .errors import SurveyError
from .report import write_hole_reports
from .validation import load_survey


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="borehole_survey",
        description="Reconstruct 3D borehole trajectories (minimum curvature).")
    parser.add_argument("input", help="survey JSON file")
    parser.add_argument("--out", required=True, help="output directory")
    args = parser.parse_args(argv)

    try:
        holes = load_survey(args.input)
        results = [compute_hole(h) for h in holes]
    except SurveyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    for result in results:
        csv_path, json_path = write_hole_reports(result, out_dir)
        print(f"{result.hole_id}: wrote {csv_path.name}, {json_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

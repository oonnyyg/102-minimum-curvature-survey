"""Command line entry point: python -m borehole_survey input.json --out DIR"""

import argparse
import sys

from .survey import SurveyError, run


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="borehole_survey",
        description="Reconstruct 3D borehole trajectories (minimum curvature).",
    )
    parser.add_argument("input", help="input JSON file with wells and stations")
    parser.add_argument("--out", required=True, help="output directory for reports")
    args = parser.parse_args(argv)

    try:
        run(args.input, args.out)
    except (SurveyError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

import csv
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest

from borehole_survey.survey import SurveyError, compute_well, load_input, run


def make_well(stations, well_id="W1", collar=None):
    return {
        "id": well_id,
        "collar": collar or {"east": 0.0, "north": 0.0, "elevation": 100.0},
        "stations": stations,
    }


def write_input(tmp, data):
    path = os.path.join(tmp, "input.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    return path


class StraightDownTest(unittest.TestCase):
    def test_vertical_well(self):
        well = make_well(
            [
                (0.0, 0.0, 0.0),
                (50.0, 0.0, 120.0),
                (100.0, 0.0, 240.0),
            ]
        )
        stations, summary = compute_well(well)
        bottom = stations[-1]
        self.assertAlmostEqual(bottom["tvd"], 100.0, places=12)
        self.assertAlmostEqual(bottom["elevation"], 0.0, places=12)
        self.assertAlmostEqual(bottom["horizontal_offset"], 0.0, places=12)
        self.assertIsNone(bottom["closure_azimuth"])
        self.assertIsNone(stations[0]["beta_deg"])
        self.assertIsNone(stations[0]["dogleg_per_30m"])
        self.assertAlmostEqual(summary["max_dogleg_per_30m"], 0.0, places=12)

    def test_horizontal_east(self):
        well = make_well([(0.0, 90.0, 90.0), (100.0, 90.0, 90.0)])
        stations, _ = compute_well(well)
        bottom = stations[-1]
        self.assertAlmostEqual(bottom["east"], 100.0, places=12)
        self.assertAlmostEqual(bottom["north"], 0.0, places=12)
        self.assertAlmostEqual(bottom["tvd"], 0.0, places=12)
        self.assertAlmostEqual(bottom["closure_azimuth"], 90.0, places=9)


class KnownTrajectoryTest(unittest.TestCase):
    def test_quarter_circle_build(self):
        # 0 -> 90 deg inclination over 100 m at constant azimuth 0 (north).
        well = make_well([(0.0, 0.0, 0.0), (100.0, 90.0, 0.0)])
        stations, summary = compute_well(well)
        bottom = stations[-1]
        # Minimum curvature arc: radius = 100 / (pi/2)
        radius = 100.0 / (math.pi / 2.0)
        self.assertAlmostEqual(bottom["north"], radius, delta=1e-8)
        self.assertAlmostEqual(bottom["tvd"], radius, delta=1e-8)
        self.assertAlmostEqual(bottom["beta_deg"], 90.0, places=9)
        self.assertAlmostEqual(
            bottom["dogleg_per_30m"], 90.0 * 30.0 / 100.0, places=9
        )
        self.assertAlmostEqual(
            summary["max_dogleg_per_30m"], 27.0, places=9
        )

    def test_closure_azimuth_normalization(self):
        # Drill toward the west (negative east).
        well = make_well([(0.0, 90.0, 270.0), (10.0, 90.0, 270.0)])
        stations, _ = compute_well(well)
        self.assertAlmostEqual(stations[-1]["closure_azimuth"], 270.0, places=9)
        stations, _ = compute_well(well)
        self.assertAlmostEqual(stations[-1]["closure_azimuth"], 270.0, places=9)


class ValidationTest(unittest.TestCase):
    def _load(self, data):
        with tempfile.TemporaryDirectory() as tmp:
            return load_input(write_input(tmp, data))

    def _bad(self, data):
        with self.assertRaises(SurveyError):
            self._load(data)

    def _well_json(self, stations, well_id="W1"):
        return {
            "id": well_id,
            "collar": {"east": 0.0, "north": 0.0, "elevation": 0.0},
            "stations": [
                {"md": md, "inclination": inc, "azimuth": az}
                for md, inc, az in stations
            ],
        }

    def test_duplicate_ids(self):
        w = self._well_json([(0, 0, 0), (10, 0, 0)])
        self._bad({"wells": [w, w]})

    def test_single_station(self):
        self._bad({"wells": [self._well_json([(0, 0, 0)])]})

    def test_md_not_starting_at_zero(self):
        self._bad({"wells": [self._well_json([(5, 0, 0), (10, 0, 0)])]})

    def test_md_not_increasing(self):
        self._bad({"wells": [self._well_json([(0, 0, 0), (10, 0, 0), (10, 0, 0)])]})
        self._bad({"wells": [self._well_json([(0, 0, 0), (10, 0, 0), (5, 0, 0)])]})

    def test_inclination_range(self):
        self._bad({"wells": [self._well_json([(0, -1, 0), (10, 0, 0)])]})
        self._bad({"wells": [self._well_json([(0, 0, 0), (10, 181, 0)])]})

    def test_azimuth_range(self):
        self._bad({"wells": [self._well_json([(0, 0, -0.1), (10, 0, 0)])]})
        self._bad({"wells": [self._well_json([(0, 0, 0), (10, 0, 360)])]})

    def test_non_finite(self):
        w = self._well_json([(0, 0, 0), (10, 0, 0)])
        w["stations"][1]["md"] = float("nan")
        self._bad({"wells": [w]})
        w = self._well_json([(0, 0, 0), (10, 0, 0)])
        w["collar"]["east"] = float("inf")
        self._bad({"wells": [w]})

    def test_direction_reversal_rejected(self):
        well = make_well([(0.0, 0.0, 0.0), (10.0, 180.0, 0.0)])
        with self.assertRaises(SurveyError):
            compute_well(well)

    def test_valid_input_loads(self):
        wells = self._load(
            {"wells": [self._well_json([(0, 0, 0), (10, 5, 30)], "A"),
                       self._well_json([(0, 1, 2), (20, 3, 4)], "B")]}
        )
        self.assertEqual([w["id"] for w in wells], ["A", "B"])
        wells = self._load(
            {"wells": [self._well_json([(0, 0, 0), (10, 5, 30)], "A"),
                       self._well_json([(0, 1, 2), (20, 3, 4)], "B")]}
        )
        self.assertEqual([w["id"] for w in wells], ["A", "B"])


class CliTest(unittest.TestCase):
    def _input(self):
        return {
            "wells": [
                {
                    "id": "W1",
                    "collar": {"east": 10.0, "north": 20.0, "elevation": 500.0},
                    "stations": [
                        {"md": 0.0, "inclination": 0.0, "azimuth": 0.0},
                        {"md": 100.0, "inclination": 90.0, "azimuth": 0.0},
                    ],
                },
                {
                    "id": "W2",
                    "collar": {"east": 0.0, "north": 0.0, "elevation": 0.0},
                    "stations": [
                        {"md": 0.0, "inclination": 0.0, "azimuth": 0.0},
                        {"md": 50.0, "inclination": 0.0, "azimuth": 0.0},
                    ],
                },
            ]
        }

    def test_cli_writes_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            inp = write_input(tmp, self._input())
            out = os.path.join(tmp, "out")
            proc = subprocess.run(
                [sys.executable, "-m", "borehole_survey", inp, "--out", out],
                capture_output=True,
                text=True,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)

            with open(os.path.join(out, "stations.csv"), newline="",
                      encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(len(rows), 4)
            self.assertEqual(rows[0]["well_id"], "W1")
            self.assertEqual(rows[0]["beta_deg"], "")
            self.assertEqual(rows[0]["closure_azimuth"], "")

            with open(os.path.join(out, "W1.json"), encoding="utf-8") as fh:
                summary = json.load(fh)
            radius = 100.0 / (math.pi / 2.0)
            self.assertAlmostEqual(summary["bottom"]["north"], radius, delta=1e-8)
            self.assertAlmostEqual(
                summary["bottom"]["elevation"], 500.0 - radius, delta=1e-8
            )
            self.assertAlmostEqual(
                summary["max_dogleg_per_30m"], 27.0, delta=1e-8
            )
            self.assertTrue(os.path.exists(os.path.join(out, "W2.json")))

    def test_cli_rejects_invalid_batch_without_reports(self):
        bad = self._input()
        bad["wells"][1]["stations"][1]["md"] = 0.0  # not increasing
        with tempfile.TemporaryDirectory() as tmp:
            inp = write_input(tmp, bad)
            out = os.path.join(tmp, "out")
            proc = subprocess.run(
                [sys.executable, "-m", "borehole_survey", inp, "--out", out],
                capture_output=True,
                text=True,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            )
            self.assertEqual(proc.returncode, 1)
            self.assertIn("error:", proc.stderr)
            self.assertFalse(os.path.exists(out))


if __name__ == "__main__":
    unittest.main()

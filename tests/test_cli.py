import csv
import json
import tempfile
import unittest
from pathlib import Path

from borehole_survey.__main__ import main


class TestCli(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write_input(self, data):
        path = self.tmp / "in.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_end_to_end(self):
        data = {"holes": [{
            "id": "H1",
            "collar": {"east": 10, "north": 20, "elevation": 500},
            "stations": [
                {"md": 0, "inclination": 0, "azimuth": 0},
                {"md": 100, "inclination": 0, "azimuth": 0},
            ],
        }]}
        out = self.tmp / "out"
        rc = main([str(self.write_input(data)), "--out", str(out)])
        self.assertEqual(rc, 0)
        summary = json.loads((out / "H1.json").read_text(encoding="utf-8"))
        self.assertAlmostEqual(summary["bottom"]["elevation_m"], 400.0, places=9)
        self.assertEqual(summary["max_dogleg_per_30m_deg"], 0.0)
        with (out / "H1_stations.csv").open(encoding="utf-8") as fh:
            rows = list(csv.reader(fh))
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0][0], "md_m")

    def test_invalid_input_writes_nothing(self):
        data = {"holes": [{"id": "X",
                           "collar": {"east": 0, "north": 0, "elevation": 0},
                           "stations": [
                               {"md": 0, "inclination": 0, "azimuth": 0}]}]}
        out = self.tmp / "out"
        rc = main([str(self.write_input(data)), "--out", str(out)])
        self.assertEqual(rc, 1)
        self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()

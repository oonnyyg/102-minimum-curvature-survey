import json
import tempfile
import unittest
from pathlib import Path

from borehole_survey.errors import SurveyError
from borehole_survey.validation import load_survey


def write(tmp, data):
    path = Path(tmp) / "in.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def hole(hid="H1", stations=None):
    return {
        "id": hid,
        "collar": {"east": 0.0, "north": 0.0, "elevation": 100.0},
        "stations": stations if stations is not None else [
            {"md": 0, "inclination": 0, "azimuth": 0},
            {"md": 50, "inclination": 10, "azimuth": 90},
        ],
    }


class TestValidation(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def load(self, data):
        return load_survey(write(self.tmp, data))

    def test_valid(self):
        holes = self.load({"holes": [hole("A"), hole("B")]})
        self.assertEqual([h.hole_id for h in holes], ["A", "B"])

    def test_duplicate_id(self):
        with self.assertRaises(SurveyError):
            self.load({"holes": [hole("A"), hole("A")]})

    def test_too_few_stations(self):
        with self.assertRaises(SurveyError):
            self.load({"holes": [hole(stations=[
                {"md": 0, "inclination": 0, "azimuth": 0}])]})

    def test_md_must_start_at_zero(self):
        with self.assertRaises(SurveyError):
            self.load({"holes": [hole(stations=[
                {"md": 5, "inclination": 0, "azimuth": 0},
                {"md": 50, "inclination": 0, "azimuth": 0}])]})

    def test_md_strictly_increasing(self):
        with self.assertRaises(SurveyError):
            self.load({"holes": [hole(stations=[
                {"md": 0, "inclination": 0, "azimuth": 0},
                {"md": 50, "inclination": 0, "azimuth": 0},
                {"md": 50, "inclination": 0, "azimuth": 0}])]})

    def test_inclination_range(self):
        for bad in (-0.1, 180.1):
            with self.assertRaises(SurveyError):
                self.load({"holes": [hole(stations=[
                    {"md": 0, "inclination": 0, "azimuth": 0},
                    {"md": 50, "inclination": bad, "azimuth": 0}])]})

    def test_azimuth_range(self):
        for bad in (-0.1, 360.0):
            with self.assertRaises(SurveyError):
                self.load({"holes": [hole(stations=[
                    {"md": 0, "inclination": 0, "azimuth": 0},
                    {"md": 50, "inclination": 0, "azimuth": bad}])]})

    def test_non_finite(self):
        with self.assertRaises(SurveyError):
            self.load({"holes": [hole(stations=[
                {"md": 0, "inclination": 0, "azimuth": 0},
                {"md": 50, "inclination": "NaN", "azimuth": 0}])]})

    def test_missing_collar_field(self):
        h = hole()
        del h["collar"]["east"]
        with self.assertRaises(SurveyError):
            self.load({"holes": [h]})

    def test_bad_json(self):
        path = Path(self.tmp) / "bad.json"
        path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(SurveyError):
            load_survey(path)


if __name__ == "__main__":
    unittest.main()

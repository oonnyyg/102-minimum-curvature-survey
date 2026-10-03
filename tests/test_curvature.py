import math
import unittest

from borehole_survey.curvature import (compute_hole, included_angle,
                                       ratio_factor, unit_vector)
from borehole_survey.errors import SurveyError
from borehole_survey.validation import Hole, Station


def make_hole(stations, east=0.0, north=0.0, elevation=100.0, hole_id="H1"):
    return Hole(hole_id=hole_id, east=east, north=north, elevation=elevation,
                stations=[Station(md=m, inclination_deg=i, azimuth_deg=a)
                          for m, i, a in stations])


class TestVectors(unittest.TestCase):
    def test_vertical_down(self):
        e, n, d = unit_vector(0.0, 123.0)
        self.assertAlmostEqual(e, 0.0, places=15)
        self.assertAlmostEqual(n, 0.0, places=15)
        self.assertAlmostEqual(d, 1.0, places=15)

    def test_horizontal_east(self):
        e, n, d = unit_vector(90.0, 90.0)
        self.assertAlmostEqual(e, 1.0, places=15)
        self.assertAlmostEqual(n, 0.0, places=15)
        self.assertAlmostEqual(d, 0.0, places=15)

    def test_included_angle_clamps_dot(self):
        u = unit_vector(10.0, 40.0)
        self.assertAlmostEqual(included_angle(u, u), 0.0, places=6)
        self.assertAlmostEqual(included_angle((0, 0, 1), (0, 0, -1)), math.pi)

    def test_ratio_factor(self):
        self.assertEqual(ratio_factor(0.0), 1.0)
        self.assertAlmostEqual(ratio_factor(1e-9), 1.0, places=15)
        beta = math.radians(30.0)
        self.assertAlmostEqual(ratio_factor(beta),
                               2.0 * math.tan(beta / 2.0) / beta, places=15)


class TestComputeHole(unittest.TestCase):
    def test_straight_vertical(self):
        res = compute_hole(make_hole([(0, 0, 0), (100, 0, 0)]))
        last = res.stations[-1]
        self.assertAlmostEqual(last.east, 0.0, places=12)
        self.assertAlmostEqual(last.north, 0.0, places=12)
        self.assertAlmostEqual(last.tvd, 100.0, places=12)
        self.assertAlmostEqual(last.elevation, 0.0, places=12)
        self.assertIsNone(res.stations[0].dogleg_deg)
        self.assertIsNone(last.closure_azimuth_deg)
        self.assertEqual(res.max_dogleg_per_30m_deg, 0.0)

    def test_first_station_zero_state(self):
        res = compute_hole(make_hole([(0, 10, 90), (50, 10, 90)],
                                     east=5.0, north=6.0, elevation=7.0))
        first = res.stations[0]
        self.assertEqual((first.east, first.north, first.elevation),
                         (5.0, 6.0, 7.0))
        self.assertEqual(first.tvd, 0.0)
        self.assertIsNone(first.dogleg_per_30m_deg)

    def test_horizontal_east_segment(self):
        res = compute_hole(make_hole([(0, 90, 90), (30, 90, 90)]))
        last = res.stations[-1]
        self.assertAlmostEqual(last.east, 30.0, places=12)
        self.assertAlmostEqual(last.tvd, 0.0, places=12)
        self.assertAlmostEqual(last.horizontal_offset, 30.0, places=12)
        self.assertAlmostEqual(last.closure_azimuth_deg, 90.0, places=12)

    def test_quarter_turn_minimum_curvature(self):
        res = compute_hole(make_hole([(0, 0, 0), (30, 90, 90)]))
        last = res.stations[-1]
        rf = 2.0 * math.tan(math.pi / 4.0) / (math.pi / 2.0)
        expect = 30.0 * rf / 2.0
        self.assertAlmostEqual(last.east, expect, places=12)
        self.assertAlmostEqual(last.tvd, expect, places=12)
        self.assertAlmostEqual(last.dogleg_deg, 90.0, places=9)
        self.assertAlmostEqual(last.dogleg_per_30m_deg, 90.0, places=9)
        self.assertAlmostEqual(res.max_dogleg_per_30m_deg, 90.0, places=9)

    def test_closure_azimuth_normalized(self):
        res = compute_hole(make_hole([(0, 90, 270), (10, 90, 270)]))
        az = res.stations[-1].closure_azimuth_deg
        self.assertIsNotNone(az)
        self.assertTrue(0.0 <= az < 360.0)
        self.assertAlmostEqual(az, 270.0, places=9)

    def test_reject_beta_near_pi(self):
        with self.assertRaises(SurveyError):
            compute_hole(make_hole([(0, 0, 0), (10, 180, 0)]))


if __name__ == "__main__":
    unittest.main()

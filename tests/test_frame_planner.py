import unittest

import frame_planner
import lumber_catalog


class TestFramePlanner(unittest.TestCase):
    def setUp(self):
        self.two_by_four = lumber_catalog.LUMBER_BY_NOMINAL["2x4"]
        self.len_cm = lumber_catalog.inches_to_cm(96.0)
        self.wid_cm = lumber_catalog.inches_to_cm(48.0)

    def test_butt_long_rails_full_shortens_sides_by_3_inches(self):
        members = frame_planner.compute_frame_members(
            self.two_by_four, self.len_cm, self.wid_cm, on_edge=True,
            corner_style="Butt (Long Rails Full)",
        )
        self.assertEqual(len(members), 4)
        self.assertAlmostEqual(members[0].dx_cm, self.len_cm)
        self.assertAlmostEqual(members[2].dy_cm, lumber_catalog.inches_to_cm(45.0))
        self.assertEqual(members[2].name, "2x4 - 45 in")

    def test_butt_short_rails_full_shortens_long_rails_by_3_inches(self):
        members = frame_planner.compute_frame_members(
            self.two_by_four, self.len_cm, self.wid_cm, on_edge=True,
            corner_style="Butt (Short Rails Full)",
        )
        self.assertAlmostEqual(members[0].dx_cm, lumber_catalog.inches_to_cm(93.0))
        self.assertAlmostEqual(members[2].dy_cm, self.wid_cm)

    def test_flat_frame_uses_3_5_inch_width_in_xy(self):
        members = frame_planner.compute_frame_members(
            self.two_by_four, self.len_cm, self.wid_cm, on_edge=False,
            corner_style="Butt (Long Rails Full)",
        )
        # 48 - 2 * 3.5 = 41 in
        self.assertAlmostEqual(members[2].dy_cm, lumber_catalog.inches_to_cm(41.0))
        self.assertAlmostEqual(members[0].dz_cm, self.two_by_four.thickness_cm)

    def test_mitered_45_keeps_full_lengths_and_adds_miter_triangles(self):
        members = frame_planner.compute_frame_members(
            self.two_by_four, self.len_cm, self.wid_cm, on_edge=True,
            corner_style="Mitered (45°)",
        )
        self.assertEqual(len(members), 4)
        for m in members:
            self.assertEqual(len(m.miter_triangles_xy), 2)

    def test_half_lap_corners_alternates_top_and_bottom_cuts(self):
        members = frame_planner.compute_frame_members(
            self.two_by_four, self.len_cm, self.wid_cm, on_edge=True,
            corner_style="Half-Lap Corners",
        )
        self.assertTrue(members[0].lap_from_top)
        self.assertTrue(members[1].lap_from_top)
        self.assertFalse(members[2].lap_from_top)
        self.assertFalse(members[3].lap_from_top)
        for m in members:
            self.assertEqual(len(m.lap_cuts_xy), 2)

    def test_validation_errors(self):
        with self.assertRaises(ValueError):
            frame_planner.compute_frame_members(
                self.two_by_four, self.len_cm, self.wid_cm, corner_style="Unknown"
            )
        with self.assertRaises(ValueError):
            frame_planner.compute_frame_members(
                self.two_by_four, 2.0, 2.0, on_edge=True
            )


if __name__ == "__main__":
    unittest.main()

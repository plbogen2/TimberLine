import unittest

import corner_planner


class TestCornerPlanner(unittest.TestCase):
    def setUp(self):
        # Board A along X: 0..243.84 x 0..3.81 x 0..8.89
        # Board B along Y: 0..3.81 x 0..121.92 x 0..8.89
        self.box_a = (0.0, 0.0, 0.0, 243.84, 3.81, 8.89)
        self.box_b = (0.0, 0.0, 0.0, 3.81, 121.92, 8.89)

    def test_overlap_box_and_disjoint(self):
        ov = corner_planner.compute_overlap_box(self.box_a, self.box_b)
        self.assertEqual(ov, (0.0, 0.0, 0.0, 3.81, 3.81, 8.89))
        self.assertIsNone(
            corner_planner.compute_overlap_box(self.box_a, (500.0, 0.0, 0.0, 510.0, 3.81, 8.89))
        )

    def test_half_lap_auto_picks_thinnest_or_explicit_axis(self):
        # Thinnest overlap is X/Y (3.81), picks X (0)
        plan = corner_planner.compute_corner_cuts(self.box_a, self.box_b, "Half-Lap")
        self.assertEqual(len(plan.a_boxes), 1)
        self.assertEqual(len(plan.b_boxes), 1)
        self.assertAlmostEqual(plan.a_boxes[0][0], 1.905)
        self.assertAlmostEqual(plan.b_boxes[0][3], 1.905)

        for ax in ("X", "Y", "Z"):
            p = corner_planner.compute_corner_cuts(self.box_a, self.box_b, "Half-Lap", ax)
            self.assertEqual(len(p.a_boxes), 1)

    def test_bridle_splits_into_thirds(self):
        plan = corner_planner.compute_corner_cuts(
            self.box_a, self.box_b, "Bridle (A=Slot, B=Tenon)", "Z"
        )
        self.assertEqual(len(plan.a_boxes), 1)
        self.assertEqual(len(plan.b_boxes), 2)

    def test_miter_45_and_butt_trims(self):
        plan = corner_planner.compute_corner_cuts(self.box_a, self.box_b, "Miter (45°)", "Z")
        self.assertIsNotNone(plan.a_miter)
        self.assertIsNotNone(plan.b_miter)

        pa = corner_planner.compute_corner_cuts(self.box_a, self.box_b, "Butt (Trim A to B)")
        self.assertTrue(pa.use_boolean_trim_a)
        pb = corner_planner.compute_corner_cuts(self.box_a, self.box_b, "Butt (Trim B to A)")
        self.assertTrue(pb.use_boolean_trim_b)

    def test_errors(self):
        with self.assertRaises(ValueError):
            corner_planner.compute_corner_cuts(self.box_a, self.box_b, "Unknown")
        with self.assertRaises(ValueError):
            corner_planner.compute_corner_cuts(
                self.box_a, (500.0, 0.0, 0.0, 510.0, 3.81, 8.89), "Half-Lap"
            )


if __name__ == "__main__":
    unittest.main()

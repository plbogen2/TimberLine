import unittest

import lumber_catalog
import panel_planner


class TestPanelPlanner(unittest.TestCase):
    def setUp(self):
        # 4-sided 48" x 96" frame of 2x4s on edge (height 3.5" in Z)
        t = lumber_catalog.inches_to_cm(1.5)
        h = lumber_catalog.inches_to_cm(3.5)
        L = lumber_catalog.inches_to_cm(96.0)
        W = lumber_catalog.inches_to_cm(48.0)
        self.frame_4 = [
            (0.0, 0.0, 0.0, L, t, h),
            (0.0, W - t, 0.0, L, W, h),
            (0.0, t, 0.0, t, W - t, h),
            (L - t, t, 0.0, L, W - t, h),
        ]
        self.ply = lumber_catalog.SHEET_BY_NAME['1/4" Plywood']
        self.depth = lumber_catalog.inches_to_cm(0.25)

    def test_centered_panel_sizes_to_opening_plus_dado_depth(self):
        plan = panel_planner.compute_panel_plan(
            self.frame_4, self.ply, depth_cm=self.depth,
            plane_choice="Auto (Opening Plane)", alignment="Centered (Dado / Groove)",
        )
        # Inner opening is 45" x 93", + 0.25" each side = 45.5" x 93.5"
        self.assertAlmostEqual(plan.width_in, 45.5)
        self.assertAlmostEqual(plan.length_in, 93.5)
        self.assertTrue(plan.fits_max_sheet)
        self.assertEqual(plan.normal_axis, 2)

    def test_flush_front_and_back_rabbets_and_explicit_planes(self):
        p_front = panel_planner.compute_panel_plan(
            self.frame_4, self.ply, depth_cm=self.depth,
            plane_choice="XY (Z-Normal)", alignment="Flush Front (+Normal Rabbet)",
        )
        self.assertAlmostEqual(p_front.panel_box[5], lumber_catalog.inches_to_cm(3.5))

        p_back = panel_planner.compute_panel_plan(
            self.frame_4, self.ply, depth_cm=self.depth,
            plane_choice="XY (Z-Normal)", alignment="Flush Back (-Normal Rabbet)",
        )
        self.assertAlmostEqual(p_back.panel_box[2], 0.0)

        for plane in ("XZ (Y-Normal)", "YZ (X-Normal)"):
            p = panel_planner.compute_panel_plan(
                self.frame_4[:2], self.ply, depth_cm=self.depth, plane_choice=plane
            )
            self.assertIsNotNone(p.panel_box)

    def test_one_sided_boards_and_validation_errors(self):
        # Single-sided low board + single-sided high board
        p_low = panel_planner.compute_panel_plan(
            [(0.0, 0.0, 0.0, 10.0, 10.0, 2.0), (0.0, 0.0, 0.0, 2.0, 30.0, 2.0)],
            self.ply, depth_cm=0.5, plane_choice="XY (Z-Normal)",
        )
        self.assertIsNotNone(p_low.panel_box)

        with self.assertRaises(ValueError):
            panel_planner.compute_panel_plan([(0.0, 0.0, 0.0, 1.0, 1.0, 1.0)], self.ply)
        with self.assertRaises(ValueError):
            panel_planner.compute_panel_plan(self.frame_4, self.ply, plane_choice="Bad")
        with self.assertRaises(ValueError):
            panel_planner.compute_panel_plan(self.frame_4, self.ply, alignment="Bad")

    def test_hexagonal_6_board_panel_generates_6_sided_polygon(self):
        import math

        r = 30.0
        hex_boards = []
        for i in range(6):
            ang = math.radians(i * 60.0)
            cx = r * math.cos(ang)
            cy = r * math.sin(ang)
            hex_boards.append((cx - 2.0, cy - 2.0, 0.0, cx + 2.0, cy + 2.0, 8.89))

        plan = panel_planner.compute_panel_plan(
            hex_boards, self.ply, depth_cm=self.depth, plane_choice="XY (Z-Normal)"
        )
        self.assertEqual(len(plan.polygon_uv), 6)


if __name__ == "__main__":
    unittest.main()

import unittest

import attach_planner
import lumber_catalog
import operation_log


class TestAttachPlanner(unittest.TestCase):
    def setUp(self):
        self.two_by_four = lumber_catalog.LUMBER_BY_NOMINAL["2x4"]
        self.bounds = (0.0, 0.0, 243.84, 8.89)  # Side face of horizontal 2x4 (96" x 3.5")
        self.len_cm = lumber_catalog.inches_to_cm(48.0)
        self.depth_cm = lumber_catalog.inches_to_cm(1.5)

    def test_butt_flush_exact_and_outer_span_left_right(self):
        # Left vertical edge, exact length -> extrudes +48" from z=0
        plan = attach_planner.compute_attach_plan(
            self.bounds, (0.0, 0.0), (0.0, 8.89),
            self.two_by_four, self.len_cm, existing_depth_cm=self.depth_cm,
            on_edge=True, joint_type="Butt (Flush)", length_mode="Exact Board Length",
        )
        self.assertAlmostEqual(plan.start_z_cm, 0.0)
        self.assertAlmostEqual(plan.extrude_z_cm, self.len_cm)
        self.assertAlmostEqual(plan.cross_section_rect[0], 0.0)
        self.assertAlmostEqual(plan.cross_section_rect[2], self.two_by_four.thickness_cm)

        # Right vertical edge, Total Outer Span -> shortens outward by existing 1.5"
        plan_r = attach_planner.compute_attach_plan(
            self.bounds, (243.84, 0.0), (243.84, 8.89),
            self.two_by_four, self.len_cm, existing_depth_cm=self.depth_cm,
            on_edge=True, joint_type="Butt (Flush)", length_mode="Total Outer Span",
            flip_along_edge=True,
        )
        self.assertAlmostEqual(plan_r.extrude_z_cm, lumber_catalog.inches_to_cm(46.5))
        self.assertAlmostEqual(plan_r.cross_section_rect[2], 243.84)

    def test_butt_flush_top_and_bottom_edges(self):
        plan_b = attach_planner.compute_attach_plan(
            self.bounds, (0.0, 0.0), (243.84, 0.0),
            self.two_by_four, self.len_cm, existing_depth_cm=self.depth_cm,
            on_edge=False, joint_type="Butt (Flush)", length_mode="Total Outer Span",
        )
        self.assertAlmostEqual(plan_b.extrude_z_cm, lumber_catalog.inches_to_cm(46.5))

        plan_t = attach_planner.compute_attach_plan(
            self.bounds, (0.0, 8.89), (243.84, 8.89),
            self.two_by_four, self.len_cm, existing_depth_cm=self.depth_cm,
            on_edge=True, joint_type="Butt (Flush)", flip_along_edge=True,
        )
        self.assertAlmostEqual(plan_t.cross_section_rect[3], 8.89)

    def test_miter_half_lap_rabbet_and_dado_all_edges(self):
        for edge_p0, edge_p1 in [
            ((0.0, 0.0), (0.0, 8.89)),
            ((243.84, 0.0), (243.84, 8.89)),
            ((0.0, 0.0), (243.84, 0.0)),
            ((0.0, 8.89), (243.84, 8.89)),
        ]:
            m_plan = attach_planner.compute_attach_plan(
                self.bounds, edge_p0, edge_p1, self.two_by_four, self.len_cm,
                existing_depth_cm=self.depth_cm, joint_type="Miter", outer_angle_deg=120.0,
            )
            self.assertAlmostEqual(m_plan.outer_angle_deg, 120.0)
            self.assertEqual(len(m_plan.miter_existing_tri), 1)
            self.assertEqual(len(m_plan.miter_new_tri), 1)

            hl_plan = attach_planner.compute_attach_plan(
                self.bounds, edge_p0, edge_p1, self.two_by_four, self.len_cm,
                existing_depth_cm=self.depth_cm, joint_type="Half-Lap",
            )
            self.assertAlmostEqual(hl_plan.start_z_cm, -self.depth_cm / 2.0)
            self.assertAlmostEqual(hl_plan.existing_cut_depth_cm, self.depth_cm / 2.0)

            rab_plan = attach_planner.compute_attach_plan(
                self.bounds, edge_p0, edge_p1, self.two_by_four, self.len_cm,
                existing_depth_cm=self.depth_cm, joint_type="Rabbet",
                joint_depth_cm=lumber_catalog.inches_to_cm(0.375),
            )
            self.assertAlmostEqual(rab_plan.existing_cut_depth_cm, lumber_catalog.inches_to_cm(0.375))

            dado_plan = attach_planner.compute_attach_plan(
                self.bounds, edge_p0, edge_p1, self.two_by_four, self.len_cm,
                existing_depth_cm=self.depth_cm, joint_type="Dado / Groove",
                offset_cm=15.0,
            )
            self.assertAlmostEqual(dado_plan.existing_cut_depth_cm, lumber_catalog.inches_to_cm(0.375))

    def test_invalid_options_raise(self):
        with self.assertRaises(ValueError):
            attach_planner.compute_attach_plan(
                self.bounds, (0.0, 0.0), (0.0, 8.89), self.two_by_four, 10.0, 3.81, joint_type="Bad"
            )
        with self.assertRaises(ValueError):
            attach_planner.compute_attach_plan(
                self.bounds, (0.0, 0.0), (0.0, 8.89), self.two_by_four, 10.0, 3.81, length_mode="Bad"
            )
        with self.assertRaises(ValueError):
            attach_planner.compute_attach_plan(
                self.bounds, (0.0, 0.0), (0.0, 8.89), self.two_by_four, 10.0, 3.81,
                joint_type="Miter", outer_angle_deg=180.0,
            )


class TestOperationLog(unittest.TestCase):
    def test_record_format_and_clear(self):
        log = operation_log.OperationLog()
        self.assertIn("No TimberLine operations", log.format_report([]))

        log.record("Create Lumber", "2x4 - 96 in")
        log.record("Attach Board", "2x4 - 46.5 in [Butt (Flush)]")
        self.assertEqual(len(log.entries()), 2)

        report = log.format_report([("Extrude1", False), ("Cut1", True)])
        self.assertIn("Create Lumber: 2x4 - 96 in", report)
        self.assertIn("Extrude1", report)
        self.assertIn("Cut1 [suppressed]", report)

        log.clear()
        self.assertEqual(len(log.entries()), 0)


if __name__ == "__main__":
    unittest.main()

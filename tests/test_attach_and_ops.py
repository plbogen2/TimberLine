import unittest

import attach_planner
import lumber_catalog
import operation_log


class TestAttachPlanner(unittest.TestCase):
    def setUp(self):
        self.two_by_four = lumber_catalog.LUMBER_BY_NOMINAL["2x4"]
        self.bounds = (0.0, 0.0, 3.81, 243.84)  # Vertical 2x4 along Y (1.5" x 96")
        self.len_cm = lumber_catalog.inches_to_cm(48.0)

    def test_butt_flush_exact_and_outer_span_left_right(self):
        # Right edge, exact length
        plan = attach_planner.compute_attach_plan(
            self.bounds, (3.81, 0.0), (3.81, 243.84),
            self.two_by_four, self.len_cm, on_edge=True,
            joint_type="Butt (Flush)", length_mode="Exact Board Length",
        )
        self.assertAlmostEqual(plan.new_board_length_cm, self.len_cm)
        self.assertAlmostEqual(plan.new_board_rect[0], 3.81)

        # Left edge, Total Outer Span shortens by existing 1.5"
        plan_l = attach_planner.compute_attach_plan(
            self.bounds, (0.0, 0.0), (0.0, 243.84),
            self.two_by_four, self.len_cm, on_edge=True,
            joint_type="Butt (Flush)", length_mode="Total Outer Span",
            flip_along_edge=True,
        )
        self.assertAlmostEqual(plan_l.new_board_length_cm, lumber_catalog.inches_to_cm(46.5))
        self.assertAlmostEqual(plan_l.new_board_rect[2], 0.0)

    def test_butt_flush_top_and_bottom_edges(self):
        h_bounds = (0.0, 0.0, 243.84, 3.81)
        plan_b = attach_planner.compute_attach_plan(
            h_bounds, (0.0, 0.0), (243.84, 0.0),
            self.two_by_four, self.len_cm, on_edge=False,
            joint_type="Butt (Flush)", length_mode="Total Outer Span",
        )
        self.assertAlmostEqual(plan_b.new_board_length_cm, lumber_catalog.inches_to_cm(46.5))

        plan_t = attach_planner.compute_attach_plan(
            h_bounds, (0.0, 3.81), (243.84, 3.81),
            self.two_by_four, self.len_cm, on_edge=True,
            joint_type="Butt (Flush)", flip_along_edge=True,
        )
        self.assertAlmostEqual(plan_t.new_board_rect[1], 3.81)

    def test_miter_and_half_lap_all_four_edges(self):
        for edge_p0, edge_p1, bnd in [
            ((0.0, 0.0), (0.0, 243.84), self.bounds),
            ((3.81, 0.0), (3.81, 243.84), self.bounds),
            ((0.0, 0.0), (243.84, 0.0), (0.0, 0.0, 243.84, 3.81)),
            ((0.0, 3.81), (243.84, 3.81), (0.0, 0.0, 243.84, 3.81)),
        ]:
            m_plan = attach_planner.compute_attach_plan(
                bnd, edge_p0, edge_p1, self.two_by_four, self.len_cm, joint_type="Miter (45°)"
            )
            self.assertEqual(len(m_plan.existing_miter_tri), 1)
            self.assertEqual(len(m_plan.new_miter_tri), 1)

            hl_plan = attach_planner.compute_attach_plan(
                bnd, edge_p0, edge_p1, self.two_by_four, self.len_cm, joint_type="Half-Lap"
            )
            self.assertEqual(len(hl_plan.lap_rect), 1)

    def test_invalid_options_raise(self):
        with self.assertRaises(ValueError):
            attach_planner.compute_attach_plan(
                self.bounds, (0.0, 0.0), (0.0, 10.0), self.two_by_four, 10.0, joint_type="Bad"
            )
        with self.assertRaises(ValueError):
            attach_planner.compute_attach_plan(
                self.bounds, (0.0, 0.0), (0.0, 10.0), self.two_by_four, 10.0, length_mode="Bad"
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

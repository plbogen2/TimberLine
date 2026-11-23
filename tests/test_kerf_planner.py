import unittest

import kerf_planner


class TestKerfPlanner(unittest.TestCase):
    def test_linear_packing_accounts_for_kerf(self):
        cuts = [
            kerf_planner.LinearCut("Part A", 48.0),
            kerf_planner.LinearCut("Part B", 48.0),
        ]
        boards, oversized = kerf_planner.pack_linear_cuts(
            cuts, stock_length_in=96.0, kerf_in=0.125
        )
        self.assertEqual(len(oversized), 0)
        self.assertEqual(len(boards), 2)

    def test_linear_packing_fits_with_kerf_and_trim(self):
        cuts = [
            kerf_planner.LinearCut("Leg 1", 30.0),
            kerf_planner.LinearCut("Leg 2", 30.0),
            kerf_planner.LinearCut("Leg 3", 30.0),
        ]
        boards, oversized = kerf_planner.pack_linear_cuts(
            cuts, stock_length_in=96.0, kerf_in=0.125, trim_in=0.5
        )
        self.assertEqual(len(oversized), 0)
        self.assertEqual(len(boards), 1)
        self.assertAlmostEqual(boards[0].kerf_loss_in, 0.25)
        self.assertAlmostEqual(boards[0].offcut_in, 5.25)

    def test_linear_oversized_cut_flagged(self):
        cuts = [kerf_planner.LinearCut("Too Long", 100.0)]
        boards, oversized = kerf_planner.pack_linear_cuts(cuts, stock_length_in=96.0)
        self.assertEqual(len(boards), 0)
        self.assertEqual(len(oversized), 1)

    def test_sheet_packing_accounts_for_kerf(self):
        cuts = [kerf_planner.SheetCut(f"Panel {i}", 24.0, 48.0) for i in range(4)]
        sheets, oversized = kerf_planner.pack_sheet_cuts(cuts, 48.0, 96.0, kerf_in=0.125)
        self.assertEqual(len(oversized), 0)
        self.assertGreaterEqual(len(sheets), 2)

    def test_sheet_oversized_cut_flagged(self):
        cuts = [kerf_planner.SheetCut("Huge", 60.0, 60.0)]
        sheets, oversized = kerf_planner.pack_sheet_cuts(cuts, 48.0, 96.0)
        self.assertEqual(len(sheets), 0)
        self.assertEqual(len(oversized), 1)

    def test_format_cut_plan_report(self):
        empty = kerf_planner.format_cut_plan_report({}, {}, 0.125)
        self.assertIn("No lumber or sheet stock", empty)

        boards, oversized = kerf_planner.pack_linear_cuts(
            [kerf_planner.LinearCut("A", 24.0)], 96.0, kerf_in=0.125
        )
        report = kerf_planner.format_cut_plan_report({"2x4": (boards, oversized)}, {}, 0.125)
        self.assertIn("[2x4] -> 1 stock board(s) needed", report)


if __name__ == "__main__":
    unittest.main()

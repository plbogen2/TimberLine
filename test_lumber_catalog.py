import unittest

import joinery_tools
import kerf_planner
import lumber_catalog


class TestLumberCatalog(unittest.TestCase):
    def test_2x4_actual_dimensions(self):
        lumber = lumber_catalog.LUMBER_BY_NOMINAL["2x4"]
        self.assertAlmostEqual(lumber.thickness_in, 1.5)
        self.assertAlmostEqual(lumber.width_in, 3.5)
        self.assertAlmostEqual(lumber.thickness_cm, 3.81)
        self.assertAlmostEqual(lumber.width_cm, 8.89)
        self.assertEqual(lumber.label, '2x4 (1.5" x 3.5")')

    def test_wide_boards_use_quarter_inch_less(self):
        for nominal, expected_width in [("2x8", 7.25), ("2x10", 9.25), ("2x12", 11.25)]:
            lumber = lumber_catalog.LUMBER_BY_NOMINAL[nominal]
            self.assertAlmostEqual(lumber.width_in, expected_width)
            self.assertAlmostEqual(lumber.thickness_in, 1.5)

    def test_1x_boards_thickness(self):
        for nominal in ["1x2", "1x4", "1x6", "1x8", "1x12"]:
            lumber = lumber_catalog.LUMBER_BY_NOMINAL[nominal]
            self.assertAlmostEqual(lumber.thickness_in, 0.75)

    def test_timbers_and_decking(self):
        self.assertAlmostEqual(lumber_catalog.LUMBER_BY_NOMINAL["4x4"].thickness_in, 3.5)
        self.assertAlmostEqual(lumber_catalog.LUMBER_BY_NOMINAL["4x4"].width_in, 3.5)
        self.assertAlmostEqual(lumber_catalog.LUMBER_BY_NOMINAL["5/4x6"].thickness_in, 1.0)
        self.assertAlmostEqual(lumber_catalog.LUMBER_BY_NOMINAL["5/4x6"].width_in, 5.5)

    def test_unique_labels_and_nominals(self):
        self.assertEqual(len(lumber_catalog.LUMBER_BY_LABEL), len(lumber_catalog.LUMBER_SIZES))
        self.assertEqual(len(lumber_catalog.LUMBER_BY_NOMINAL), len(lumber_catalog.LUMBER_SIZES))

    def test_format_component_name(self):
        length_cm = lumber_catalog.inches_to_cm(96.0)
        self.assertEqual(lumber_catalog.format_component_name("2x4", length_cm), "2x4 - 96 in")


class TestSheetStock(unittest.TestCase):
    def test_plywood_actual_thickness_and_4x8_limit(self):
        ply = lumber_catalog.SHEET_BY_NAME['3/4" Plywood']
        self.assertAlmostEqual(ply.thickness_in, 23.0 / 32.0)
        self.assertTrue(ply.fits_in_sheet(48.0, 96.0))
        self.assertTrue(ply.fits_in_sheet(96.0, 48.0))
        self.assertFalse(ply.fits_in_sheet(60.0, 60.0))

    def test_baltic_birch_5x5_limit(self):
        bb = lumber_catalog.SHEET_BY_NAME["18mm Baltic Birch"]
        self.assertAlmostEqual(bb.thickness_cm, 1.8)
        self.assertTrue(bb.fits_in_sheet(60.0, 60.0))
        self.assertFalse(bb.fits_in_sheet(48.0, 96.0))

    def test_format_sheet_component_name(self):
        w_cm = lumber_catalog.inches_to_cm(24.0)
        l_cm = lumber_catalog.inches_to_cm(48.0)
        self.assertEqual(
            lumber_catalog.format_sheet_component_name('1/2" MDF', w_cm, l_cm),
            '1/2" MDF - 24x48 in',
        )


class TestJoineryTools(unittest.TestCase):
    def test_rabbet_left_edge(self):
        u0, v0, u1, v1 = joinery_tools.compute_edge_strip_rect(
            (0.0, 0.0, 10.0, 20.0), (0.0, 0.0), (0.0, 20.0), width=1.0, offset=0.0
        )
        self.assertLess(u0, 0.0)
        self.assertAlmostEqual(u1, 1.0)
        self.assertLess(v0, 0.0)
        self.assertGreater(v1, 20.0)

    def test_dado_offset_from_bottom_edge(self):
        u0, v0, u1, v1 = joinery_tools.compute_edge_strip_rect(
            (0.0, 0.0, 10.0, 20.0), (0.0, 0.0), (10.0, 0.0), width=1.8, offset=5.0
        )
        self.assertAlmostEqual(v0, 5.0)
        self.assertAlmostEqual(v1, 6.8)
        self.assertLess(u0, 0.0)
        self.assertGreater(u1, 10.0)

    def test_centered_tenon_aligns_with_long_axis(self):
        u0, v0, u1, v1 = joinery_tools.compute_centered_rect(
            (0.0, 0.0, 3.81, 8.89), short_dim=1.27, long_dim=6.35
        )
        self.assertAlmostEqual(u1 - u0, 1.27)
        self.assertAlmostEqual(v1 - v0, 6.35)

    def test_dowel_centers_even_spacing(self):
        centers = joinery_tools.compute_dowel_centers((0.0, 0.0, 10.0, 2.0), count=3, edge_inset=1.0)
        self.assertEqual(centers, [(1.0, 1.0), (5.0, 1.0), (9.0, 1.0)])

    def test_pocket_hole_line_and_centers(self):
        lp0, lp1, to_edge, centers = joinery_tools.compute_pocket_hole_line_and_centers(
            (0.0, 0.0, 20.0, 10.0), (0.0, 0.0), (0.0, 10.0), setback=3.0, count=2, edge_inset=2.0
        )
        self.assertEqual(lp0, (3.0, 0.0))
        self.assertEqual(lp1, (3.0, 10.0))
        self.assertEqual(to_edge, (-1.0, 0.0))
        self.assertEqual(centers, [(3.0, 2.0), (3.0, 8.0)])


class TestKerfPlanner(unittest.TestCase):
    def test_linear_packing_accounts_for_kerf(self):
        # Two 48" cuts cannot fit on one 96" board when blade kerf is 0.125"
        cuts = [
            kerf_planner.LinearCut("Part A", 48.0),
            kerf_planner.LinearCut("Part B", 48.0),
        ]
        boards, oversized = kerf_planner.pack_linear_cuts(cuts, stock_length_in=96.0, kerf_in=0.125)
        self.assertEqual(len(oversized), 0)
        self.assertEqual(len(boards), 2)

    def test_linear_packing_fits_with_kerf_and_trim(self):
        cuts = [
            kerf_planner.LinearCut("Leg 1", 30.0),
            kerf_planner.LinearCut("Leg 2", 30.0),
            kerf_planner.LinearCut("Leg 3", 30.0),
        ]
        # 30 + 0.125 + 30 + 0.125 + 30 = 90.25 <= 95.5 (96 - 0.5 trim)
        boards, oversized = kerf_planner.pack_linear_cuts(
            cuts, stock_length_in=96.0, kerf_in=0.125, trim_in=0.5
        )
        self.assertEqual(len(oversized), 0)
        self.assertEqual(len(boards), 1)
        self.assertAlmostEqual(boards[0].kerf_loss_in, 0.25)
        self.assertAlmostEqual(boards[0].offcut_in, 5.25)

    def test_sheet_packing_accounts_for_kerf(self):
        # Four 24x48 panels fit on one 48x96 sheet ONLY if kerf=0; with 0.125" kerf, 2 fit per shelf
        # and 24 + 0.125 + 24 = 48.125 > 48, so they must stack as 4 shelves or need 2 sheets!
        cuts = [kerf_planner.SheetCut(f"Panel {i}", 24.0, 48.0) for i in range(4)]
        sheets, oversized = kerf_planner.pack_sheet_cuts(cuts, 48.0, 96.0, kerf_in=0.125)
        self.assertEqual(len(oversized), 0)
        self.assertGreaterEqual(len(sheets), 2)


if __name__ == "__main__":
    unittest.main()

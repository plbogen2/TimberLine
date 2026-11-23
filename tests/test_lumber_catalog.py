import unittest

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


if __name__ == "__main__":
    unittest.main()

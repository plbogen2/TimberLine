import unittest

import joinery_tools


class TestJoineryTools(unittest.TestCase):
    def test_rabbet_all_four_edges(self):
        bounds = (0.0, 0.0, 10.0, 20.0)
        # Left edge
        u0, v0, u1, v1 = joinery_tools.compute_edge_strip_rect(
            bounds, (0.0, 0.0), (0.0, 20.0), width=1.0
        )
        self.assertLess(u0, 0.0)
        self.assertAlmostEqual(u1, 1.0)
        # Right edge
        u0, v0, u1, v1 = joinery_tools.compute_edge_strip_rect(
            bounds, (10.0, 0.0), (10.0, 20.0), width=1.0
        )
        self.assertAlmostEqual(u0, 9.0)
        self.assertGreater(u1, 10.0)
        # Bottom edge
        u0, v0, u1, v1 = joinery_tools.compute_edge_strip_rect(
            bounds, (0.0, 0.0), (10.0, 0.0), width=1.0
        )
        self.assertLess(v0, 0.0)
        self.assertAlmostEqual(v1, 1.0)
        # Top edge
        u0, v0, u1, v1 = joinery_tools.compute_edge_strip_rect(
            bounds, (0.0, 20.0), (10.0, 20.0), width=1.0
        )
        self.assertAlmostEqual(v0, 19.0)
        self.assertGreater(v1, 20.0)

    def test_dado_offset_from_bottom_and_right(self):
        bounds = (0.0, 0.0, 10.0, 20.0)
        u0, v0, u1, v1 = joinery_tools.compute_edge_strip_rect(
            bounds, (0.0, 0.0), (10.0, 0.0), width=1.8, offset=5.0
        )
        self.assertAlmostEqual(v0, 5.0)
        self.assertAlmostEqual(v1, 6.8)

        u0, v0, u1, v1 = joinery_tools.compute_edge_strip_rect(
            bounds, (10.0, 0.0), (10.0, 20.0), width=1.8, offset=3.0
        )
        self.assertAlmostEqual(u0, 5.2)
        self.assertAlmostEqual(u1, 7.0)

    def test_centered_tenon_aligns_with_long_axis(self):
        u0, v0, u1, v1 = joinery_tools.compute_centered_rect(
            (0.0, 0.0, 3.81, 8.89), short_dim=1.27, long_dim=6.35
        )
        self.assertAlmostEqual(u1 - u0, 1.27)
        self.assertAlmostEqual(v1 - v0, 6.35)

        u0, v0, u1, v1 = joinery_tools.compute_centered_rect(
            (0.0, 0.0, 8.89, 3.81), short_dim=1.27, long_dim=6.35
        )
        self.assertAlmostEqual(u1 - u0, 6.35)
        self.assertAlmostEqual(v1 - v0, 1.27)

    def test_dowel_centers_edge_cases(self):
        self.assertEqual(joinery_tools.compute_dowel_centers((0.0, 0.0, 10.0, 2.0), 0, 1.0), [])
        self.assertEqual(
            joinery_tools.compute_dowel_centers((0.0, 0.0, 10.0, 2.0), 1, 1.0),
            [(5.0, 1.0)],
        )
        self.assertEqual(
            joinery_tools.compute_dowel_centers((0.0, 0.0, 10.0, 2.0), 3, 1.0),
            [(1.0, 1.0), (5.0, 1.0), (9.0, 1.0)],
        )
        # Portrait face + inset larger than half length falls back to full span
        self.assertEqual(
            joinery_tools.compute_dowel_centers((0.0, 0.0, 2.0, 10.0), 2, 6.0),
            [(1.0, 0.0), (1.0, 10.0)],
        )
        # Landscape face with inset larger than half length
        self.assertEqual(
            joinery_tools.compute_dowel_centers((0.0, 0.0, 10.0, 2.0), 2, 6.0),
            [(0.0, 1.0), (10.0, 1.0)],
        )

    def test_pocket_hole_line_and_centers_vertical_and_horizontal(self):
        lp0, lp1, to_edge, centers = joinery_tools.compute_pocket_hole_line_and_centers(
            (0.0, 0.0, 20.0, 10.0), (0.0, 0.0), (0.0, 10.0), setback=3.0, count=2, edge_inset=2.0
        )
        self.assertEqual(lp0, (3.0, 0.0))
        self.assertEqual(lp1, (3.0, 10.0))
        self.assertEqual(to_edge, (-1.0, 0.0))
        self.assertEqual(centers, [(3.0, 2.0), (3.0, 8.0)])

        # Right edge + single pocket hole + fallback inset
        lp0, lp1, to_edge, centers = joinery_tools.compute_pocket_hole_line_and_centers(
            (0.0, 0.0, 20.0, 10.0), (20.0, 0.0), (20.0, 10.0), setback=3.0, count=1, edge_inset=2.0
        )
        self.assertEqual(lp0, (17.0, 0.0))
        self.assertEqual(to_edge, (1.0, 0.0))
        self.assertEqual(centers, [(17.0, 5.0)])

        lp0, lp1, to_edge, centers = joinery_tools.compute_pocket_hole_line_and_centers(
            (0.0, 0.0, 20.0, 10.0), (20.0, 0.0), (20.0, 10.0), setback=3.0, count=2, edge_inset=6.0
        )
        self.assertEqual(centers, [(17.0, 0.0), (17.0, 10.0)])

        # Top edge + single hole
        lp0, lp1, to_edge, centers = joinery_tools.compute_pocket_hole_line_and_centers(
            (0.0, 0.0, 20.0, 10.0), (0.0, 10.0), (20.0, 10.0), setback=2.0, count=1, edge_inset=2.0
        )
        self.assertEqual(lp0, (0.0, 8.0))
        self.assertEqual(lp1, (20.0, 8.0))
        self.assertEqual(to_edge, (0.0, 1.0))
        self.assertEqual(centers, [(10.0, 8.0)])

        # Bottom edge + 2 holes + fallback inset
        lp0, lp1, to_edge, centers = joinery_tools.compute_pocket_hole_line_and_centers(
            (0.0, 0.0, 20.0, 10.0), (0.0, 0.0), (20.0, 0.0), setback=2.0, count=2, edge_inset=15.0
        )
        self.assertEqual(lp0, (0.0, 2.0))
        self.assertEqual(to_edge, (0.0, -1.0))
        self.assertEqual(centers, [(0.0, 2.0), (20.0, 2.0)])

    def test_board_reference_params_all_edges(self):
        bounds = (0.0, 0.0, 10.0, 20.0)
        # Left edge (dado 3..4.8 -> offset=3, width=1.8)
        off, w = joinery_tools.compute_board_reference_params(
            bounds, (0.0, 0.0), (0.0, 20.0), (3.0, 0.0, 4.8, 20.0)
        )
        self.assertAlmostEqual(off, 3.0)
        self.assertAlmostEqual(w, 1.8)

        # Right edge (rabbet/dado 7..9 -> offset=1, width=2.0)
        off, w = joinery_tools.compute_board_reference_params(
            bounds, (10.0, 0.0), (10.0, 20.0), (7.0, 0.0, 9.0, 20.0)
        )
        self.assertAlmostEqual(off, 1.0)
        self.assertAlmostEqual(w, 2.0)

        # Bottom edge (dado 0..1.8 -> offset=0, width=1.8)
        off, w = joinery_tools.compute_board_reference_params(
            bounds, (0.0, 0.0), (10.0, 0.0), (0.0, 5.0, 10.0, 6.8)
        )
        self.assertAlmostEqual(off, 5.0)
        self.assertAlmostEqual(w, 1.8)

        # Top edge (offset from top=20 -> 20-16=4, width=2)
        off, w = joinery_tools.compute_board_reference_params(
            bounds, (0.0, 20.0), (10.0, 20.0), (0.0, 14.0, 10.0, 16.0)
        )
        self.assertAlmostEqual(off, 4.0)
        self.assertAlmostEqual(w, 2.0)

    def test_tongue_and_groove_both_orientations(self):
        r1, r2 = joinery_tools.compute_tongue_shoulder_rects((0.0, 0.0, 20.0, 2.0), 0.5)
        self.assertAlmostEqual(r1[3], 0.75)
        self.assertAlmostEqual(r2[1], 1.25)

        r1, r2 = joinery_tools.compute_tongue_shoulder_rects((0.0, 0.0, 2.0, 20.0), 0.5)
        self.assertAlmostEqual(r1[2], 0.75)
        self.assertAlmostEqual(r2[0], 1.25)

        g1 = joinery_tools.compute_centered_groove_rect((0.0, 0.0, 20.0, 2.0), 0.5)
        self.assertAlmostEqual(g1[1], 0.75)
        self.assertAlmostEqual(g1[3], 1.25)

        g2 = joinery_tools.compute_centered_groove_rect((0.0, 0.0, 2.0, 20.0), 0.5)
        self.assertAlmostEqual(g2[0], 0.75)
        self.assertAlmostEqual(g2[2], 1.25)

    def test_box_finger_cuts(self):
        self.assertEqual(joinery_tools.compute_finger_cut_rects((0.0, 0.0, 10.0, 2.0), 1), [])
        evens = joinery_tools.compute_finger_cut_rects((0.0, 0.0, 10.0, 2.0), 5, cut_even=True)
        odds = joinery_tools.compute_finger_cut_rects((0.0, 0.0, 10.0, 2.0), 5, cut_even=False)
        self.assertEqual(len(evens), 3)
        self.assertEqual(len(odds), 2)

        portrait = joinery_tools.compute_finger_cut_rects((0.0, 0.0, 2.0, 10.0), 5, cut_even=True)
        self.assertEqual(len(portrait), 3)

    def test_dovetail_polygons_and_biscuit_slots(self):
        self.assertEqual(joinery_tools.compute_dovetail_cut_polygons((0.0, 0.0, 10.0, 2.0), 0, 2.0), [])
        tails = joinery_tools.compute_dovetail_cut_polygons((0.0, 0.0, 20.0, 2.0), 3, 2.0, is_pins=False)
        pins = joinery_tools.compute_dovetail_cut_polygons((0.0, 0.0, 2.0, 20.0), 3, 2.0, is_pins=True)
        self.assertEqual(len(tails), 4)
        self.assertEqual(len(pins), 3)

        b_land = joinery_tools.compute_biscuit_slot_rects((0.0, 0.0, 20.0, 2.0), 2, 2.0, 5.6, 0.4)
        b_port = joinery_tools.compute_biscuit_slot_rects((0.0, 0.0, 2.0, 20.0), 2, 2.0, 5.6, 0.4)
        self.assertEqual(len(b_land), 2)
        self.assertEqual(len(b_port), 2)

    def test_bowtie_and_birdsmouth_all_orientations(self):
        bow_h = joinery_tools.compute_bowtie_polygon((0.0, 0.0, 20.0, 8.0), 2.0, 6.0)
        bow_v = joinery_tools.compute_bowtie_polygon((0.0, 0.0, 8.0, 20.0), 2.0, 6.0)
        self.assertEqual(len(bow_h), 6)
        self.assertEqual(len(bow_v), 6)

        bounds = (0.0, 0.0, 20.0, 10.0)
        for p0, p1 in [
            ((0.0, 0.0), (0.0, 10.0)),
            ((20.0, 0.0), (20.0, 10.0)),
            ((0.0, 0.0), (20.0, 0.0)),
            ((0.0, 10.0), (20.0, 10.0)),
        ]:
            tri = joinery_tools.compute_birdsmouth_triangle(bounds, p0, p1, 2.0, 3.5, 1.5)
            self.assertEqual(len(tri), 3)


if __name__ == "__main__":
    unittest.main()

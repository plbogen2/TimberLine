"""Registry of TimberLine joinery technique modules."""

from typing import Callable, Dict

from joinery import (
    birdsmouth,
    biscuit,
    bowtie,
    box_joint,
    bridle,
    dovetail,
    dowel_holes,
    edge_cuts,
    housing_2board,
    mortise_tenon,
    pocket_holes,
    scarf,
    sliding_dovetail,
    tongue_groove,
)

FACE_JOINTS: Dict[str, Callable] = {
    "Tenon": mortise_tenon.execute_tenon,
    "Mortise": mortise_tenon.execute_mortise,
    "Bridle (Open Mortise)": bridle.execute_bridle_slot,
    "Tongue (Edge)": tongue_groove.execute_tongue,
    "Groove / Spline": tongue_groove.execute_groove,
    "Box Joint (Even Slots)": lambda c, f, i: box_joint.execute_box_joint(c, f, i, cut_even=True),
    "Box Joint (Odd Slots)": lambda c, f, i: box_joint.execute_box_joint(c, f, i, cut_even=False),
    "Dovetail (Tails)": lambda c, f, i: dovetail.execute_dovetail(c, f, i, is_pins=False),
    "Dovetail (Pins)": lambda c, f, i: dovetail.execute_dovetail(c, f, i, is_pins=True),
    "Bowtie / Butterfly Key": bowtie.execute_bowtie,
    "Biscuit Slot": biscuit.execute_biscuit_slots,
    "Dowel Holes": dowel_holes.execute_dowel_holes,
}

EDGE_JOINTS: Dict[str, Callable] = {
    "Rabbet": lambda c, f, e, i: edge_cuts.execute_edge_joint("Rabbet", c, f, e, i),
    "Dado / Groove": lambda c, f, e, i: edge_cuts.execute_edge_joint("Dado / Groove", c, f, e, i),
    "Sliding Dovetail": sliding_dovetail.execute_sliding_dovetail,
    "Half-Lap": lambda c, f, e, i: edge_cuts.execute_edge_joint("Half-Lap", c, f, e, i),
    "Scarf Joint": scarf.execute_scarf,
    "Birdsmouth Notch": birdsmouth.execute_birdsmouth,
    "Pocket Holes (15°)": pocket_holes.execute_pocket_holes,
}

TWO_BOARD_JOINTS: Dict[str, Callable] = {
    "Housing / Dado (2-Board)": housing_2board.execute_two_board_housing,
}

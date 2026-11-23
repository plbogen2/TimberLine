"""Registry of TimberLine joinery technique modules."""

from typing import Callable, Dict

from joinery import dowel_holes, edge_cuts, housing_2board, mortise_tenon, pocket_holes

FACE_JOINTS: Dict[str, Callable] = {
    "Tenon": mortise_tenon.execute_tenon,
    "Mortise": mortise_tenon.execute_mortise,
    "Dowel Holes": dowel_holes.execute_dowel_holes,
}

EDGE_JOINTS: Dict[str, Callable] = {
    "Rabbet": lambda c, f, e, i: edge_cuts.execute_edge_joint("Rabbet", c, f, e, i),
    "Dado / Groove": lambda c, f, e, i: edge_cuts.execute_edge_joint("Dado / Groove", c, f, e, i),
    "Half-Lap": lambda c, f, e, i: edge_cuts.execute_edge_joint("Half-Lap", c, f, e, i),
    "Pocket Holes (15°)": pocket_holes.execute_pocket_holes,
}

TWO_BOARD_JOINTS: Dict[str, Callable] = {
    "Housing / Dado (2-Board)": housing_2board.execute_two_board_housing,
}

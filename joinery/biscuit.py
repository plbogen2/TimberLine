"""Biscuit slot joinery technique."""

import adsk.core
import adsk.fusion

import joinery_tools
from joinery import base


def execute_biscuit_slots(
    comp: adsk.fusion.Component,
    face: adsk.fusion.BRepFace,
    inputs: adsk.core.CommandInputs,
) -> None:
    """Cut evenly spaced #20/#10/#0 biscuit slots along ``face``."""
    sketch = comp.sketches.add(face)
    bounds = base.face_bounds_2d(sketch, face)
    sketch.deleteMe()

    rects = joinery_tools.compute_biscuit_slot_rects(
        bounds,
        count=base.get_int(inputs, "holeCount"),
        edge_inset=base.get_val(inputs, "holeInset"),
        slot_len=base.get_val(inputs, "jointWidth"),
        slot_thick=base.get_val(inputs, "holeDia"),
    )
    depth = base.get_val(inputs, "jointDepth")
    for idx, rect in enumerate(rects):
        base.cut_rect_on_face(comp, face, rect, depth, f"Biscuit Slot {idx + 1}")

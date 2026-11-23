"""Box / Finger joint joinery technique."""

import adsk.core
import adsk.fusion

import joinery_tools
from joinery import base


def execute_box_joint(
    comp: adsk.fusion.Component,
    face: adsk.fusion.BRepFace,
    inputs: adsk.core.CommandInputs,
    cut_even: bool = True,
) -> None:
    """Cut alternating rectangular finger slots across ``face``."""
    sketch = comp.sketches.add(face)
    bounds = base.face_bounds_2d(sketch, face)
    sketch.deleteMe()

    count = base.get_int(inputs, "holeCount")
    depth = base.get_val(inputs, "jointDepth")
    rects = joinery_tools.compute_finger_cut_rects(bounds, count, cut_even=cut_even)
    for idx, rect in enumerate(rects):
        base.cut_rect_on_face(comp, face, rect, depth, f"Box Finger {idx + 1}")

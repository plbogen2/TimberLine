"""Bridle (open mortise) joinery technique."""

import adsk.core
import adsk.fusion

import joinery_tools
from joinery import base


def execute_bridle_slot(
    comp: adsk.fusion.Component,
    face: adsk.fusion.BRepFace,
    inputs: adsk.core.CommandInputs,
) -> None:
    """Cut a centered open mortise (bridle slot) into an end face."""
    sketch = comp.sketches.add(face)
    bounds = base.face_bounds_2d(sketch, face)
    sketch.deleteMe()

    rect = joinery_tools.compute_centered_groove_rect(
        bounds, base.get_val(inputs, "jointWidth")
    )
    base.cut_rect_on_face(
        comp, face, rect, base.get_val(inputs, "jointDepth"), "Bridle Slot"
    )

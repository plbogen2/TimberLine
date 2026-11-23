"""Tongue and Groove (plus Spline Slot) joinery techniques."""

import adsk.core
import adsk.fusion

import joinery_tools
from joinery import base


def execute_tongue(
    comp: adsk.fusion.Component,
    face: adsk.fusion.BRepFace,
    inputs: adsk.core.CommandInputs,
) -> None:
    """Cut shoulders on both sides of ``face`` leaving a centered tongue."""
    sketch = comp.sketches.add(face)
    bounds = base.face_bounds_2d(sketch, face)
    sketch.deleteMe()

    tongue_thick = base.get_val(inputs, "jointWidth")
    tongue_len = base.get_val(inputs, "jointDepth")
    r_left, r_right = joinery_tools.compute_tongue_shoulder_rects(bounds, tongue_thick)
    base.cut_rect_on_face(comp, face, r_left, tongue_len, "Tongue Shoulder L")
    base.cut_rect_on_face(comp, face, r_right, tongue_len, "Tongue Shoulder R")


def execute_groove(
    comp: adsk.fusion.Component,
    face: adsk.fusion.BRepFace,
    inputs: adsk.core.CommandInputs,
) -> None:
    """Cut a centered full-length groove (or spline slot) into ``face``."""
    sketch = comp.sketches.add(face)
    bounds = base.face_bounds_2d(sketch, face)
    sketch.deleteMe()

    rect = joinery_tools.compute_centered_groove_rect(
        bounds, base.get_val(inputs, "jointWidth")
    )
    base.cut_rect_on_face(
        comp, face, rect, base.get_val(inputs, "jointDepth"), "Groove / Spline"
    )

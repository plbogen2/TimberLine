"""Dowel hole joinery technique."""

import adsk.core
import adsk.fusion

import joinery_tools
from joinery import base


def execute_dowel_holes(
    comp: adsk.fusion.Component,
    face: adsk.fusion.BRepFace,
    inputs: adsk.core.CommandInputs,
) -> None:
    """Drill evenly spaced dowel holes along ``face``'s longer axis."""
    sketch = comp.sketches.add(face)
    bounds = base.face_bounds_2d(sketch, face)
    centers_2d = joinery_tools.compute_dowel_centers(
        bounds, base.get_int(inputs, "holeCount"), base.get_val(inputs, "holeInset")
    )
    centers_3d = [
        sketch.sketchToModelSpace(adsk.core.Point3D.create(cx, cy, 0.0))
        for cx, cy in centers_2d
    ]
    sketch.deleteMe()
    base.cut_circles_on_plane(
        comp,
        face,
        centers_3d,
        base.get_val(inputs, "holeDia"),
        base.get_val(inputs, "jointDepth"),
        "Dowel Holes",
    )

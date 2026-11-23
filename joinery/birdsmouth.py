"""Birdsmouth rafter notch joinery technique."""

import adsk.core
import adsk.fusion

import joinery_tools
from joinery import base


def execute_birdsmouth(
    comp: adsk.fusion.Component,
    face: adsk.fusion.BRepFace,
    edge: adsk.fusion.BRepEdge,
    inputs: adsk.core.CommandInputs,
) -> None:
    """Cut a triangular birdsmouth (seat + plumb) notch along a rafter edge."""
    sketch = comp.sketches.add(face)
    sketch.name = "Birdsmouth Notch"
    bounds = base.face_bounds_2d(sketch, face)
    p0 = sketch.modelToSketchSpace(edge.startVertex.geometry)
    p1 = sketch.modelToSketchSpace(edge.endVertex.geometry)

    tri = joinery_tools.compute_birdsmouth_triangle(
        bounds,
        (p0.x, p0.y),
        (p1.x, p1.y),
        offset=base.get_val(inputs, "jointOffset"),
        seat_len=base.get_val(inputs, "jointWidth"),
        plumb_depth=base.get_val(inputs, "tenonWidth"),
    )
    pts = [adsk.core.Point3D.create(x, y, 0.0) for x, y in tri]
    lines = sketch.sketchCurves.sketchLines
    for i in range(3):
        lines.addByTwoPoints(pts[i], pts[(i + 1) % 3])

    if sketch.profiles.count > 0:
        base.cut_profiles(comp, sketch.profiles.item(0), base.get_val(inputs, "jointDepth"))

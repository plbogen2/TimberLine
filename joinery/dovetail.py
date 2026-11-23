"""Dovetail (Tails and Pins) joinery technique."""

import adsk.core
import adsk.fusion

import joinery_tools
from joinery import base


def execute_dovetail(
    comp: adsk.fusion.Component,
    face: adsk.fusion.BRepFace,
    inputs: adsk.core.CommandInputs,
    is_pins: bool = False,
) -> None:
    """Cut trapezoidal dovetail tail or pin pockets across ``face``."""
    sketch = comp.sketches.add(face)
    sketch.name = "Dovetail Pins" if is_pins else "Dovetail Tails"
    bounds = base.face_bounds_2d(sketch, face)

    count = base.get_int(inputs, "holeCount")
    depth = base.get_val(inputs, "jointDepth")
    polys = joinery_tools.compute_dovetail_cut_polygons(
        bounds, count=count, depth=depth, is_pins=is_pins
    )

    lines = sketch.sketchCurves.sketchLines
    for poly in polys:
        pts = [adsk.core.Point3D.create(x, y, 0.0) for x, y in poly]
        for i in range(len(pts)):
            lines.addByTwoPoints(pts[i], pts[(i + 1) % len(pts)])

    if sketch.profiles.count == 0:
        return
    profs = adsk.core.ObjectCollection.create()
    for i in range(sketch.profiles.count):
        profs.add(sketch.profiles.item(i))
    base.cut_profiles(comp, profs, depth)

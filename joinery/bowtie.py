"""Bowtie / Butterfly key inlay pocket joinery technique."""

import adsk.core
import adsk.fusion

import joinery_tools
from joinery import base


def execute_bowtie(
    comp: adsk.fusion.Component,
    face: adsk.fusion.BRepFace,
    inputs: adsk.core.CommandInputs,
) -> None:
    """Cut a centered double-dovetail bowtie/butterfly key pocket into ``face``."""
    sketch = comp.sketches.add(face)
    sketch.name = "Bowtie Key Pocket"
    bounds = base.face_bounds_2d(sketch, face)

    poly = joinery_tools.compute_bowtie_polygon(
        bounds,
        width=base.get_val(inputs, "jointWidth"),
        length=base.get_val(inputs, "tenonWidth"),
    )
    pts = [adsk.core.Point3D.create(x, y, 0.0) for x, y in poly]
    lines = sketch.sketchCurves.sketchLines
    for i in range(len(pts)):
        lines.addByTwoPoints(pts[i], pts[(i + 1) % len(pts)])

    if sketch.profiles.count > 0:
        base.cut_profiles(comp, sketch.profiles.item(0), base.get_val(inputs, "jointDepth"))

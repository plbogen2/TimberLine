"""Mortise and Tenon joinery techniques."""

import adsk.core
import adsk.fusion

import joinery_tools
from joinery import base


def execute_tenon(
    comp: adsk.fusion.Component,
    face: adsk.fusion.BRepFace,
    inputs: adsk.core.CommandInputs,
) -> None:
    """Cut shoulders around the end face to leave a centered rectangular tenon."""
    thickness_cm = base.get_val(inputs, "tenonThick")
    width_cm = base.get_val(inputs, "tenonWidth")
    length_cm = base.get_val(inputs, "tenonLength")

    sketch = comp.sketches.add(face)
    sketch.name = "Tenon Profile"
    bounds = base.face_bounds_2d(sketch, face)
    u_min, v_min, u_max, v_max = bounds

    lines = sketch.sketchCurves.sketchLines
    lines.addTwoPointRectangle(
        adsk.core.Point3D.create(u_min - 0.01, v_min - 0.01, 0.0),
        adsk.core.Point3D.create(u_max + 0.01, v_max + 0.01, 0.0),
    )
    iu0, iv0, iu1, iv1 = joinery_tools.compute_centered_rect(
        bounds, thickness_cm, width_cm
    )
    lines.addTwoPointRectangle(
        adsk.core.Point3D.create(iu0, iv0, 0.0),
        adsk.core.Point3D.create(iu1, iv1, 0.0),
    )

    for i in range(sketch.profiles.count):
        prof = sketch.profiles.item(i)
        if prof.profileLoops.count >= 2:
            base.cut_profiles(comp, prof, length_cm)
            return


def execute_mortise(
    comp: adsk.fusion.Component,
    face: adsk.fusion.BRepFace,
    inputs: adsk.core.CommandInputs,
) -> None:
    """Cut a centered rectangular mortise pocket into ``face``."""
    sketch = comp.sketches.add(face)
    bounds = base.face_bounds_2d(sketch, face)
    sketch.deleteMe()
    rect = joinery_tools.compute_centered_rect(
        bounds, base.get_val(inputs, "jointWidth"), base.get_val(inputs, "tenonWidth")
    )
    base.cut_rect_on_face(
        comp, face, rect, base.get_val(inputs, "jointDepth"), "Mortise"
    )

"""Shared Fusion geometry and parameter helpers for joinery technique modules."""

import adsk.core
import adsk.fusion

import joinery_tools


def face_bounds_2d(
    sketch: adsk.fusion.Sketch, face: adsk.fusion.BRepFace
) -> joinery_tools.Rect2D:
    us = []
    vs = []
    for i in range(face.vertices.count):
        pt = sketch.modelToSketchSpace(face.vertices.item(i).geometry)
        us.append(pt.x)
        vs.append(pt.y)
    return (min(us), min(vs), max(us), max(vs))


def target_component_for_face(
    design: adsk.fusion.Design, face: adsk.fusion.BRepFace
) -> adsk.fusion.Component:
    body = face.body
    if body and body.parentComponent:
        return body.parentComponent
    return design.activeComponent


def cut_profiles(
    comp: adsk.fusion.Component,
    profiles,
    depth_cm: float,
) -> None:
    extrudes = comp.features.extrudeFeatures
    ext_input = extrudes.createInput(
        profiles, adsk.fusion.FeatureOperations.CutFeatureOperation
    )
    ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(-depth_cm))
    extrudes.add(ext_input)


def cut_rect_on_face(
    comp: adsk.fusion.Component,
    face: adsk.fusion.BRepFace,
    rect: joinery_tools.Rect2D,
    depth_cm: float,
    name: str,
) -> None:
    sketch = comp.sketches.add(face)
    sketch.name = name
    u0, v0, u1, v1 = rect
    sketch.sketchCurves.sketchLines.addTwoPointRectangle(
        adsk.core.Point3D.create(u0, v0, 0.0),
        adsk.core.Point3D.create(u1, v1, 0.0),
    )
    if sketch.profiles.count > 0:
        cut_profiles(comp, sketch.profiles.item(0), depth_cm)


def cut_circles_on_plane(
    comp: adsk.fusion.Component,
    plane,
    centers_3d: list,
    dia_cm: float,
    depth_cm: float,
    name: str,
) -> None:
    sketch = comp.sketches.add(plane)
    sketch.name = name
    radius = dia_cm / 2.0
    circles = sketch.sketchCurves.sketchCircles
    for c3 in centers_3d:
        cp = sketch.modelToSketchSpace(c3)
        circles.addByCenterRadius(adsk.core.Point3D.create(cp.x, cp.y, 0.0), radius)

    if sketch.profiles.count == 0:
        return
    profs = adsk.core.ObjectCollection.create()
    for i in range(sketch.profiles.count):
        profs.add(sketch.profiles.item(i))
    cut_profiles(comp, profs, depth_cm)


def get_val(inputs: adsk.core.CommandInputs, input_id: str) -> float:
    return adsk.core.ValueCommandInput.cast(inputs.itemById(input_id)).value


def get_int(inputs: adsk.core.CommandInputs, input_id: str) -> int:
    return adsk.core.IntegerSpinnerCommandInput.cast(
        inputs.itemById(input_id)
    ).value

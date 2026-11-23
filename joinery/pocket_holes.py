"""15-degree Kreg-style pocket hole joinery technique."""

import math

import adsk.core
import adsk.fusion

import joinery_tools
from joinery import base


def execute_pocket_holes(
    comp: adsk.fusion.Component,
    face: adsk.fusion.BRepFace,
    edge: adsk.fusion.BRepEdge,
    inputs: adsk.core.CommandInputs,
) -> None:
    """Drill 15-degree pocket bores and pilot holes toward ``edge``."""
    count = base.get_int(inputs, "holeCount")
    setback_cm = base.get_val(inputs, "jointOffset")
    inset_cm = base.get_val(inputs, "holeInset")
    pocket_dia_cm = base.get_val(inputs, "holeDia")
    pilot_dia_cm = base.get_val(inputs, "pilotDia")
    pocket_depth_cm = base.get_val(inputs, "jointDepth")

    base_sketch = comp.sketches.add(face)
    base_sketch.name = "Pocket Hole Layout"
    bounds = base.face_bounds_2d(base_sketch, face)
    p0_3d = base_sketch.modelToSketchSpace(edge.startVertex.geometry)
    p1_3d = base_sketch.modelToSketchSpace(edge.endVertex.geometry)

    lp0, lp1, to_edge_2d, centers_2d = joinery_tools.compute_pocket_hole_line_and_centers(
        bounds, (p0_3d.x, p0_3d.y), (p1_3d.x, p1_3d.y), setback_cm, count, inset_cm
    )

    line = base_sketch.sketchCurves.sketchLines.addByTwoPoints(
        adsk.core.Point3D.create(lp0[0], lp0[1], 0.0),
        adsk.core.Point3D.create(lp1[0], lp1[1], 0.0),
    )
    line.isConstruction = True

    origin_3d = base_sketch.sketchToModelSpace(adsk.core.Point3D.create(0.0, 0.0, 0.0))
    dir_pt_3d = base_sketch.sketchToModelSpace(
        adsk.core.Point3D.create(to_edge_2d[0], to_edge_2d[1], 0.0)
    )
    to_edge_vec = origin_3d.vectorTo(dir_pt_3d)
    to_edge_vec.normalize()

    planes = comp.constructionPlanes
    plane_input = planes.createInput()
    # 15-deg drill path from face => perpendicular plane tilted 75 deg (90 - 15).
    plane_input.setByAngle(line, adsk.core.ValueInput.createByString("75 deg"), face)
    angled_plane = planes.add(plane_input)

    if angled_plane.geometry.normal.dotProduct(to_edge_vec) > 0:
        angled_plane.deleteMe()
        plane_input = planes.createInput()
        plane_input.setByAngle(
            line, adsk.core.ValueInput.createByString("-75 deg"), face
        )
        angled_plane = planes.add(plane_input)

    back_offset_cm = (pocket_dia_cm / 2.0) + 0.5
    off_input = planes.createInput()
    off_input.setByOffset(angled_plane, adsk.core.ValueInput.createByReal(back_offset_cm))
    start_plane = planes.add(off_input)

    centers_3d = [
        base_sketch.sketchToModelSpace(adsk.core.Point3D.create(cx, cy, 0.0))
        for cx, cy in centers_2d
    ]

    base.cut_circles_on_plane(
        comp,
        start_plane,
        centers_3d,
        pocket_dia_cm,
        back_offset_cm + pocket_depth_cm,
        "Pocket Bore",
    )
    pilot_depth_cm = back_offset_cm + setback_cm / math.cos(math.radians(15.0)) + 1.0
    base.cut_circles_on_plane(
        comp, start_plane, centers_3d, pilot_dia_cm, pilot_depth_cm, "Pocket Pilot"
    )

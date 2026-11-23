"""Sliding dovetail slot joinery technique."""

import adsk.core
import adsk.fusion

from joinery import base


def execute_sliding_dovetail(
    comp: adsk.fusion.Component,
    face: adsk.fusion.BRepFace,
    edge: adsk.fusion.BRepEdge,
    inputs: adsk.core.CommandInputs,
) -> None:
    """Cut a full-length dovetail-profiled dado slot across ``face``."""
    offset = base.get_val(inputs, "jointOffset")
    neck_w = base.get_val(inputs, "jointWidth")
    depth = base.get_val(inputs, "jointDepth")
    flare = depth / 7.0

    ref_sk = comp.sketches.add(face)
    u_min, v_min, u_max, v_max = base.face_bounds_2d(ref_sk, face)
    p0 = ref_sk.modelToSketchSpace(edge.startVertex.geometry)
    p1 = ref_sk.modelToSketchSpace(edge.endVertex.geometry)

    du = abs(p0.x - p1.x)
    dv = abs(p0.y - p1.y)
    if du < dv:
        u_edge = 0.5 * (p0.x + p1.x)
        is_left = abs(u_edge - u_min) <= abs(u_edge - u_max)
        c = u_min + offset + 0.5 * neck_w if is_left else u_max - offset - 0.5 * neck_w
        mid_v = 0.5 * (v_min + v_max)
        span = v_max - v_min
        lp0 = adsk.core.Point3D.create(u_min, mid_v, 0.0)
        lp1 = adsk.core.Point3D.create(u_max, mid_v, 0.0)
        axis_is_u = True
    else:
        v_edge = 0.5 * (p0.y + p1.y)
        is_bottom = abs(v_edge - v_min) <= abs(v_edge - v_max)
        c = v_min + offset + 0.5 * neck_w if is_bottom else v_max - offset - 0.5 * neck_w
        mid_u = 0.5 * (u_min + u_max)
        span = u_max - u_min
        lp0 = adsk.core.Point3D.create(mid_u, v_min, 0.0)
        lp1 = adsk.core.Point3D.create(mid_u, v_max, 0.0)
        axis_is_u = False

    axis_line = ref_sk.sketchCurves.sketchLines.addByTwoPoints(lp0, lp1)
    axis_line.isConstruction = True

    p_in = comp.constructionPlanes.createInput()
    p_in.setByAngle(axis_line, adsk.core.ValueInput.createByString("90 deg"), face)
    cut_plane = comp.constructionPlanes.add(p_in)

    d_sk = comp.sketches.add(cut_plane)
    d_sk.name = "Sliding Dovetail Slot"
    half_n = 0.5 * neck_w
    half_b = half_n + flare
    trap = [
        (c - half_n, 0.01),
        (c + half_n, 0.01),
        (c + half_b, -depth),
        (c - half_b, -depth),
    ]
    pts = []
    for coord, z_val in trap:
        p3_f = (
            adsk.core.Point3D.create(coord, 0.5 * (v_min + v_max), z_val)
            if axis_is_u
            else adsk.core.Point3D.create(0.5 * (u_min + u_max), coord, z_val)
        )
        p2 = d_sk.modelToSketchSpace(ref_sk.sketchToModelSpace(p3_f))
        pts.append(adsk.core.Point3D.create(p2.x, p2.y, 0.0))

    lines = d_sk.sketchCurves.sketchLines
    for i in range(4):
        lines.addByTwoPoints(pts[i], pts[(i + 1) % 4])

    if d_sk.profiles.count > 0:
        ext_in = comp.features.extrudeFeatures.createInput(
            d_sk.profiles.item(0), adsk.fusion.FeatureOperations.CutFeatureOperation
        )
        ext_in.setDistanceExtent(
            True, adsk.core.ValueInput.createByReal(span / 2.0 + 0.05)
        )
        comp.features.extrudeFeatures.add(ext_in)

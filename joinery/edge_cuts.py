"""Edge-based joinery techniques: Rabbet, Dado / Groove, and Half-Lap."""

import adsk.core
import adsk.fusion

import joinery_tools
from joinery import base


def execute_edge_joint(
    joint_type: str,
    comp: adsk.fusion.Component,
    face: adsk.fusion.BRepFace,
    edge: adsk.fusion.BRepEdge,
    inputs: adsk.core.CommandInputs,
) -> None:
    """Cut a Rabbet, Dado / Groove, or Half-Lap parallel to ``edge`` on ``face``."""
    sketch = comp.sketches.add(face)
    bounds = base.face_bounds_2d(sketch, face)
    p0 = sketch.modelToSketchSpace(edge.startVertex.geometry)
    p1 = sketch.modelToSketchSpace(edge.endVertex.geometry)
    sketch.deleteMe()

    ref_sel = adsk.core.SelectionCommandInput.cast(inputs.itemById("refBoard"))
    use_offset = joint_type == "Dado / Groove" or (
        joint_type == "Half-Lap" and ref_sel and ref_sel.selectionCount > 0
    )
    offset = base.get_val(inputs, "jointOffset") if use_offset else 0.0
    rect = joinery_tools.compute_edge_strip_rect(
        bounds,
        (p0.x, p0.y),
        (p1.x, p1.y),
        base.get_val(inputs, "jointWidth"),
        offset=offset,
    )
    base.cut_rect_on_face(comp, face, rect, base.get_val(inputs, "jointDepth"), joint_type)

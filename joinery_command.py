"""Autodesk Fusion command: Add Joinery (Rabbet, Dado, Half-Lap, Tenon, Mortise, Pocket Holes, Dowels)."""

import math
import os
import traceback
from typing import Dict, List, Tuple

import adsk.core
import adsk.fusion

import fusion_ui
import joinery_tools

JOINERY_CMD_ID = "TimberLineJoineryCmd"
JOINERY_CMD_NAME = "Add Joinery"
JOINERY_CMD_DESC = (
    "Cut common woodworking joints (Rabbet, Dado, Half-Lap, Tenon, Mortise, "
    "15° Pocket Holes, Dowel Holes) into existing lumber or sheet stock."
)

JOINT_TYPES = [
    "Rabbet",
    "Dado / Groove",
    "Half-Lap",
    "Housing / Dado (2-Board)",
    "Tenon",
    "Mortise",
    "Pocket Holes (15°)",
    "Dowel Holes",
]

_EDGE_REQUIRED_JOINTS = {"Rabbet", "Dado / Groove", "Half-Lap", "Pocket Holes (15°)"}
_BOARD_REF_JOINTS = {"Rabbet", "Dado / Groove", "Half-Lap"}
_TWO_BOARD_JOINTS = {"Housing / Dado (2-Board)"}

_ALL_PARAM_INPUT_IDS = (
    "jointWidth",
    "jointDepth",
    "jointOffset",
    "tenonThick",
    "tenonWidth",
    "tenonLength",
    "holeCount",
    "holeDia",
    "pilotDia",
    "holeInset",
)

# Declarative per-joint UI layout: maps joint name -> list of (input_id, label_override, default_expr).
_JOINT_UI_CONFIG: Dict[str, List[Tuple[str, str, str]]] = {
    "Rabbet": [
        ("jointWidth", "Width", "0.5 in"),
        ("jointDepth", "Depth", "0.375 in"),
    ],
    "Dado / Groove": [
        ("jointOffset", "Offset from Edge", "6 in"),
        ("jointWidth", "Dado Width", "23/32 in"),
        ("jointDepth", "Depth", "0.375 in"),
    ],
    "Half-Lap": [
        ("jointWidth", "Lap Length", "3.5 in"),
        ("jointDepth", "Depth", "0.75 in"),
    ],
    "Housing / Dado (2-Board)": [],
    "Tenon": [
        ("tenonThick", "Tenon Thickness", "0.5 in"),
        ("tenonWidth", "Tenon Width", "2.5 in"),
        ("tenonLength", "Tenon Length", "1.5 in"),
    ],
    "Mortise": [
        ("jointWidth", "Mortise Width", "0.5 in"),
        ("tenonWidth", "Mortise Length", "2.5 in"),
        ("jointDepth", "Mortise Depth", "1.625 in"),
    ],
    "Pocket Holes (15°)": [
        ("holeCount", "", ""),
        ("jointOffset", "Setback from Edge", "1.25 in"),
        ("holeInset", "", ""),
        ("holeDia", "Pocket Dia", "0.375 in"),
        ("pilotDia", "", ""),
        ("jointDepth", "Pocket Depth", "1.0 in"),
    ],
    "Dowel Holes": [
        ("holeCount", "", ""),
        ("holeDia", "Dowel Dia", "0.375 in"),
        ("jointDepth", "Hole Depth", "0.75 in"),
        ("holeInset", "", ""),
    ],
}


def _face_bounds_2d(
    sketch: adsk.fusion.Sketch, face: adsk.fusion.BRepFace
) -> joinery_tools.Rect2D:
    us = []
    vs = []
    for i in range(face.vertices.count):
        pt = sketch.modelToSketchSpace(face.vertices.item(i).geometry)
        us.append(pt.x)
        vs.append(pt.y)
    return (min(us), min(vs), max(us), max(vs))


def _project_body_bounds_2d(
    sketch: adsk.fusion.Sketch, body
) -> joinery_tools.Rect2D:
    bb = body.boundingBox
    xs = (bb.minPoint.x, bb.maxPoint.x)
    ys = (bb.minPoint.y, bb.maxPoint.y)
    zs = (bb.minPoint.z, bb.maxPoint.z)
    us = []
    vs = []
    for x in xs:
        for y in ys:
            for z in zs:
                pt = sketch.modelToSketchSpace(adsk.core.Point3D.create(x, y, z))
                us.append(pt.x)
                vs.append(pt.y)
    return (min(us), min(vs), max(us), max(vs))


def _apply_board_reference(inputs: adsk.core.CommandInputs) -> None:
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if not design:
        return
    jt = adsk.core.DropDownCommandInput.cast(
        inputs.itemById("jointType")
    ).selectedItem.name
    if jt not in _BOARD_REF_JOINTS:
        return

    face_sel = adsk.core.SelectionCommandInput.cast(inputs.itemById("jointFace"))
    edge_sel = adsk.core.SelectionCommandInput.cast(inputs.itemById("jointEdge"))
    ref_sel = adsk.core.SelectionCommandInput.cast(inputs.itemById("refBoard"))
    if (
        not face_sel
        or not edge_sel
        or not ref_sel
        or face_sel.selectionCount == 0
        or edge_sel.selectionCount == 0
        or ref_sel.selectionCount == 0
    ):
        return

    face = adsk.fusion.BRepFace.cast(face_sel.selection(0).entity)
    edge = adsk.fusion.BRepEdge.cast(edge_sel.selection(0).entity)
    ref_body = ref_sel.selection(0).entity
    comp = _target_component_for_face(design, face)

    sketch = comp.sketches.add(face)
    bounds = _face_bounds_2d(sketch, face)
    p0 = sketch.modelToSketchSpace(edge.startVertex.geometry)
    p1 = sketch.modelToSketchSpace(edge.endVertex.geometry)
    ref_bounds = _project_body_bounds_2d(sketch, ref_body)
    sketch.deleteMe()

    offset_cm, width_cm = joinery_tools.compute_board_reference_params(
        bounds, (p0.x, p0.y), (p1.x, p1.y), ref_bounds
    )
    if width_cm > 0:
        adsk.core.ValueCommandInput.cast(inputs.itemById("jointWidth")).value = width_cm
    if jt in ("Dado / Groove", "Half-Lap"):
        off_in = adsk.core.ValueCommandInput.cast(inputs.itemById("jointOffset"))
        off_in.value = offset_cm
        if jt == "Half-Lap" and offset_cm > 1e-4:
            off_in.name = "Offset from Edge"
            off_in.isVisible = True


def _target_component_for_face(
    design: adsk.fusion.Design, face: adsk.fusion.BRepFace
) -> adsk.fusion.Component:
    body = face.body
    if body and body.parentComponent:
        return body.parentComponent
    return design.activeComponent


def _cut_profiles(
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


def _cut_rect_on_face(
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
        _cut_profiles(comp, sketch.profiles.item(0), depth_cm)


def _cut_circles_on_plane(
    comp: adsk.fusion.Component,
    plane,
    centers_3d: List[adsk.core.Point3D],
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
    _cut_profiles(comp, profs, depth_cm)


def _cut_tenon(
    comp: adsk.fusion.Component,
    face: adsk.fusion.BRepFace,
    thickness_cm: float,
    width_cm: float,
    length_cm: float,
) -> None:
    sketch = comp.sketches.add(face)
    sketch.name = "Tenon Profile"
    bounds = _face_bounds_2d(sketch, face)
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
            _cut_profiles(comp, prof, length_cm)
            return


def _cut_dowel_holes(
    comp: adsk.fusion.Component,
    face: adsk.fusion.BRepFace,
    count: int,
    dia_cm: float,
    depth_cm: float,
    inset_cm: float,
) -> None:
    sketch = comp.sketches.add(face)
    bounds = _face_bounds_2d(sketch, face)
    centers_2d = joinery_tools.compute_dowel_centers(bounds, count, inset_cm)
    centers_3d = [
        sketch.sketchToModelSpace(adsk.core.Point3D.create(cx, cy, 0.0))
        for cx, cy in centers_2d
    ]
    sketch.deleteMe()
    _cut_circles_on_plane(comp, face, centers_3d, dia_cm, depth_cm, "Dowel Holes")


def _cut_pocket_holes(
    comp: adsk.fusion.Component,
    face: adsk.fusion.BRepFace,
    edge: adsk.fusion.BRepEdge,
    count: int,
    setback_cm: float,
    inset_cm: float,
    pocket_dia_cm: float,
    pilot_dia_cm: float,
    pocket_depth_cm: float,
) -> None:
    base_sketch = comp.sketches.add(face)
    base_sketch.name = "Pocket Hole Layout"
    bounds = _face_bounds_2d(base_sketch, face)
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
    # A 15-degree drill path from the face means the plane perpendicular to the drill
    # is tilted 75 degrees (90 - 15) from the face.
    plane_input.setByAngle(line, adsk.core.ValueInput.createByString("75 deg"), face)
    angled_plane = planes.add(plane_input)

    # Cut direction is -normal; ensure it points toward the selected edge.
    if angled_plane.geometry.normal.dotProduct(to_edge_vec) > 0:
        angled_plane.deleteMe()
        plane_input = planes.createInput()
        plane_input.setByAngle(
            line, adsk.core.ValueInput.createByString("-75 deg"), face
        )
        angled_plane = planes.add(plane_input)

    # Offset the drill start plane outward along +normal so the full bore
    # enters cleanly through the face without leaving an uncut lip.
    back_offset_cm = (pocket_dia_cm / 2.0) + 0.5
    off_input = planes.createInput()
    off_input.setByOffset(angled_plane, adsk.core.ValueInput.createByReal(back_offset_cm))
    start_plane = planes.add(off_input)

    centers_3d = [
        base_sketch.sketchToModelSpace(adsk.core.Point3D.create(cx, cy, 0.0))
        for cx, cy in centers_2d
    ]

    _cut_circles_on_plane(
        comp,
        start_plane,
        centers_3d,
        pocket_dia_cm,
        back_offset_cm + pocket_depth_cm,
        "Pocket Bore",
    )
    pilot_depth_cm = back_offset_cm + setback_cm / math.cos(math.radians(15.0)) + 1.0
    _cut_circles_on_plane(
        comp, start_plane, centers_3d, pilot_dia_cm, pilot_depth_cm, "Pocket Pilot"
    )


def _execute_joinery(inputs: adsk.core.CommandInputs) -> None:
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if not design:
        return

    joint_type = adsk.core.DropDownCommandInput.cast(
        inputs.itemById("jointType")
    ).selectedItem.name

    if joint_type == "Housing / Dado (2-Board)":
        tgt_sel = adsk.core.SelectionCommandInput.cast(inputs.itemById("targetBoard"))
        tool_sel = adsk.core.SelectionCommandInput.cast(inputs.itemById("refBoard"))
        if (
            not tgt_sel
            or not tool_sel
            or tgt_sel.selectionCount == 0
            or tool_sel.selectionCount == 0
        ):
            return
        target_body = tgt_sel.selection(0).entity
        tool_body = tool_sel.selection(0).entity
        comp = target_body.parentComponent or design.activeComponent
        tools = adsk.core.ObjectCollection.create()
        tools.add(tool_body)
        comb = comp.features.combineFeatures
        comb_in = comb.createInput(target_body, tools)
        comb_in.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
        comb_in.isKeepToolBodies = True
        comb.add(comb_in)
        return

    face_sel = adsk.core.SelectionCommandInput.cast(inputs.itemById("jointFace"))
    if face_sel.selectionCount == 0:
        return
    face = adsk.fusion.BRepFace.cast(face_sel.selection(0).entity)
    comp = _target_component_for_face(design, face)

    edge_sel = adsk.core.SelectionCommandInput.cast(inputs.itemById("jointEdge"))
    edge = (
        adsk.fusion.BRepEdge.cast(edge_sel.selection(0).entity)
        if edge_sel.selectionCount > 0
        else None
    )

    def _val(input_id: str) -> float:
        return adsk.core.ValueCommandInput.cast(inputs.itemById(input_id)).value

    def _int(input_id: str) -> int:
        return adsk.core.IntegerSpinnerCommandInput.cast(
            inputs.itemById(input_id)
        ).value

    if joint_type in ("Rabbet", "Half-Lap", "Dado / Groove"):
        if edge is None:
            return
        sketch = comp.sketches.add(face)
        bounds = _face_bounds_2d(sketch, face)
        p0 = sketch.modelToSketchSpace(edge.startVertex.geometry)
        p1 = sketch.modelToSketchSpace(edge.endVertex.geometry)
        sketch.deleteMe()

        ref_sel = adsk.core.SelectionCommandInput.cast(inputs.itemById("refBoard"))
        use_offset = joint_type == "Dado / Groove" or (
            joint_type == "Half-Lap" and ref_sel and ref_sel.selectionCount > 0
        )
        offset = _val("jointOffset") if use_offset else 0.0
        rect = joinery_tools.compute_edge_strip_rect(
            bounds, (p0.x, p0.y), (p1.x, p1.y), _val("jointWidth"), offset=offset
        )
        _cut_rect_on_face(comp, face, rect, _val("jointDepth"), joint_type)

    elif joint_type == "Tenon":
        _cut_tenon(
            comp,
            face,
            _val("tenonThick"),
            _val("tenonWidth"),
            _val("tenonLength"),
        )

    elif joint_type == "Mortise":
        sketch = comp.sketches.add(face)
        bounds = _face_bounds_2d(sketch, face)
        sketch.deleteMe()
        rect = joinery_tools.compute_centered_rect(
            bounds, _val("jointWidth"), _val("tenonWidth")
        )
        _cut_rect_on_face(comp, face, rect, _val("jointDepth"), "Mortise")

    elif joint_type == "Pocket Holes (15°)":
        if edge is None:
            return
        _cut_pocket_holes(
            comp,
            face,
            edge,
            _int("holeCount"),
            _val("jointOffset"),
            _val("holeInset"),
            _val("holeDia"),
            _val("pilotDia"),
            _val("jointDepth"),
        )

    elif joint_type == "Dowel Holes":
        _cut_dowel_holes(
            comp,
            face,
            _int("holeCount"),
            _val("holeDia"),
            _val("jointDepth"),
            _val("holeInset"),
        )


class JoineryExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args: adsk.core.CommandEventArgs):
        try:
            _execute_joinery(args.command.commandInputs)
        except Exception:
            ui = adsk.core.Application.get().userInterface
            if ui:
                ui.messageBox(f"Failed to add joinery:\n{traceback.format_exc()}")


class JoineryInputChangedHandler(adsk.core.InputChangedEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args: adsk.core.InputChangedEventArgs):
        try:
            inputs = args.inputs
            changed_id = args.input.id
            if changed_id in ("refBoard", "jointEdge", "jointFace"):
                _apply_board_reference(inputs)
                return
            if changed_id != "jointType":
                return
            jt = adsk.core.DropDownCommandInput.cast(args.input).selectedItem.name

            face_sel = adsk.core.SelectionCommandInput.cast(
                inputs.itemById("jointFace")
            )
            if face_sel:
                face_sel.isVisible = jt not in _TWO_BOARD_JOINTS

            edge_sel = adsk.core.SelectionCommandInput.cast(
                inputs.itemById("jointEdge")
            )
            edge_sel.isVisible = jt in _EDGE_REQUIRED_JOINTS

            tgt_sel = adsk.core.SelectionCommandInput.cast(
                inputs.itemById("targetBoard")
            )
            if tgt_sel:
                tgt_sel.isVisible = jt in _TWO_BOARD_JOINTS

            ref_sel = adsk.core.SelectionCommandInput.cast(
                inputs.itemById("refBoard")
            )
            if ref_sel:
                ref_sel.isVisible = jt in _BOARD_REF_JOINTS or jt in _TWO_BOARD_JOINTS

            for input_id in _ALL_PARAM_INPUT_IDS:
                inputs.itemById(input_id).isVisible = False

            for input_id, label, expr in _JOINT_UI_CONFIG.get(jt, []):
                ctrl = inputs.itemById(input_id)
                if label:
                    ctrl.name = label
                if expr:
                    adsk.core.ValueCommandInput.cast(ctrl).expression = expr
                ctrl.isVisible = True

            _apply_board_reference(inputs)
        except Exception:
            pass


class JoineryValidateHandler(adsk.core.ValidateInputsEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args: adsk.core.ValidateInputsEventArgs):
        try:
            inputs = args.inputs
            jt = adsk.core.DropDownCommandInput.cast(
                inputs.itemById("jointType")
            ).selectedItem.name
            if jt in _TWO_BOARD_JOINTS:
                tgt_sel = adsk.core.SelectionCommandInput.cast(
                    inputs.itemById("targetBoard")
                )
                ref_sel = adsk.core.SelectionCommandInput.cast(
                    inputs.itemById("refBoard")
                )
                if (
                    not tgt_sel
                    or not ref_sel
                    or tgt_sel.selectionCount == 0
                    or ref_sel.selectionCount == 0
                ):
                    args.areInputsValid = False
                    return
                args.areInputsValid = True
                return

            face_sel = adsk.core.SelectionCommandInput.cast(
                inputs.itemById("jointFace")
            )
            if not face_sel or face_sel.selectionCount == 0:
                args.areInputsValid = False
                return
            if jt in _EDGE_REQUIRED_JOINTS:
                edge_sel = adsk.core.SelectionCommandInput.cast(
                    inputs.itemById("jointEdge")
                )
                if not edge_sel or edge_sel.selectionCount == 0:
                    args.areInputsValid = False
                    return
            args.areInputsValid = True
        except Exception:
            args.areInputsValid = False


class JoineryCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self, handlers: list):
        super().__init__()
        self._handlers = handlers

    def notify(self, args: adsk.core.CommandCreatedEventArgs):
        try:
            cmd = args.command
            inputs = cmd.commandInputs

            jt_dd = inputs.addDropDownCommandInput(
                "jointType",
                "Joint Type",
                adsk.core.DropDownStyles.TextListDropDownStyle,
            )
            for idx, jt in enumerate(JOINT_TYPES):
                jt_dd.listItems.add(jt, idx == 0, "")

            face_sel = inputs.addSelectionInput(
                "jointFace", "Target Face", "Select the planar face to cut"
            )
            face_sel.addSelectionFilter("PlanarFaces")
            face_sel.setSelectionLimits(0, 1)

            tgt_sel = inputs.addSelectionInput(
                "targetBoard", "Target Board", "Select the board to cut into"
            )
            tgt_sel.addSelectionFilter("Bodies")
            tgt_sel.setSelectionLimits(0, 1)
            tgt_sel.isVisible = False

            edge_sel = inputs.addSelectionInput(
                "jointEdge", "Reference Edge", "Select the edge on that face"
            )
            edge_sel.addSelectionFilter("Edges")
            edge_sel.setSelectionLimits(0, 1)

            ref_sel = inputs.addSelectionInput(
                "refBoard",
                "Reference Board",
                "Optional: select mating board to auto-size width/offset",
            )
            ref_sel.addSelectionFilter("Bodies")
            ref_sel.setSelectionLimits(0, 1)

            inputs.addValueInput(
                "jointOffset",
                "Offset from Edge",
                "in",
                adsk.core.ValueInput.createByString("6 in"),
            ).isVisible = False
            inputs.addValueInput(
                "jointWidth",
                "Width",
                "in",
                adsk.core.ValueInput.createByString("0.5 in"),
            )
            inputs.addValueInput(
                "jointDepth",
                "Depth",
                "in",
                adsk.core.ValueInput.createByString("0.375 in"),
            )

            inputs.addValueInput(
                "tenonThick",
                "Tenon Thickness",
                "in",
                adsk.core.ValueInput.createByString("0.5 in"),
            ).isVisible = False
            inputs.addValueInput(
                "tenonWidth",
                "Tenon Width",
                "in",
                adsk.core.ValueInput.createByString("2.5 in"),
            ).isVisible = False
            inputs.addValueInput(
                "tenonLength",
                "Tenon Length",
                "in",
                adsk.core.ValueInput.createByString("1.5 in"),
            ).isVisible = False

            inputs.addIntegerSpinnerCommandInput(
                "holeCount", "Hole Count", 1, 12, 1, 2
            ).isVisible = False
            inputs.addValueInput(
                "holeDia",
                "Pocket Dia",
                "in",
                adsk.core.ValueInput.createByString("0.375 in"),
            ).isVisible = False
            inputs.addValueInput(
                "pilotDia",
                "Pilot Dia",
                "in",
                adsk.core.ValueInput.createByString("0.15625 in"),
            ).isVisible = False
            inputs.addValueInput(
                "holeInset",
                "Edge Inset",
                "in",
                adsk.core.ValueInput.createByString("0.75 in"),
            ).isVisible = False

            on_exec = JoineryExecuteHandler()
            cmd.execute.add(on_exec)
            self._handlers.append(on_exec)

            on_chg = JoineryInputChangedHandler()
            cmd.inputChanged.add(on_chg)
            self._handlers.append(on_chg)

            on_val = JoineryValidateHandler()
            cmd.validateInputs.add(on_val)
            self._handlers.append(on_val)
        except Exception:
            ui = adsk.core.Application.get().userInterface
            if ui:
                ui.messageBox(
                    f"Failed to initialize Add Joinery dialog:\n{traceback.format_exc()}"
                )


def register_joinery_command(
    ui: adsk.core.UserInterface,
    panel_id: str,
    addin_dir: str,
    handlers: list,
) -> None:
    fusion_ui.register_panel_command(
        ui=ui,
        panel_id=panel_id,
        cmd_id=JOINERY_CMD_ID,
        cmd_name=JOINERY_CMD_NAME,
        cmd_desc=JOINERY_CMD_DESC,
        resource_dir=os.path.join(addin_dir, "resources", "JoineryIcon"),
        created_handler_factory=lambda: JoineryCommandCreatedHandler(handlers),
        handlers=handlers,
    )


def unregister_joinery_command(ui: adsk.core.UserInterface, panel_id: str) -> None:
    fusion_ui.unregister_panel_command(ui, panel_id, JOINERY_CMD_ID)

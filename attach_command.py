"""Autodesk Fusion command: Attach Board (extrude outward from selected face)."""

import os
import traceback
from typing import Dict, List, Tuple

import adsk.core
import adsk.fusion

import attach_planner
import fusion_ui
import lumber_catalog
import operation_log

ATTACH_CMD_ID = "TimberLineAttachCmd"
ATTACH_CMD_NAME = "Attach Board"
ATTACH_CMD_DESC = (
    "Attach a new board extending outward from an existing board's face and edge "
    "with a Butt, Half-Lap, Rabbet, Dado / Groove, or angled Miter joint."
)

_ATTACH_PARAM_IDS = ("attachJointDepth", "attachOffset", "attachOuterAngle")

_ATTACH_UI_CONFIG: Dict[str, List[Tuple[str, str, str]]] = {
    "Butt (Flush)": [],
    "Half-Lap": [("attachJointDepth", "Lap Depth", "0.75 in")],
    "Rabbet": [("attachJointDepth", "Rabbet Depth", "0.375 in")],
    "Dado / Groove": [
        ("attachOffset", "Offset from Edge", "6 in"),
        ("attachJointDepth", "Dado Depth", "0.375 in"),
    ],
    "Miter": [("attachOuterAngle", "Outer Angle", "90 deg")],
}


def _face_bounds_2d(
    sketch: adsk.fusion.Sketch, face: adsk.fusion.BRepFace
) -> attach_planner.Rect2D:
    us = []
    vs = []
    for i in range(face.vertices.count):
        pt = sketch.modelToSketchSpace(face.vertices.item(i).geometry)
        us.append(pt.x)
        vs.append(pt.y)
    return (min(us), min(vs), max(us), max(vs))


def _measure_body_depth_behind_face(
    sketch: adsk.fusion.Sketch, body: adsk.fusion.BRepBody
) -> float:
    if not body:
        return 0.0
    bb = body.boundingBox
    zs = []
    for x in (bb.minPoint.x, bb.maxPoint.x):
        for y in (bb.minPoint.y, bb.maxPoint.y):
            for z in (bb.minPoint.z, bb.maxPoint.z):
                pt = sketch.modelToSketchSpace(adsk.core.Point3D.create(x, y, z))
                zs.append(pt.z)
    return max(0.0, -min(zs))


def _cut_profiles(
    comp: adsk.fusion.Component,
    sketch: adsk.fusion.Sketch,
    target_body: adsk.fusion.BRepBody,
    distance_cm: float,
    symmetric: bool = False,
) -> None:
    if sketch.profiles.count == 0:
        return
    profs = adsk.core.ObjectCollection.create()
    for i in range(sketch.profiles.count):
        profs.add(sketch.profiles.item(i))
    extrudes = comp.features.extrudeFeatures
    ext_in = extrudes.createInput(
        profs, adsk.fusion.FeatureOperations.CutFeatureOperation
    )
    ext_in.setDistanceExtent(
        symmetric, adsk.core.ValueInput.createByReal(distance_cm)
    )
    ext_in.participantBodies = [target_body]
    extrudes.add(ext_in)


def _cut_miter_wedge(
    comp: adsk.fusion.Component,
    face: adsk.fusion.BRepFace,
    ref_sketch: adsk.fusion.Sketch,
    plan: attach_planner.AttachPlan,
    triangles: tuple,
    target_body: adsk.fusion.BRepBody,
    name: str,
) -> None:
    mid = plan.miter_plane_coord + plan.miter_span_cm / 2.0
    u0, v0, u1, v1 = plan.cross_section_rect
    if plan.miter_axis_is_u:
        lp0 = adsk.core.Point3D.create(u0, mid, 0.0)
        lp1 = adsk.core.Point3D.create(u1, mid, 0.0)
    else:
        lp0 = adsk.core.Point3D.create(mid, v0, 0.0)
        lp1 = adsk.core.Point3D.create(mid, v1, 0.0)

    line_sk = comp.sketches.add(face)
    line_sk.name = f"{name} Axis"
    axis_line = line_sk.sketchCurves.sketchLines.addByTwoPoints(lp0, lp1)
    axis_line.isConstruction = True

    p_in = comp.constructionPlanes.createInput()
    p_in.setByAngle(axis_line, adsk.core.ValueInput.createByString("90 deg"), face)
    miter_plane = comp.constructionPlanes.add(p_in)

    m_sk = comp.sketches.add(miter_plane)
    m_sk.name = name
    lines = m_sk.sketchCurves.sketchLines
    for tri in triangles:
        pts_2d = []
        for coord, z_val in tri:
            p3_face = (
                adsk.core.Point3D.create(coord, mid, z_val)
                if plan.miter_axis_is_u
                else adsk.core.Point3D.create(mid, coord, z_val)
            )
            p3_model = ref_sketch.sketchToModelSpace(p3_face)
            p2 = m_sk.modelToSketchSpace(p3_model)
            pts_2d.append(adsk.core.Point3D.create(p2.x, p2.y, 0.0))
        lines.addByTwoPoints(pts_2d[0], pts_2d[1])
        lines.addByTwoPoints(pts_2d[1], pts_2d[2])
        lines.addByTwoPoints(pts_2d[2], pts_2d[0])

    _cut_profiles(
        comp, m_sk, target_body, plan.miter_span_cm / 2.0 + 0.05, symmetric=True
    )


def _execute_attach(inputs: adsk.core.CommandInputs, record_log: bool = True) -> None:
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if not design:
        return

    face_sel = adsk.core.SelectionCommandInput.cast(inputs.itemById("attachFace"))
    edge_sel = adsk.core.SelectionCommandInput.cast(inputs.itemById("attachEdge"))
    if (
        not face_sel
        or not edge_sel
        or face_sel.selectionCount == 0
        or edge_sel.selectionCount == 0
    ):
        return

    face = adsk.fusion.BRepFace.cast(face_sel.selection(0).entity)
    edge = adsk.fusion.BRepEdge.cast(edge_sel.selection(0).entity)
    existing_body = face.body
    existing_comp = (
        existing_body.parentComponent
        if existing_body and existing_body.parentComponent
        else design.activeComponent
    )

    size_label = adsk.core.DropDownCommandInput.cast(
        inputs.itemById("attachLumberSize")
    ).selectedItem.name
    lumber = lumber_catalog.LUMBER_BY_LABEL[size_label]
    length_cm = adsk.core.ValueCommandInput.cast(
        inputs.itemById("attachLength")
    ).value
    if length_cm <= 0:
        return

    length_mode = adsk.core.DropDownCommandInput.cast(
        inputs.itemById("attachLengthMode")
    ).selectedItem.name
    joint_type = adsk.core.DropDownCommandInput.cast(
        inputs.itemById("attachJointType")
    ).selectedItem.name
    on_edge = adsk.core.BoolValueCommandInput.cast(
        inputs.itemById("attachOnEdge")
    ).value
    flip_dir = adsk.core.BoolValueCommandInput.cast(
        inputs.itemById("attachFlip")
    ).value
    new_comp = adsk.core.BoolValueCommandInput.cast(
        inputs.itemById("attachNewComp")
    ).value

    joint_depth_cm = adsk.core.ValueCommandInput.cast(
        inputs.itemById("attachJointDepth")
    ).value
    offset_cm = adsk.core.ValueCommandInput.cast(
        inputs.itemById("attachOffset")
    ).value
    angle_rad = adsk.core.ValueCommandInput.cast(
        inputs.itemById("attachOuterAngle")
    ).value
    outer_angle_deg = angle_rad * (180.0 / 3.141592653589793) if angle_rad > 0 else 90.0

    ref_sketch = existing_comp.sketches.add(face)
    bounds = _face_bounds_2d(ref_sketch, face)
    p0 = ref_sketch.modelToSketchSpace(edge.startVertex.geometry)
    p1 = ref_sketch.modelToSketchSpace(edge.endVertex.geometry)
    existing_depth_cm = _measure_body_depth_behind_face(ref_sketch, existing_body)

    plan = attach_planner.compute_attach_plan(
        face_bounds=bounds,
        edge_p0=(p0.x, p0.y),
        edge_p1=(p1.x, p1.y),
        lumber=lumber,
        length_cm=length_cm,
        existing_depth_cm=existing_depth_cm,
        on_edge=on_edge,
        joint_type=joint_type,
        length_mode=length_mode,
        flip_along_edge=flip_dir,
        joint_depth_cm=joint_depth_cm,
        offset_cm=offset_cm,
        outer_angle_deg=outer_angle_deg,
    )
    board_name = lumber_catalog.format_component_name(
        lumber.nominal, plan.new_board_length_cm
    )

    if new_comp:
        try:
            occ = design.rootComponent.occurrences.addNewComponent(
                adsk.core.Matrix3D.create()
            )
            target_comp = occ.component
            target_comp.name = board_name
        except RuntimeError:
            target_comp = existing_comp
    else:
        target_comp = existing_comp

    # Cut pocket/lap/rabbet/dado into existing board
    if plan.existing_cut_depth_cm > 0 and existing_body:
        cut_sk = existing_comp.sketches.add(face)
        cut_sk.name = f"{joint_type} Cut"
        u0, v0, u1, v1 = plan.cross_section_rect
        cut_sk.sketchCurves.sketchLines.addTwoPointRectangle(
            adsk.core.Point3D.create(u0, v0, 0.0),
            adsk.core.Point3D.create(u1, v1, 0.0),
        )
        _cut_profiles(
            existing_comp, cut_sk, existing_body, -plan.existing_cut_depth_cm
        )

    # Start plane for new board
    if abs(plan.start_z_cm) > 1e-6:
        p_in = target_comp.constructionPlanes.createInput()
        p_in.setByOffset(face, adsk.core.ValueInput.createByReal(plan.start_z_cm))
        start_plane = target_comp.constructionPlanes.add(p_in)
    else:
        start_plane = face

    if joint_type == "Miter" and abs(plan.outer_angle_deg - 90.0) > 0.1:
        tilt_deg = plan.outer_angle_deg - 90.0
        tilt_in = target_comp.constructionPlanes.createInput()
        tilt_in.setByAngle(
            edge, adsk.core.ValueInput.createByString(f"{tilt_deg:g} deg"), start_plane
        )
        start_plane = target_comp.constructionPlanes.add(tilt_in)

    sk = target_comp.sketches.add(start_plane)
    sk.name = f"{lumber.nominal} Attached"
    u0, v0, u1, v1 = plan.cross_section_rect
    sk.sketchCurves.sketchLines.addTwoPointRectangle(
        adsk.core.Point3D.create(u0, v0, 0.0),
        adsk.core.Point3D.create(u1, v1, 0.0),
    )
    if sk.profiles.count == 0:
        ref_sketch.deleteMe()
        return
    extrudes = target_comp.features.extrudeFeatures
    ext_in = extrudes.createInput(
        sk.profiles.item(0), adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    )
    ext_in.setDistanceExtent(
        False, adsk.core.ValueInput.createByReal(plan.extrude_z_cm)
    )
    feat = extrudes.add(ext_in)
    new_body = feat.bodies.item(0)
    new_body.name = board_name

    if plan.miter_existing_tri and existing_body:
        _cut_miter_wedge(
            existing_comp,
            face,
            ref_sketch,
            plan,
            plan.miter_existing_tri,
            existing_body,
            "Miter Existing",
        )
    if plan.miter_new_tri:
        _cut_miter_wedge(
            target_comp,
            face,
            ref_sketch,
            plan,
            plan.miter_new_tri,
            new_body,
            "Miter New",
        )

    ref_sketch.deleteMe()

    if record_log:
        operation_log.SESSION_LOG.record(
            "Attach Board", f"{board_name} [{joint_type}]"
        )


class AttachExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args: adsk.core.CommandEventArgs):
        try:
            _execute_attach(args.command.commandInputs, record_log=True)
        except Exception:
            ui = adsk.core.Application.get().userInterface
            if ui:
                ui.messageBox(f"Failed to attach board:\n{traceback.format_exc()}")


class AttachPreviewHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args: adsk.core.CommandEventArgs):
        try:
            _execute_attach(args.command.commandInputs, record_log=False)
            args.isValidResult = True
        except Exception:
            pass


class AttachInputChangedHandler(adsk.core.InputChangedEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args: adsk.core.InputChangedEventArgs):
        try:
            if args.input.id != "attachJointType":
                return
            inputs = args.inputs
            jt = adsk.core.DropDownCommandInput.cast(args.input).selectedItem.name
            for pid in _ATTACH_PARAM_IDS:
                inputs.itemById(pid).isVisible = False
            for pid, label, expr in _ATTACH_UI_CONFIG.get(jt, []):
                ctrl = adsk.core.ValueCommandInput.cast(inputs.itemById(pid))
                ctrl.name = label
                ctrl.expression = expr
                ctrl.isVisible = True
        except Exception:
            pass


class AttachValidateHandler(adsk.core.ValidateInputsEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args: adsk.core.ValidateInputsEventArgs):
        try:
            inputs = args.inputs
            face_sel = adsk.core.SelectionCommandInput.cast(
                inputs.itemById("attachFace")
            )
            edge_sel = adsk.core.SelectionCommandInput.cast(
                inputs.itemById("attachEdge")
            )
            len_val = adsk.core.ValueCommandInput.cast(
                inputs.itemById("attachLength")
            )
            args.areInputsValid = bool(
                face_sel
                and edge_sel
                and len_val
                and face_sel.selectionCount == 1
                and edge_sel.selectionCount == 1
                and len_val.value > 0
            )
        except Exception:
            args.areInputsValid = False


class AttachCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self, handlers: list):
        super().__init__()
        self._handlers = handlers

    def notify(self, args: adsk.core.CommandCreatedEventArgs):
        try:
            cmd = args.command
            inputs = cmd.commandInputs

            face_sel = inputs.addSelectionInput(
                "attachFace",
                "Source Face",
                "Select the face the new board comes out from",
            )
            face_sel.addSelectionFilter("PlanarFaces")
            face_sel.setSelectionLimits(1, 1)

            edge_sel = inputs.addSelectionInput(
                "attachEdge",
                "Snap Edge",
                "Select edge on that face to align the new board flush",
            )
            edge_sel.addSelectionFilter("Edges")
            edge_sel.setSelectionLimits(1, 1)

            size_dd = inputs.addDropDownCommandInput(
                "attachLumberSize",
                "New Board Size",
                adsk.core.DropDownStyles.TextListDropDownStyle,
            )
            for idx, item in enumerate(lumber_catalog.LUMBER_SIZES):
                size_dd.listItems.add(item.label, idx == 0, "")

            inputs.addValueInput(
                "attachLength",
                "Length / Span",
                "in",
                adsk.core.ValueInput.createByString("48 in"),
            )

            mode_dd = inputs.addDropDownCommandInput(
                "attachLengthMode",
                "Length Mode",
                adsk.core.DropDownStyles.TextListDropDownStyle,
            )
            for idx, mode in enumerate(attach_planner.LENGTH_MODES):
                mode_dd.listItems.add(mode, idx == 0, "")

            jt_dd = inputs.addDropDownCommandInput(
                "attachJointType",
                "Corner Joint",
                adsk.core.DropDownStyles.TextListDropDownStyle,
            )
            for idx, jt in enumerate(attach_planner.ATTACH_JOINT_TYPES):
                jt_dd.listItems.add(jt, idx == 0, "")

            inputs.addValueInput(
                "attachOffset",
                "Offset from Edge",
                "in",
                adsk.core.ValueInput.createByString("6 in"),
            ).isVisible = False
            inputs.addValueInput(
                "attachJointDepth",
                "Joint Depth",
                "in",
                adsk.core.ValueInput.createByString("0.75 in"),
            ).isVisible = False
            inputs.addValueInput(
                "attachOuterAngle",
                "Outer Angle",
                "deg",
                adsk.core.ValueInput.createByString("90 deg"),
            ).isVisible = False

            inputs.addBoolValueInput(
                "attachOnEdge", "New Board On Edge", True, "", True
            )
            inputs.addBoolValueInput(
                "attachFlip", "Flip Along Edge", True, "", False
            )
            inputs.addBoolValueInput(
                "attachNewComp", "Create New Component", True, "", False
            )

            on_exec = AttachExecuteHandler()
            cmd.execute.add(on_exec)
            self._handlers.append(on_exec)

            on_prev = AttachPreviewHandler()
            cmd.executePreview.add(on_prev)
            self._handlers.append(on_prev)

            on_chg = AttachInputChangedHandler()
            cmd.inputChanged.add(on_chg)
            self._handlers.append(on_chg)

            on_val = AttachValidateHandler()
            cmd.validateInputs.add(on_val)
            self._handlers.append(on_val)
        except Exception:
            ui = adsk.core.Application.get().userInterface
            if ui:
                ui.messageBox(
                    f"Failed to initialize Attach Board dialog:\n{traceback.format_exc()}"
                )


def register_attach_command(
    ui: adsk.core.UserInterface,
    panel_id: str,
    addin_dir: str,
    handlers: list,
) -> None:
    fusion_ui.register_panel_command(
        ui=ui,
        panel_id=panel_id,
        cmd_id=ATTACH_CMD_ID,
        cmd_name=ATTACH_CMD_NAME,
        cmd_desc=ATTACH_CMD_DESC,
        resource_dir=os.path.join(addin_dir, "resources", "AttachIcon"),
        created_handler_factory=lambda: AttachCommandCreatedHandler(handlers),
        handlers=handlers,
    )


def unregister_attach_command(ui: adsk.core.UserInterface, panel_id: str) -> None:
    fusion_ui.unregister_panel_command(ui, panel_id, ATTACH_CMD_ID)

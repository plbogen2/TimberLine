"""Autodesk Fusion command: Attach Board (iterative board -> joint -> next board)."""

import os
import traceback

import adsk.core
import adsk.fusion

import attach_planner
import fusion_ui
import lumber_catalog
import operation_log

ATTACH_CMD_ID = "TimberLineAttachCmd"
ATTACH_CMD_NAME = "Attach Board"
ATTACH_CMD_DESC = (
    "Attach a new board to an existing board's face and edge with a "
    "Butt, 45° Miter, or Half-Lap joint, then continue building from there."
)


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


def _cut_sketch_on_face(
    comp: adsk.fusion.Component,
    plane,
    sketch: adsk.fusion.Sketch,
    target_body: adsk.fusion.BRepBody,
    distance_cm: float,
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
    ext_in.setDistanceExtent(False, adsk.core.ValueInput.createByReal(distance_cm))
    ext_in.participantBodies = [target_body]
    extrudes.add(ext_in)


def _cut_triangles(
    comp: adsk.fusion.Component,
    face: adsk.fusion.BRepFace,
    triangles: tuple,
    target_body: adsk.fusion.BRepBody,
    depth_cm: float,
    name: str,
) -> None:
    sk = comp.sketches.add(face)
    sk.name = name
    lines = sk.sketchCurves.sketchLines
    for (x0, y0), (x1, y1), (x2, y2) in triangles:
        p0 = adsk.core.Point3D.create(x0, y0, 0.0)
        p1 = adsk.core.Point3D.create(x1, y1, 0.0)
        p2 = adsk.core.Point3D.create(x2, y2, 0.0)
        lines.addByTwoPoints(p0, p1)
        lines.addByTwoPoints(p1, p2)
        lines.addByTwoPoints(p2, p0)
    _cut_sketch_on_face(comp, face, sk, target_body, -depth_cm)


def _cut_lap_rect(
    comp: adsk.fusion.Component,
    plane,
    rect: attach_planner.Rect2D,
    target_body: adsk.fusion.BRepBody,
    depth_cm: float,
    name: str,
) -> None:
    sk = comp.sketches.add(plane)
    sk.name = name
    u0, v0, u1, v1 = rect
    sk.sketchCurves.sketchLines.addTwoPointRectangle(
        adsk.core.Point3D.create(u0, v0, 0.0),
        adsk.core.Point3D.create(u1, v1, 0.0),
    )
    _cut_sketch_on_face(comp, plane, sk, target_body, depth_cm)


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

    ref_sketch = existing_comp.sketches.add(face)
    bounds = _face_bounds_2d(ref_sketch, face)
    p0 = ref_sketch.modelToSketchSpace(edge.startVertex.geometry)
    p1 = ref_sketch.modelToSketchSpace(edge.endVertex.geometry)
    ref_sketch.deleteMe()

    plan = attach_planner.compute_attach_plan(
        face_bounds=bounds,
        edge_p0=(p0.x, p0.y),
        edge_p1=(p1.x, p1.y),
        lumber=lumber,
        length_cm=length_cm,
        on_edge=on_edge,
        joint_type=joint_type,
        length_mode=length_mode,
        flip_along_edge=flip_dir,
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

    # Sketch and extrude the new board on the target face
    sk = target_comp.sketches.add(face)
    sk.name = f"{lumber.nominal} Attached"
    u0, v0, u1, v1 = plan.new_board_rect
    sk.sketchCurves.sketchLines.addTwoPointRectangle(
        adsk.core.Point3D.create(u0, v0, 0.0),
        adsk.core.Point3D.create(u1, v1, 0.0),
    )
    if sk.profiles.count == 0:
        return
    extrudes = target_comp.features.extrudeFeatures
    ext_in = extrudes.createInput(
        sk.profiles.item(0), adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    )
    ext_in.setDistanceExtent(
        False, adsk.core.ValueInput.createByReal(-plan.new_board_height_cm)
    )
    feat = extrudes.add(ext_in)
    new_body = feat.bodies.item(0)
    new_body.name = board_name

    if plan.existing_miter_tri and existing_body:
        _cut_triangles(
            existing_comp,
            face,
            plan.existing_miter_tri,
            existing_body,
            plan.new_board_height_cm,
            "Miter Existing",
        )
    if plan.new_miter_tri:
        _cut_triangles(
            target_comp,
            face,
            plan.new_miter_tri,
            new_body,
            plan.new_board_height_cm,
            "Miter New",
        )
    if plan.lap_rect:
        lap_depth = plan.new_board_height_cm / 2.0
        if existing_body:
            _cut_lap_rect(
                existing_comp,
                face,
                plan.lap_rect[0],
                existing_body,
                -lap_depth,
                "Half-Lap Existing",
            )
        p_in = target_comp.constructionPlanes.createInput()
        p_in.setByOffset(
            face, adsk.core.ValueInput.createByReal(-plan.new_board_height_cm)
        )
        bottom_plane = target_comp.constructionPlanes.add(p_in)
        _cut_lap_rect(
            target_comp,
            bottom_plane,
            plan.lap_rect[0],
            new_body,
            lap_depth,
            "Half-Lap New",
        )

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
                "attachFace", "Target Face", "Select face on the existing board"
            )
            face_sel.addSelectionFilter("PlanarFaces")
            face_sel.setSelectionLimits(1, 1)

            edge_sel = inputs.addSelectionInput(
                "attachEdge", "Attach Edge", "Select edge where the new board joins"
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

            inputs.addBoolValueInput(
                "attachOnEdge", "New Board On Edge", True, "", True
            )
            inputs.addBoolValueInput(
                "attachFlip", "Flip Along Edge", True, "", False
            )
            inputs.addBoolValueInput(
                "attachNewComp", "Create New Component", True, "", True
            )

            on_exec = AttachExecuteHandler()
            cmd.execute.add(on_exec)
            self._handlers.append(on_exec)

            on_prev = AttachPreviewHandler()
            cmd.executePreview.add(on_prev)
            self._handlers.append(on_prev)

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

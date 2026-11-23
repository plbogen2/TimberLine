"""Autodesk Fusion command: Convert Corner (convert 2 overlapping boards into a joint)."""

import os
import traceback

import adsk.core
import adsk.fusion

import corner_planner
import fusion_ui
import operation_log

CORNER_CMD_ID = "TimberLineCornerCmd"
CORNER_CMD_NAME = "Convert Corner"
CORNER_CMD_DESC = (
    "Convert an existing corner between two boards into a Half-Lap, 45° Miter, "
    "Bridle, or trimmed Butt joint."
)


def _body_box_3d(body: adsk.fusion.BRepBody) -> corner_planner.Box3D:
    bb = body.boundingBox
    return (
        bb.minPoint.x,
        bb.minPoint.y,
        bb.minPoint.z,
        bb.maxPoint.x,
        bb.maxPoint.y,
        bb.maxPoint.z,
    )


def _cut_box_3d(
    comp: adsk.fusion.Component,
    target_body: adsk.fusion.BRepBody,
    box: corner_planner.Box3D,
    name: str,
) -> None:
    x0, y0, z0, x1, y1, z1 = box
    xy = comp.xYConstructionPlane
    if abs(z0) > 1e-6:
        p_in = comp.constructionPlanes.createInput()
        p_in.setByOffset(xy, adsk.core.ValueInput.createByReal(z0))
        plane = comp.constructionPlanes.add(p_in)
    else:
        plane = xy

    sk = comp.sketches.add(plane)
    sk.name = name
    sk.sketchCurves.sketchLines.addTwoPointRectangle(
        adsk.core.Point3D.create(x0, y0, 0.0),
        adsk.core.Point3D.create(x1, y1, 0.0),
    )
    if sk.profiles.count == 0:
        return
    ext_in = comp.features.extrudeFeatures.createInput(
        sk.profiles.item(0), adsk.fusion.FeatureOperations.CutFeatureOperation
    )
    ext_in.setDistanceExtent(False, adsk.core.ValueInput.createByReal(z1 - z0))
    ext_in.participantBodies = [target_body]
    comp.features.extrudeFeatures.add(ext_in)


def _cut_miter_prism(
    comp: adsk.fusion.Component,
    target_body: adsk.fusion.BRepBody,
    prism: corner_planner.MiterPrismSpec,
    name: str,
) -> None:
    base_planes = (
        comp.yZConstructionPlane,
        comp.xZConstructionPlane,
        comp.xYConstructionPlane,
    )
    base_plane = base_planes[prism.extrude_axis]
    mid_ext = 0.5 * (prism.ext_min + prism.ext_max)
    half_span = 0.5 * (prism.ext_max - prism.ext_min) + 0.05

    probe_sk = comp.sketches.add(base_plane)
    p_orig = probe_sk.sketchToModelSpace(adsk.core.Point3D.create(0.0, 0.0, 0.0))
    p_z = probe_sk.sketchToModelSpace(adsk.core.Point3D.create(0.0, 0.0, 1.0))
    probe_sk.deleteMe()
    normal_comps = (p_z.x - p_orig.x, p_z.y - p_orig.y, p_z.z - p_orig.z)
    sign = 1.0 if normal_comps[prism.extrude_axis] >= 0 else -1.0

    p_in = comp.constructionPlanes.createInput()
    p_in.setByOffset(base_plane, adsk.core.ValueInput.createByReal(sign * mid_ext))
    mid_plane = comp.constructionPlanes.add(p_in)

    sk = comp.sketches.add(mid_plane)
    sk.name = name
    pts = []
    for u_val, v_val in prism.tri_2d:
        coords = [0.0, 0.0, 0.0]
        coords[prism.u_axis] = u_val
        coords[prism.v_axis] = v_val
        coords[prism.extrude_axis] = mid_ext
        p2 = sk.modelToSketchSpace(
            adsk.core.Point3D.create(coords[0], coords[1], coords[2])
        )
        pts.append(adsk.core.Point3D.create(p2.x, p2.y, 0.0))

    lines = sk.sketchCurves.sketchLines
    for i in range(3):
        lines.addByTwoPoints(pts[i], pts[(i + 1) % 3])

    if sk.profiles.count == 0:
        return
    ext_in = comp.features.extrudeFeatures.createInput(
        sk.profiles.item(0), adsk.fusion.FeatureOperations.CutFeatureOperation
    )
    ext_in.setDistanceExtent(True, adsk.core.ValueInput.createByReal(half_span))
    ext_in.participantBodies = [target_body]
    comp.features.extrudeFeatures.add(ext_in)


def _boolean_trim(
    design: adsk.fusion.Design,
    target_body: adsk.fusion.BRepBody,
    tool_body: adsk.fusion.BRepBody,
) -> None:
    comp = target_body.parentComponent or design.activeComponent
    tools = adsk.core.ObjectCollection.create()
    tools.add(tool_body)
    comb = comp.features.combineFeatures
    comb_in = comb.createInput(target_body, tools)
    comb_in.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
    comb_in.isKeepToolBodies = True
    comb.add(comb_in)


def _execute_convert_corner(
    inputs: adsk.core.CommandInputs, record_log: bool = True
) -> None:
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if not design:
        return

    sel_a = adsk.core.SelectionCommandInput.cast(inputs.itemById("cornerBoardA"))
    sel_b = adsk.core.SelectionCommandInput.cast(inputs.itemById("cornerBoardB"))
    if not sel_a or not sel_b or sel_a.selectionCount == 0 or sel_b.selectionCount == 0:
        return

    body_a = adsk.fusion.BRepBody.cast(sel_a.selection(0).entity)
    body_b = adsk.fusion.BRepBody.cast(sel_b.selection(0).entity)
    if body_a == body_b:
        return

    jt = adsk.core.DropDownCommandInput.cast(
        inputs.itemById("cornerJointType")
    ).selectedItem.name
    axis_choice = adsk.core.DropDownCommandInput.cast(
        inputs.itemById("cornerAxis")
    ).selectedItem.name

    plan = corner_planner.compute_corner_cuts(
        _body_box_3d(body_a), _body_box_3d(body_b), jt, axis_choice
    )

    if plan.use_boolean_trim_a:
        _boolean_trim(design, body_a, body_b)
    elif plan.use_boolean_trim_b:
        _boolean_trim(design, body_b, body_a)
    else:
        comp_a = body_a.parentComponent or design.activeComponent
        comp_b = body_b.parentComponent or design.activeComponent
        for idx, box in enumerate(plan.a_boxes):
            _cut_box_3d(comp_a, body_a, box, f"{jt} A-{idx + 1}")
        for idx, box in enumerate(plan.b_boxes):
            _cut_box_3d(comp_b, body_b, box, f"{jt} B-{idx + 1}")
        if plan.a_miter:
            _cut_miter_prism(comp_a, body_a, plan.a_miter, "Miter A")
        if plan.b_miter:
            _cut_miter_prism(comp_b, body_b, plan.b_miter, "Miter B")

    if record_log:
        operation_log.SESSION_LOG.record(
            "Convert Corner", f"{body_a.name} + {body_b.name} [{jt}]"
        )


class CornerExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args: adsk.core.CommandEventArgs):
        try:
            _execute_convert_corner(args.command.commandInputs, record_log=True)
        except Exception:
            ui = adsk.core.Application.get().userInterface
            if ui:
                ui.messageBox(f"Failed to convert corner:\n{traceback.format_exc()}")


class CornerPreviewHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args: adsk.core.CommandEventArgs):
        try:
            _execute_convert_corner(args.command.commandInputs, record_log=False)
            args.isValidResult = True
        except Exception:
            pass


class CornerValidateHandler(adsk.core.ValidateInputsEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args: adsk.core.ValidateInputsEventArgs):
        try:
            inputs = args.inputs
            sel_a = adsk.core.SelectionCommandInput.cast(inputs.itemById("cornerBoardA"))
            sel_b = adsk.core.SelectionCommandInput.cast(inputs.itemById("cornerBoardB"))
            if not sel_a or not sel_b or sel_a.selectionCount == 0 or sel_b.selectionCount == 0:
                args.areInputsValid = False
                return
            body_a = sel_a.selection(0).entity
            body_b = sel_b.selection(0).entity
            if body_a == body_b:
                args.areInputsValid = False
                return
            ov = corner_planner.compute_overlap_box(
                _body_box_3d(body_a), _body_box_3d(body_b)
            )
            args.areInputsValid = ov is not None
        except Exception:
            args.areInputsValid = False


class CornerCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self, handlers: list):
        super().__init__()
        self._handlers = handlers

    def notify(self, args: adsk.core.CommandCreatedEventArgs):
        try:
            cmd = args.command
            inputs = cmd.commandInputs

            sel_a = inputs.addSelectionInput(
                "cornerBoardA", "Board A", "Select first board at the corner"
            )
            sel_a.addSelectionFilter("Bodies")
            sel_a.setSelectionLimits(1, 1)

            sel_b = inputs.addSelectionInput(
                "cornerBoardB", "Board B", "Select second overlapping board"
            )
            sel_b.addSelectionFilter("Bodies")
            sel_b.setSelectionLimits(1, 1)

            jt_dd = inputs.addDropDownCommandInput(
                "cornerJointType",
                "Corner Joint",
                adsk.core.DropDownStyles.TextListDropDownStyle,
            )
            for idx, jt in enumerate(corner_planner.CORNER_CONVERT_TYPES):
                jt_dd.listItems.add(jt, idx == 0, "")

            ax_dd = inputs.addDropDownCommandInput(
                "cornerAxis",
                "Lap / Miter Axis",
                adsk.core.DropDownStyles.TextListDropDownStyle,
            )
            for idx, ax in enumerate(corner_planner.AXIS_CHOICES):
                ax_dd.listItems.add(ax, idx == 0, "")

            on_exec = CornerExecuteHandler()
            cmd.execute.add(on_exec)
            self._handlers.append(on_exec)

            on_prev = CornerPreviewHandler()
            cmd.executePreview.add(on_prev)
            self._handlers.append(on_prev)

            on_val = CornerValidateHandler()
            cmd.validateInputs.add(on_val)
            self._handlers.append(on_val)
        except Exception:
            ui = adsk.core.Application.get().userInterface
            if ui:
                ui.messageBox(
                    f"Failed to initialize Convert Corner dialog:\n{traceback.format_exc()}"
                )


def register_corner_command(
    ui: adsk.core.UserInterface,
    panel_id: str,
    addin_dir: str,
    handlers: list,
) -> None:
    fusion_ui.register_panel_command(
        ui=ui,
        panel_id=panel_id,
        cmd_id=CORNER_CMD_ID,
        cmd_name=CORNER_CMD_NAME,
        cmd_desc=CORNER_CMD_DESC,
        resource_dir=os.path.join(addin_dir, "resources", "CornerIcon"),
        created_handler_factory=lambda: CornerCommandCreatedHandler(handlers),
        handlers=handlers,
    )


def unregister_corner_command(ui: adsk.core.UserInterface, panel_id: str) -> None:
    fusion_ui.unregister_panel_command(ui, panel_id, CORNER_CMD_ID)

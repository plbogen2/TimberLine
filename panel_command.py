"""Autodesk Fusion command: Fill Panel (fill space between boards + auto dado/rabbet)."""

import os
import traceback

import adsk.core
import adsk.fusion

import fusion_ui
import lumber_catalog
import operation_log
import panel_planner

PANEL_CMD_ID = "TimberLinePanelCmd"
PANEL_CMD_NAME = "Fill Panel"
PANEL_CMD_DESC = (
    "Fill an opening between 2 to 4 boards with a sheet panel and automatically "
    "cut matching dados or rabbets into the surrounding boards."
)


def _body_box_3d(body: adsk.fusion.BRepBody) -> panel_planner.Box3D:
    bb = body.boundingBox
    return (
        bb.minPoint.x,
        bb.minPoint.y,
        bb.minPoint.z,
        bb.maxPoint.x,
        bb.maxPoint.y,
        bb.maxPoint.z,
    )


def _create_panel_body(
    comp: adsk.fusion.Component,
    plan: panel_planner.PanelPlan,
    name: str,
) -> adsk.fusion.BRepBody:
    x0, y0, z0, x1, y1, z1 = plan.panel_box
    n_ax = plan.normal_axis
    base_planes = (
        comp.yZConstructionPlane,
        comp.xZConstructionPlane,
        comp.xYConstructionPlane,
    )
    base_plane = base_planes[n_ax]
    w_lo = plan.panel_box[n_ax]
    w_hi = plan.panel_box[n_ax + 3]

    probe_sk = comp.sketches.add(base_plane)
    p_orig = probe_sk.sketchToModelSpace(adsk.core.Point3D.create(0.0, 0.0, 0.0))
    p_z = probe_sk.sketchToModelSpace(adsk.core.Point3D.create(0.0, 0.0, 1.0))
    probe_sk.deleteMe()
    normal_comps = (p_z.x - p_orig.x, p_z.y - p_orig.y, p_z.z - p_orig.z)
    sign = 1.0 if normal_comps[n_ax] >= 0 else -1.0

    if abs(w_lo) > 1e-6:
        p_in = comp.constructionPlanes.createInput()
        p_in.setByOffset(base_plane, adsk.core.ValueInput.createByReal(sign * w_lo))
        plane = comp.constructionPlanes.add(p_in)
    else:
        plane = base_plane

    sk = comp.sketches.add(plane)
    sk.name = f"{name} Profile"
    span_axes = [ax for ax in (0, 1, 2) if ax != n_ax]
    u_ax, v_ax = span_axes[0], span_axes[1]
    pts = []
    for u_val, v_val in plan.polygon_uv:
        coords = [0.0, 0.0, 0.0]
        coords[u_ax] = u_val
        coords[v_ax] = v_val
        coords[n_ax] = w_lo
        p2 = sk.modelToSketchSpace(
            adsk.core.Point3D.create(coords[0], coords[1], coords[2])
        )
        pts.append(adsk.core.Point3D.create(p2.x, p2.y, 0.0))
    lines = sk.sketchCurves.sketchLines
    for i in range(len(pts)):
        lines.addByTwoPoints(pts[i], pts[(i + 1) % len(pts)])

    ext_in = comp.features.extrudeFeatures.createInput(
        sk.profiles.item(0), adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    )
    ext_in.setDistanceExtent(
        False, adsk.core.ValueInput.createByReal(sign * (w_hi - w_lo))
    )
    feat = comp.features.extrudeFeatures.add(ext_in)
    body = feat.bodies.item(0)
    body.name = name
    return body


def _cut_panel_into_board(
    design: adsk.fusion.Design,
    board: adsk.fusion.BRepBody,
    panel_body: adsk.fusion.BRepBody,
) -> None:
    comp = board.parentComponent or design.activeComponent
    tools = adsk.core.ObjectCollection.create()
    tools.add(panel_body)
    comb = comp.features.combineFeatures
    comb_in = comb.createInput(board, tools)
    comb_in.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
    comb_in.isKeepToolBodies = True
    try:
        comb.add(comb_in)
    except RuntimeError:
        pass


def _execute_fill_panel(
    inputs: adsk.core.CommandInputs, record_log: bool = True
) -> None:
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if not design:
        return

    sel = adsk.core.SelectionCommandInput.cast(inputs.itemById("panelBoards"))
    if not sel or sel.selectionCount < 2:
        return

    boards = [adsk.fusion.BRepBody.cast(sel.selection(i).entity) for i in range(sel.selectionCount)]
    boxes = [_body_box_3d(b) for b in boards]

    sheet_label = adsk.core.DropDownCommandInput.cast(
        inputs.itemById("panelSheetType")
    ).selectedItem.name
    sheet = lumber_catalog.SHEET_BY_LABEL[sheet_label]
    depth_cm = adsk.core.ValueCommandInput.cast(inputs.itemById("panelDepth")).value
    plane_choice = adsk.core.DropDownCommandInput.cast(
        inputs.itemById("panelPlane")
    ).selectedItem.name
    alignment = adsk.core.DropDownCommandInput.cast(
        inputs.itemById("panelAlignment")
    ).selectedItem.name

    plan = panel_planner.compute_panel_plan(
        boxes, sheet, depth_cm=depth_cm, plane_choice=plane_choice, alignment=alignment
    )
    panel_name = f"{sheet.name} - {plan.width_in:g}x{plan.length_in:g} in"
    comp = boards[0].parentComponent or design.activeComponent
    panel_body = _create_panel_body(comp, plan, panel_name)

    if depth_cm > 0:
        for b in boards:
            _cut_panel_into_board(design, b, panel_body)

    if record_log:
        operation_log.SESSION_LOG.record("Fill Panel", f"{panel_name} [{alignment}]")


class PanelExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args: adsk.core.CommandEventArgs):
        try:
            _execute_fill_panel(args.command.commandInputs, record_log=True)
        except Exception:
            ui = adsk.core.Application.get().userInterface
            if ui:
                ui.messageBox(f"Failed to fill panel:\n{traceback.format_exc()}")


class PanelPreviewHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args: adsk.core.CommandEventArgs):
        try:
            _execute_fill_panel(args.command.commandInputs, record_log=False)
            args.isValidResult = True
        except Exception:
            pass


class PanelValidateHandler(adsk.core.ValidateInputsEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args: adsk.core.ValidateInputsEventArgs):
        try:
            sel = adsk.core.SelectionCommandInput.cast(
                args.inputs.itemById("panelBoards")
            )
            args.areInputsValid = bool(sel and sel.selectionCount >= 2)
        except Exception:
            args.areInputsValid = False


class PanelCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self, handlers: list):
        super().__init__()
        self._handlers = handlers

    def notify(self, args: adsk.core.CommandCreatedEventArgs):
        try:
            cmd = args.command
            inputs = cmd.commandInputs

            sel = inputs.addSelectionInput(
                "panelBoards",
                "Surrounding Boards",
                "Select 2 or more boards framing the space to fill (e.g. 4 for box, 6 for hexagon)",
            )
            sel.addSelectionFilter("Bodies")
            sel.setSelectionLimits(2, 0)

            sheet_dd = inputs.addDropDownCommandInput(
                "panelSheetType",
                "Panel Material",
                adsk.core.DropDownStyles.TextListDropDownStyle,
            )
            for idx, item in enumerate(lumber_catalog.SHEET_THICKNESSES):
                is_default = item.name == '1/4" Plywood'
                sheet_dd.listItems.add(item.label, is_default, "")

            plane_dd = inputs.addDropDownCommandInput(
                "panelPlane",
                "Panel Plane",
                adsk.core.DropDownStyles.TextListDropDownStyle,
            )
            for idx, p in enumerate(panel_planner.PANEL_PLANES):
                plane_dd.listItems.add(p, idx == 0, "")

            align_dd = inputs.addDropDownCommandInput(
                "panelAlignment",
                "Joint / Alignment",
                adsk.core.DropDownStyles.TextListDropDownStyle,
            )
            for idx, a in enumerate(panel_planner.PANEL_ALIGNMENTS):
                align_dd.listItems.add(a, idx == 0, "")

            inputs.addValueInput(
                "panelDepth",
                "Dado / Rabbet Depth",
                "in",
                adsk.core.ValueInput.createByString("0.25 in"),
            )

            on_exec = PanelExecuteHandler()
            cmd.execute.add(on_exec)
            self._handlers.append(on_exec)

            on_prev = PanelPreviewHandler()
            cmd.executePreview.add(on_prev)
            self._handlers.append(on_prev)

            on_val = PanelValidateHandler()
            cmd.validateInputs.add(on_val)
            self._handlers.append(on_val)
        except Exception:
            ui = adsk.core.Application.get().userInterface
            if ui:
                ui.messageBox(
                    f"Failed to initialize Fill Panel dialog:\n{traceback.format_exc()}"
                )


def register_panel_command_ui(
    ui: adsk.core.UserInterface,
    panel_id: str,
    addin_dir: str,
    handlers: list,
) -> None:
    fusion_ui.register_panel_command(
        ui=ui,
        panel_id=panel_id,
        cmd_id=PANEL_CMD_ID,
        cmd_name=PANEL_CMD_NAME,
        cmd_desc=PANEL_CMD_DESC,
        resource_dir=os.path.join(addin_dir, "resources", "PanelIcon"),
        created_handler_factory=lambda: PanelCommandCreatedHandler(handlers),
        handlers=handlers,
    )


def unregister_panel_command_ui(ui: adsk.core.UserInterface, panel_id: str) -> None:
    fusion_ui.unregister_panel_command(ui, panel_id, PANEL_CMD_ID)

"""Autodesk Fusion command: Add Joinery (delegates to joinery/ technique modules)."""

import os
import traceback
from typing import Dict, List, Tuple

import adsk.core
import adsk.fusion

import fusion_ui
import joinery
import joinery_tools
import operation_log
from joinery import base as joinery_base

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
    "Bridle (Open Mortise)",
    "Tongue (Edge)",
    "Groove / Spline",
    "Box Joint (Even Slots)",
    "Box Joint (Odd Slots)",
    "Dovetail (Tails)",
    "Dovetail (Pins)",
    "Biscuit Slot",
    "Pocket Holes (15°)",
    "Dowel Holes",
]

_EDGE_REQUIRED_JOINTS = set(joinery.EDGE_JOINTS.keys())
_BOARD_REF_JOINTS = {"Rabbet", "Dado / Groove", "Half-Lap"}
_TWO_BOARD_JOINTS = set(joinery.TWO_BOARD_JOINTS.keys())

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
    "Bridle (Open Mortise)": [
        ("jointWidth", "Slot Width", "0.5 in"),
        ("jointDepth", "Slot Depth", "1.5 in"),
    ],
    "Tongue (Edge)": [
        ("jointWidth", "Tongue Thickness", "0.25 in"),
        ("jointDepth", "Tongue Length", "0.375 in"),
    ],
    "Groove / Spline": [
        ("jointWidth", "Groove Width", "0.25 in"),
        ("jointDepth", "Groove Depth", "0.375 in"),
    ],
    "Box Joint (Even Slots)": [
        ("holeCount", "", ""),
        ("jointDepth", "Finger Depth", "0.75 in"),
    ],
    "Box Joint (Odd Slots)": [
        ("holeCount", "", ""),
        ("jointDepth", "Finger Depth", "0.75 in"),
    ],
    "Dovetail (Tails)": [
        ("holeCount", "", ""),
        ("jointDepth", "Board Thickness", "0.75 in"),
    ],
    "Dovetail (Pins)": [
        ("holeCount", "", ""),
        ("jointDepth", "Board Thickness", "0.75 in"),
    ],
    "Biscuit Slot": [
        ("holeCount", "", ""),
        ("holeInset", "", ""),
        ("jointWidth", "Slot Length", "2.25 in"),
        ("holeDia", "Slot Thickness", "0.157 in"),
        ("jointDepth", "Slot Depth", "0.472 in"),
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


def _project_body_bounds_2d(
    sketch: adsk.fusion.Sketch, body
) -> joinery_tools.Rect2D:
    bb = body.boundingBox
    us, vs = [], []
    for x in (bb.minPoint.x, bb.maxPoint.x):
        for y in (bb.minPoint.y, bb.maxPoint.y):
            for z in (bb.minPoint.z, bb.maxPoint.z):
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
    comp = joinery_base.target_component_for_face(design, face)

    sketch = comp.sketches.add(face)
    bounds = joinery_base.face_bounds_2d(sketch, face)
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


def _execute_joinery(inputs: adsk.core.CommandInputs) -> None:
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if not design:
        return

    jt = adsk.core.DropDownCommandInput.cast(
        inputs.itemById("jointType")
    ).selectedItem.name

    if jt in joinery.TWO_BOARD_JOINTS:
        joinery.TWO_BOARD_JOINTS[jt](design, inputs)
        return

    face_sel = adsk.core.SelectionCommandInput.cast(inputs.itemById("jointFace"))
    if not face_sel or face_sel.selectionCount == 0:
        return
    face = adsk.fusion.BRepFace.cast(face_sel.selection(0).entity)
    comp = joinery_base.target_component_for_face(design, face)

    if jt in joinery.EDGE_JOINTS:
        edge_sel = adsk.core.SelectionCommandInput.cast(inputs.itemById("jointEdge"))
        if not edge_sel or edge_sel.selectionCount == 0:
            return
        edge = adsk.fusion.BRepEdge.cast(edge_sel.selection(0).entity)
        joinery.EDGE_JOINTS[jt](comp, face, edge, inputs)
        return

    if jt in joinery.FACE_JOINTS:
        joinery.FACE_JOINTS[jt](comp, face, inputs)


class JoineryExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args: adsk.core.CommandEventArgs):
        try:
            _execute_joinery(args.command.commandInputs)
            jt = adsk.core.DropDownCommandInput.cast(
                args.command.commandInputs.itemById("jointType")
            ).selectedItem.name
            operation_log.SESSION_LOG.record("Add Joinery", jt)
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

            face_sel = adsk.core.SelectionCommandInput.cast(inputs.itemById("jointFace"))
            if face_sel:
                face_sel.isVisible = jt not in _TWO_BOARD_JOINTS

            edge_sel = adsk.core.SelectionCommandInput.cast(inputs.itemById("jointEdge"))
            edge_sel.isVisible = jt in _EDGE_REQUIRED_JOINTS

            tgt_sel = adsk.core.SelectionCommandInput.cast(inputs.itemById("targetBoard"))
            if tgt_sel:
                tgt_sel.isVisible = jt in _TWO_BOARD_JOINTS

            ref_sel = adsk.core.SelectionCommandInput.cast(inputs.itemById("refBoard"))
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
                tgt_sel = adsk.core.SelectionCommandInput.cast(inputs.itemById("targetBoard"))
                ref_sel = adsk.core.SelectionCommandInput.cast(inputs.itemById("refBoard"))
                args.areInputsValid = bool(
                    tgt_sel and ref_sel and tgt_sel.selectionCount > 0 and ref_sel.selectionCount > 0
                )
                return

            face_sel = adsk.core.SelectionCommandInput.cast(inputs.itemById("jointFace"))
            if not face_sel or face_sel.selectionCount == 0:
                args.areInputsValid = False
                return
            if jt in _EDGE_REQUIRED_JOINTS:
                edge_sel = adsk.core.SelectionCommandInput.cast(inputs.itemById("jointEdge"))
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
                "jointType", "Joint Type", adsk.core.DropDownStyles.TextListDropDownStyle
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
                "jointOffset", "Offset from Edge", "in", adsk.core.ValueInput.createByString("6 in")
            ).isVisible = False
            inputs.addValueInput(
                "jointWidth", "Width", "in", adsk.core.ValueInput.createByString("0.5 in")
            )
            inputs.addValueInput(
                "jointDepth", "Depth", "in", adsk.core.ValueInput.createByString("0.375 in")
            )
            inputs.addValueInput(
                "tenonThick", "Tenon Thickness", "in", adsk.core.ValueInput.createByString("0.5 in")
            ).isVisible = False
            inputs.addValueInput(
                "tenonWidth", "Tenon Width", "in", adsk.core.ValueInput.createByString("2.5 in")
            ).isVisible = False
            inputs.addValueInput(
                "tenonLength", "Tenon Length", "in", adsk.core.ValueInput.createByString("1.5 in")
            ).isVisible = False
            inputs.addIntegerSpinnerCommandInput(
                "holeCount", "Hole Count", 1, 12, 1, 2
            ).isVisible = False
            inputs.addValueInput(
                "holeDia", "Pocket Dia", "in", adsk.core.ValueInput.createByString("0.375 in")
            ).isVisible = False
            inputs.addValueInput(
                "pilotDia", "Pilot Dia", "in", adsk.core.ValueInput.createByString("0.15625 in")
            ).isVisible = False
            inputs.addValueInput(
                "holeInset", "Edge Inset", "in", adsk.core.ValueInput.createByString("0.75 in")
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

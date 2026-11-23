"""Autodesk Fusion command: Cut List & Kerf Planner."""

import os
import traceback
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import adsk.core
import adsk.fusion

import kerf_planner
import lumber_catalog

KERF_CMD_ID = "TimberLineKerfCmd"
KERF_CMD_NAME = "Cut List & Kerf"
KERF_CMD_DESC = (
    "Analyze lumber and sheet stock bodies in the design and plan cuts "
    "accounting for saw blade kerf."
)

_TOL_IN = 0.03


def _match_lumber(d0_in: float, d1_in: float) -> Optional[lumber_catalog.LumberSize]:
    for item in lumber_catalog.LUMBER_SIZES:
        if (
            abs(d0_in - item.thickness_in) <= _TOL_IN
            and abs(d1_in - item.width_in) <= _TOL_IN
        ):
            return item
    return None


def _match_sheet(d0_in: float) -> Optional[lumber_catalog.SheetThickness]:
    for item in lumber_catalog.SHEET_THICKNESSES:
        if abs(d0_in - item.thickness_in) <= 0.015:
            return item
    return None


def _collect_design_cuts(design: adsk.fusion.Design) -> Tuple[
    Dict[str, List[kerf_planner.LinearCut]],
    Dict[str, Tuple[lumber_catalog.SheetThickness, List[kerf_planner.SheetCut]]],
]:
    linear: Dict[str, List[kerf_planner.LinearCut]] = defaultdict(list)
    sheets: Dict[str, Tuple[lumber_catalog.SheetThickness, List[kerf_planner.SheetCut]]] = {}

    root = design.rootComponent
    bodies = list(root.bRepBodies)
    for occ in root.allOccurrences:
        if occ.isLightBulbOn:
            for b in occ.bRepBodies:
                bodies.append(b)

    for body in bodies:
        if not body.isVisible:
            continue
        bb = body.boundingBox
        dims_in = sorted([
            lumber_catalog.cm_to_inches(bb.maxPoint.x - bb.minPoint.x),
            lumber_catalog.cm_to_inches(bb.maxPoint.y - bb.minPoint.y),
            lumber_catalog.cm_to_inches(bb.maxPoint.z - bb.minPoint.z),
        ])
        d0, d1, d2 = dims_in
        lumber = _match_lumber(d0, d1)
        if lumber is not None:
            linear[lumber.nominal].append(
                kerf_planner.LinearCut(label=body.name, length_in=d2)
            )
            continue

        sheet = _match_sheet(d0)
        if sheet is not None and d1 > 1.0:
            if sheet.name not in sheets:
                sheets[sheet.name] = (sheet, [])
            sheets[sheet.name][1].append(
                kerf_planner.SheetCut(label=body.name, width_in=d1, length_in=d2)
            )

    return linear, sheets


class KerfExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args: adsk.core.CommandEventArgs):
        try:
            app = adsk.core.Application.get()
            ui = app.userInterface
            design = adsk.fusion.Design.cast(app.activeProduct)
            if not design:
                return

            inputs = args.command.commandInputs
            kerf_in = lumber_catalog.cm_to_inches(
                adsk.core.ValueCommandInput.cast(inputs.itemById("bladeKerf")).value
            )
            stock_len_in = lumber_catalog.cm_to_inches(
                adsk.core.ValueCommandInput.cast(inputs.itemById("stockLength")).value
            )
            trim_in = lumber_catalog.cm_to_inches(
                adsk.core.ValueCommandInput.cast(inputs.itemById("endTrim")).value
            )
            export_chk = adsk.core.BoolValueCommandInput.cast(
                inputs.itemById("exportTxt")
            ).value

            linear_raw, sheets_raw = _collect_design_cuts(design)
            linear_packed = {
                name: kerf_planner.pack_linear_cuts(
                    cuts, stock_len_in, kerf_in=kerf_in, trim_in=trim_in
                )
                for name, cuts in sorted(linear_raw.items())
            }
            sheets_packed = {
                name: kerf_planner.pack_sheet_cuts(
                    cuts,
                    sheet_obj.max_width_in,
                    sheet_obj.max_length_in,
                    kerf_in=kerf_in,
                )
                for name, (sheet_obj, cuts) in sorted(sheets_raw.items())
            }

            report = kerf_planner.format_cut_plan_report(
                linear_packed, sheets_packed, kerf_in
            )

            if export_chk:
                dlg = ui.createFileDialog()
                dlg.title = "Save Cut List & Kerf Plan"
                dlg.filter = "Text files (*.txt);;All files (*.*)"
                dlg.initialFilename = "cut_list_kerf_plan.txt"
                if dlg.showSave() == adsk.core.DialogResults.DialogOK:
                    with open(dlg.filename, "w", encoding="utf-8") as f:
                        f.write(report + "\n")

            ui.messageBox(report, "Cut List & Kerf Plan")
        except Exception:
            ui = adsk.core.Application.get().userInterface
            if ui:
                ui.messageBox(f"Failed to generate cut list:\n{traceback.format_exc()}")


class KerfCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self, handlers: list):
        super().__init__()
        self._handlers = handlers

    def notify(self, args: adsk.core.CommandCreatedEventArgs):
        try:
            cmd = args.command
            inputs = cmd.commandInputs

            inputs.addValueInput(
                "bladeKerf",
                "Saw Blade Kerf",
                "in",
                adsk.core.ValueInput.createByString("0.125 in"),
            )
            inputs.addValueInput(
                "stockLength",
                "Lumber Stock Length",
                "in",
                adsk.core.ValueInput.createByString("96 in"),
            )
            inputs.addValueInput(
                "endTrim",
                "End Trim Allowance",
                "in",
                adsk.core.ValueInput.createByString("0.5 in"),
            )
            inputs.addBoolValueInput(
                "exportTxt", "Save Cut List to .txt File", True, "", False
            )

            on_exec = KerfExecuteHandler()
            cmd.execute.add(on_exec)
            self._handlers.append(on_exec)
        except Exception:
            ui = adsk.core.Application.get().userInterface
            if ui:
                ui.messageBox(
                    f"Failed to initialize Cut List & Kerf dialog:\n{traceback.format_exc()}"
                )


def register_kerf_command(
    ui: adsk.core.UserInterface,
    panel_id: str,
    addin_dir: str,
    handlers: list,
) -> None:
    res_dir = os.path.join(addin_dir, "resources", "KerfIcon")
    resource_arg = res_dir if os.path.isdir(res_dir) else ""
    cmd_def = ui.commandDefinitions.itemById(KERF_CMD_ID)
    if not cmd_def:
        cmd_def = ui.commandDefinitions.addButtonDefinition(
            KERF_CMD_ID, KERF_CMD_NAME, KERF_CMD_DESC, resource_arg
        )
    on_created = KerfCommandCreatedHandler(handlers)
    cmd_def.commandCreated.add(on_created)
    handlers.append(on_created)

    panel = ui.allToolbarPanels.itemById(panel_id)
    if panel and not panel.controls.itemById(KERF_CMD_ID):
        cntrl = panel.controls.addCommand(cmd_def)
        cntrl.isPromotedByDefault = True
        cntrl.isPromoted = True


def unregister_kerf_command(ui: adsk.core.UserInterface, panel_id: str) -> None:
    panel = ui.allToolbarPanels.itemById(panel_id)
    if panel:
        cntrl = panel.controls.itemById(KERF_CMD_ID)
        if cntrl:
            cntrl.deleteMe()
    cmd_def = ui.commandDefinitions.itemById(KERF_CMD_ID)
    if cmd_def:
        cmd_def.deleteMe()

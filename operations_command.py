"""Autodesk Fusion command: List Operations (session log + Fusion design timeline)."""

import os
import traceback
from typing import List, Tuple

import adsk.core
import adsk.fusion

import fusion_ui
import operation_log

OPS_CMD_ID = "TimberLineOpsCmd"
OPS_CMD_NAME = "List Operations"
OPS_CMD_DESC = (
    "List all TimberLine woodworking operations and Fusion design timeline steps."
)


def _read_design_timeline(design: adsk.fusion.Design) -> List[Tuple[str, bool]]:
    items: List[Tuple[str, bool]] = []
    timeline = getattr(design, "timeline", None)
    if not timeline:
        return items
    for i in range(timeline.count):
        item = timeline.item(i)
        name = getattr(item, "name", None) or f"Step {i + 1}"
        suppressed = bool(getattr(item, "isSuppressed", False))
        items.append((name, suppressed))
    return items


class OpsExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args: adsk.core.CommandEventArgs):
        try:
            app = adsk.core.Application.get()
            ui = app.userInterface
            design = adsk.fusion.Design.cast(app.activeProduct)
            timeline_items = _read_design_timeline(design) if design else []
            report = operation_log.SESSION_LOG.format_report(timeline_items)

            inputs = args.command.commandInputs
            export_chk = adsk.core.BoolValueCommandInput.cast(
                inputs.itemById("opsExportTxt")
            )
            if export_chk and export_chk.value:
                dlg = ui.createFileDialog()
                dlg.title = "Save TimberLine Operations Log"
                dlg.filter = "Text files (*.txt);;All files (*.*)"
                dlg.initialFilename = "timberline_operations.txt"
                if dlg.showSave() == adsk.core.DialogResults.DialogOK:
                    with open(dlg.filename, "w", encoding="utf-8") as f:
                        f.write(report + "\n")

            clear_chk = adsk.core.BoolValueCommandInput.cast(
                inputs.itemById("opsClearLog")
            )
            if clear_chk and clear_chk.value:
                operation_log.SESSION_LOG.clear()

            ui.messageBox(report, "TimberLine Operations")
        except Exception:
            ui = adsk.core.Application.get().userInterface
            if ui:
                ui.messageBox(f"Failed to list operations:\n{traceback.format_exc()}")


class OpsCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self, handlers: list):
        super().__init__()
        self._handlers = handlers

    def notify(self, args: adsk.core.CommandCreatedEventArgs):
        try:
            cmd = args.command
            inputs = cmd.commandInputs
            app = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(app.activeProduct)
            timeline_items = _read_design_timeline(design) if design else []
            report = operation_log.SESSION_LOG.format_report(timeline_items)

            inputs.addTextBoxCommandInput(
                "opsSummary", "Operations", report, 12, True
            )
            inputs.addBoolValueInput(
                "opsExportTxt", "Save Operations to .txt File", True, "", False
            )
            inputs.addBoolValueInput(
                "opsClearLog", "Clear Session Log After Viewing", True, "", False
            )

            on_exec = OpsExecuteHandler()
            cmd.execute.add(on_exec)
            self._handlers.append(on_exec)
        except Exception:
            ui = adsk.core.Application.get().userInterface
            if ui:
                ui.messageBox(
                    f"Failed to initialize List Operations dialog:\n{traceback.format_exc()}"
                )


def register_ops_command(
    ui: adsk.core.UserInterface,
    panel_id: str,
    addin_dir: str,
    handlers: list,
) -> None:
    fusion_ui.register_panel_command(
        ui=ui,
        panel_id=panel_id,
        cmd_id=OPS_CMD_ID,
        cmd_name=OPS_CMD_NAME,
        cmd_desc=OPS_CMD_DESC,
        resource_dir=os.path.join(addin_dir, "resources", "OpsIcon"),
        created_handler_factory=lambda: OpsCommandCreatedHandler(handlers),
        handlers=handlers,
    )


def unregister_ops_command(ui: adsk.core.UserInterface, panel_id: str) -> None:
    fusion_ui.unregister_panel_command(ui, panel_id, OPS_CMD_ID)

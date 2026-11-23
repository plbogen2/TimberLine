"""Shared Autodesk Fusion UI registration helpers."""

import os
from typing import Callable, List

import adsk.core


def register_panel_command(
    ui: adsk.core.UserInterface,
    panel_id: str,
    cmd_id: str,
    cmd_name: str,
    cmd_desc: str,
    resource_dir: str,
    created_handler_factory: Callable[[], adsk.core.CommandCreatedEventHandler],
    handlers: List,
) -> None:
    """Register a command definition and add a promoted button to a toolbar panel."""
    resource_arg = resource_dir if os.path.isdir(resource_dir) else ""
    cmd_def = ui.commandDefinitions.itemById(cmd_id)
    if not cmd_def:
        cmd_def = ui.commandDefinitions.addButtonDefinition(
            cmd_id, cmd_name, cmd_desc, resource_arg
        )

    on_created = created_handler_factory()
    cmd_def.commandCreated.add(on_created)
    handlers.append(on_created)

    panel = ui.allToolbarPanels.itemById(panel_id)
    if not panel:
        solid_tab = ui.allToolbarTabs.itemById("SolidTab")
        if solid_tab:
            panel = solid_tab.toolbarPanels.add(
                panel_id, "TimberLine", "SolidCreatePanel", False
            )
    if panel and not panel.controls.itemById(cmd_id):
        cntrl = panel.controls.addCommand(cmd_def)
        cntrl.isPromotedByDefault = True
        cntrl.isPromoted = True


def unregister_panel_command(
    ui: adsk.core.UserInterface,
    panel_id: str,
    cmd_id: str,
) -> None:
    """Remove a command button from a toolbar panel and delete its definition."""
    panel = ui.allToolbarPanels.itemById(panel_id)
    if panel:
        cntrl = panel.controls.itemById(cmd_id)
        if cntrl:
            cntrl.deleteMe()
        if panel.controls.count == 0:
            panel.deleteMe()

    cmd_def = ui.commandDefinitions.itemById(cmd_id)
    if cmd_def:
        cmd_def.deleteMe()

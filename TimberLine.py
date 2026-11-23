"""Autodesk Fusion Add-In: Dimensional Lumber & Sheet Stock.

Lets you create standard dimensional lumber (2x4, 2x6, 1x4, 4x4, 5/4x6, etc.)
and sheet stock (3/4" plywood, 1/2" plywood, MDF, Baltic birch) using nominal
sizes instead of typing actual dimensions like 1.5 x 3.5 or 23/32.
"""

import os
import sys
import traceback

import adsk.core
import adsk.fusion

ADDIN_DIR = os.path.dirname(os.path.realpath(__file__))
if ADDIN_DIR not in sys.path:
    sys.path.insert(0, ADDIN_DIR)

import attach_command  # noqa: E402
import fusion_ui  # noqa: E402
import joinery_command  # noqa: E402
import kerf_command  # noqa: E402
import lumber_catalog  # noqa: E402
import operation_log  # noqa: E402
import operations_command  # noqa: E402

CMD_ID = "TimberLineCreateCmd"
CMD_NAME = "Create Lumber"
CMD_DESCRIPTION = (
    "Create dimensional lumber (2x4, 2x6, 1x4, 4x4) and sheet stock "
    "(plywood, MDF, Baltic birch) using nominal sizes."
)
PANEL_ID = "SolidCreatePanel"
RESOURCE_FOLDER = os.path.join(ADDIN_DIR, "resources", "LumberIcon")

# Keep event handlers alive for the lifetime of the add-in.
_handlers = []


def _populate_sheet_presets(
    preset_dd: adsk.core.DropDownCommandInput,
    sheet: lumber_catalog.SheetThickness,
) -> None:
    preset_dd.listItems.clear()
    for idx, (label, _, _) in enumerate(sheet.presets):
        preset_dd.listItems.add(label, idx == 0, "")
    preset_dd.listItems.add("Custom", False, "")


def _update_sheet_note(inputs: adsk.core.CommandInputs) -> None:
    note_box = adsk.core.TextBoxCommandInput.cast(inputs.itemById("sheetLimitNote"))
    if not note_box:
        return
    sheet_dd = adsk.core.DropDownCommandInput.cast(inputs.itemById("sheetType"))
    width_val = adsk.core.ValueCommandInput.cast(inputs.itemById("sheetWidth"))
    length_val = adsk.core.ValueCommandInput.cast(inputs.itemById("lumberLength"))
    sheet = lumber_catalog.SHEET_BY_LABEL[sheet_dd.selectedItem.name]

    w_in = lumber_catalog.cm_to_inches(width_val.value)
    l_in = lumber_catalog.cm_to_inches(length_val.value)
    if sheet.fits_in_sheet(w_in, l_in):
        note_box.text = sheet.max_size_label
    else:
        note_box.text = f"Exceeds {sheet.max_size_label}"


def _get_inputs_state(inputs: adsk.core.CommandInputs) -> dict:
    stock_dd = adsk.core.DropDownCommandInput.cast(inputs.itemById("stockType"))
    size_dd = adsk.core.DropDownCommandInput.cast(inputs.itemById("lumberSize"))
    sheet_dd = adsk.core.DropDownCommandInput.cast(inputs.itemById("sheetType"))
    width_val = adsk.core.ValueCommandInput.cast(inputs.itemById("sheetWidth"))
    length_val = adsk.core.ValueCommandInput.cast(inputs.itemById("lumberLength"))
    orient_dd = adsk.core.DropDownCommandInput.cast(inputs.itemById("lumberOrient"))
    anchor_dd = adsk.core.DropDownCommandInput.cast(inputs.itemById("lumberAnchor"))
    rotate_chk = adsk.core.BoolValueCommandInput.cast(inputs.itemById("lumberRotate"))
    ease_chk = adsk.core.BoolValueCommandInput.cast(inputs.itemById("lumberEase"))
    comp_chk = adsk.core.BoolValueCommandInput.cast(inputs.itemById("lumberNewComp"))
    plane_sel = adsk.core.SelectionCommandInput.cast(inputs.itemById("lumberPlane"))

    is_sheet = stock_dd.selectedItem.name == "Sheet Stock"
    lumber = lumber_catalog.LUMBER_BY_LABEL[size_dd.selectedItem.name]
    sheet = lumber_catalog.SHEET_BY_LABEL[sheet_dd.selectedItem.name]

    plane_entity = None
    if plane_sel and plane_sel.selectionCount > 0:
        plane_entity = plane_sel.selection(0).entity

    return {
        "is_sheet": is_sheet,
        "lumber": lumber,
        "sheet": sheet,
        "sheet_width_cm": width_val.value,
        "length_cm": length_val.value,
        "orientation": orient_dd.selectedItem.name,
        "anchor": anchor_dd.selectedItem.name,
        "on_edge": rotate_chk.value,
        "ease_edges": ease_chk.value,
        "new_component": comp_chk.value,
        "plane_entity": plane_entity,
    }


def _resolve_target_plane(
    target_comp: adsk.fusion.Component,
    orientation: str,
    plane_entity,
):
    if plane_entity is not None:
        return plane_entity

    if orientation == "Along X (+X)":
        return target_comp.yZConstructionPlane
    if orientation == "Along Y (+Y)":
        return target_comp.xZConstructionPlane
    return target_comp.xYConstructionPlane


def _collect_long_edges(
    extrude_feat: adsk.fusion.ExtrudeFeature,
) -> adsk.core.ObjectCollection:
    """Return the 4 long edges of a rectangular extrusion (not on start/end caps)."""
    cap_edge_tokens = set()
    for face_group in (extrude_feat.startFaces, extrude_feat.endFaces):
        for i in range(face_group.count):
            face = face_group.item(i)
            for j in range(face.edges.count):
                cap_edge_tokens.add(face.edges.item(j).entityToken)

    long_edges = adsk.core.ObjectCollection.create()
    body = extrude_feat.bodies.item(0)
    for i in range(body.edges.count):
        edge = body.edges.item(i)
        if edge.entityToken not in cap_edge_tokens:
            long_edges.add(edge)
    return long_edges


def _build_stock(state: dict) -> None:
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if not design:
        return

    is_sheet: bool = state["is_sheet"]
    length_cm: float = state["length_cm"]
    if length_cm <= 0:
        return

    if is_sheet:
        sheet: lumber_catalog.SheetThickness = state["sheet"]
        sheet_width_cm: float = state["sheet_width_cm"]
        if sheet_width_cm <= 0:
            return
        comp_name = lumber_catalog.format_sheet_component_name(
            sheet.name, sheet_width_cm, length_cm
        )
        sketch_name = f"{sheet.name} Profile"
        if state["on_edge"]:
            dx_cm, dy_cm = length_cm, sheet_width_cm
        else:
            dx_cm, dy_cm = sheet_width_cm, length_cm
        extrude_dist_cm = sheet.thickness_cm
        apply_ease = False
    else:
        lumber: lumber_catalog.LumberSize = state["lumber"]
        comp_name = lumber_catalog.format_component_name(lumber.nominal, length_cm)
        sketch_name = f"{lumber.nominal} Profile"
        if state["on_edge"]:
            dx_cm, dy_cm = lumber.thickness_cm, lumber.width_cm
        else:
            dx_cm, dy_cm = lumber.width_cm, lumber.thickness_cm
        extrude_dist_cm = length_cm
        apply_ease = state["ease_edges"]

    root_comp = design.rootComponent
    if state["new_component"]:
        try:
            occ = root_comp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            target_comp = occ.component
            target_comp.name = comp_name
        except RuntimeError:
            # Part Design documents only allow a single component; fall back to activeComponent.
            target_comp = design.activeComponent
    else:
        target_comp = design.activeComponent

    sketch_plane = _resolve_target_plane(
        target_comp, state["orientation"], state["plane_entity"]
    )
    sketch = target_comp.sketches.add(sketch_plane)
    sketch.name = sketch_name

    if state["anchor"] == "Centered":
        x0, y0 = -dx_cm / 2.0, -dy_cm / 2.0
        x1, y1 = dx_cm / 2.0, dy_cm / 2.0
    else:
        x0, y0 = 0.0, 0.0
        x1, y1 = dx_cm, dy_cm

    pt1 = adsk.core.Point3D.create(x0, y0, 0.0)
    pt2 = adsk.core.Point3D.create(x1, y1, 0.0)
    sketch.sketchCurves.sketchLines.addTwoPointRectangle(pt1, pt2)

    if sketch.profiles.count == 0:
        return
    profile = sketch.profiles.item(0)

    extrudes = target_comp.features.extrudeFeatures
    ext_input = extrudes.createInput(
        profile, adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    )
    ext_input.setDistanceExtent(
        False, adsk.core.ValueInput.createByReal(extrude_dist_cm)
    )
    extrude_feat = extrudes.add(ext_input)

    body = extrude_feat.bodies.item(0)
    body.name = comp_name

    if apply_ease:
        long_edges = _collect_long_edges(extrude_feat)
        if long_edges.count > 0:
            fillets = target_comp.features.filletFeatures
            fillet_input = fillets.createInput()
            radius = adsk.core.ValueInput.createByReal(
                lumber_catalog.inches_to_cm(lumber_catalog.EASED_EDGE_RADIUS_IN)
            )
            fillet_input.addConstantRadiusEdgeSet(long_edges, radius, True)
            fillets.add(fillet_input)


class LumberExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args: adsk.core.CommandEventArgs):
        try:
            state = _get_inputs_state(args.command.commandInputs)
            _build_stock(state)
            if state["is_sheet"]:
                name = lumber_catalog.format_sheet_component_name(
                    state["sheet"].name, state["sheet_width_cm"], state["length_cm"]
                )
                operation_log.SESSION_LOG.record("Create Sheet", name)
            else:
                name = lumber_catalog.format_component_name(
                    state["lumber"].nominal, state["length_cm"]
                )
                operation_log.SESSION_LOG.record("Create Lumber", name)
        except Exception:
            ui = adsk.core.Application.get().userInterface
            if ui:
                ui.messageBox(f"Failed to create stock:\n{traceback.format_exc()}")


class LumberPreviewHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args: adsk.core.CommandEventArgs):
        try:
            state = _get_inputs_state(args.command.commandInputs)
            _build_stock(state)
            args.isValidResult = True
        except Exception:
            pass


class LumberInputChangedHandler(adsk.core.InputChangedEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args: adsk.core.InputChangedEventArgs):
        try:
            changed = args.input
            inputs = args.inputs

            if changed.id == "stockType":
                stock_dd = adsk.core.DropDownCommandInput.cast(changed)
                is_sheet = stock_dd.selectedItem.name == "Sheet Stock"
                inputs.itemById("lumberSize").isVisible = not is_sheet
                inputs.itemById("lumberEase").isVisible = not is_sheet
                inputs.itemById("sheetType").isVisible = is_sheet
                inputs.itemById("sheetPreset").isVisible = is_sheet
                inputs.itemById("sheetWidth").isVisible = is_sheet
                inputs.itemById("sheetLimitNote").isVisible = is_sheet

                rotate_chk = adsk.core.BoolValueCommandInput.cast(
                    inputs.itemById("lumberRotate")
                )
                rotate_chk.name = (
                    "Rotate 90° (Swap W/L)" if is_sheet else "On Edge (Rotate 90°)"
                )
                if is_sheet:
                    _update_sheet_note(inputs)

            elif changed.id == "sheetType":
                sheet_dd = adsk.core.DropDownCommandInput.cast(changed)
                preset_dd = adsk.core.DropDownCommandInput.cast(
                    inputs.itemById("sheetPreset")
                )
                width_val = adsk.core.ValueCommandInput.cast(
                    inputs.itemById("sheetWidth")
                )
                length_val = adsk.core.ValueCommandInput.cast(
                    inputs.itemById("lumberLength")
                )
                sheet = lumber_catalog.SHEET_BY_LABEL[sheet_dd.selectedItem.name]
                _populate_sheet_presets(preset_dd, sheet)
                if sheet.presets:
                    _, w_expr, l_expr = sheet.presets[0]
                    width_val.expression = w_expr
                    length_val.expression = l_expr
                _update_sheet_note(inputs)

            elif changed.id == "sheetPreset":
                preset_dd = adsk.core.DropDownCommandInput.cast(changed)
                sheet_dd = adsk.core.DropDownCommandInput.cast(
                    inputs.itemById("sheetType")
                )
                sheet = lumber_catalog.SHEET_BY_LABEL[sheet_dd.selectedItem.name]
                selected_name = preset_dd.selectedItem.name
                for label, w_expr, l_expr in sheet.presets:
                    if label == selected_name:
                        adsk.core.ValueCommandInput.cast(
                            inputs.itemById("sheetWidth")
                        ).expression = w_expr
                        adsk.core.ValueCommandInput.cast(
                            inputs.itemById("lumberLength")
                        ).expression = l_expr
                        break
                _update_sheet_note(inputs)

            elif changed.id in ("sheetWidth", "lumberLength"):
                stock_dd = adsk.core.DropDownCommandInput.cast(
                    inputs.itemById("stockType")
                )
                if stock_dd and stock_dd.selectedItem.name == "Sheet Stock":
                    _update_sheet_note(inputs)

            elif changed.id == "lumberPlane":
                plane_sel = adsk.core.SelectionCommandInput.cast(changed)
                orient_dd = adsk.core.DropDownCommandInput.cast(
                    inputs.itemById("lumberOrient")
                )
                if orient_dd:
                    orient_dd.isEnabled = plane_sel.selectionCount == 0
        except Exception:
            pass


class LumberValidateHandler(adsk.core.ValidateInputsEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args: adsk.core.ValidateInputsEventArgs):
        try:
            inputs = args.inputs
            length_val = adsk.core.ValueCommandInput.cast(
                inputs.itemById("lumberLength")
            )
            if not length_val or length_val.value <= 0:
                args.areInputsValid = False
                return

            stock_dd = adsk.core.DropDownCommandInput.cast(
                inputs.itemById("stockType")
            )
            if stock_dd and stock_dd.selectedItem.name == "Sheet Stock":
                width_val = adsk.core.ValueCommandInput.cast(
                    inputs.itemById("sheetWidth")
                )
                if not width_val or width_val.value <= 0:
                    args.areInputsValid = False
                    return
                sheet_dd = adsk.core.DropDownCommandInput.cast(
                    inputs.itemById("sheetType")
                )
                sheet = lumber_catalog.SHEET_BY_LABEL[sheet_dd.selectedItem.name]
                w_in = lumber_catalog.cm_to_inches(width_val.value)
                l_in = lumber_catalog.cm_to_inches(length_val.value)
                if not sheet.fits_in_sheet(w_in, l_in):
                    args.areInputsValid = False
                    return

            args.areInputsValid = True
        except Exception:
            args.areInputsValid = False


class LumberCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args: adsk.core.CommandCreatedEventArgs):
        try:
            cmd = args.command
            inputs = cmd.commandInputs

            # 0. Stock Type Selector
            stock_dd = inputs.addDropDownCommandInput(
                "stockType",
                "Stock Type",
                adsk.core.DropDownStyles.TextListDropDownStyle,
            )
            stock_dd.listItems.add("Dimensional Lumber", True, "")
            stock_dd.listItems.add("Sheet Stock", False, "")

            # 1a. Nominal Lumber Size Dropdown
            size_dd = inputs.addDropDownCommandInput(
                "lumberSize",
                "Lumber Size",
                adsk.core.DropDownStyles.TextListDropDownStyle,
            )
            for idx, item in enumerate(lumber_catalog.LUMBER_SIZES):
                size_dd.listItems.add(item.label, idx == 0, "")

            # 1b. Sheet Stock Thickness Dropdown (hidden initially)
            sheet_dd = inputs.addDropDownCommandInput(
                "sheetType",
                "Thickness",
                adsk.core.DropDownStyles.TextListDropDownStyle,
            )
            for idx, item in enumerate(lumber_catalog.SHEET_THICKNESSES):
                sheet_dd.listItems.add(item.label, idx == 0, "")
            sheet_dd.isVisible = False

            # 1c. Sheet Stock Size Preset Dropdown (hidden initially)
            preset_dd = inputs.addDropDownCommandInput(
                "sheetPreset",
                "Sheet Size",
                adsk.core.DropDownStyles.TextListDropDownStyle,
            )
            _populate_sheet_presets(preset_dd, lumber_catalog.SHEET_THICKNESSES[0])
            preset_dd.isVisible = False

            # 1d. Sheet Width Input & Max-Size Note (hidden initially)
            width_val = inputs.addValueInput(
                "sheetWidth",
                "Width",
                "in",
                adsk.core.ValueInput.createByString("48 in"),
            )
            width_val.isVisible = False

            note_box = inputs.addTextBoxCommandInput(
                "sheetLimitNote",
                "Sheet Limit",
                lumber_catalog.SHEET_THICKNESSES[0].max_size_label,
                1,
                True,
            )
            note_box.isVisible = False

            # 2. Length Input (supports expressions like '8 ft', '96 in', '2400 mm')
            inputs.addValueInput(
                "lumberLength",
                "Length",
                "in",
                adsk.core.ValueInput.createByString("96 in"),
            )

            # 3. Orientation Dropdown (used when no custom plane/face is selected)
            orient_dd = inputs.addDropDownCommandInput(
                "lumberOrient",
                "Orientation",
                adsk.core.DropDownStyles.TextListDropDownStyle,
            )
            orient_dd.listItems.add("Vertical (+Z)", True, "")
            orient_dd.listItems.add("Along X (+X)", False, "")
            orient_dd.listItems.add("Along Y (+Y)", False, "")

            # 4. Anchor / Alignment
            anchor_dd = inputs.addDropDownCommandInput(
                "lumberAnchor",
                "Anchor",
                adsk.core.DropDownStyles.TextListDropDownStyle,
            )
            anchor_dd.listItems.add("Corner at Origin", True, "")
            anchor_dd.listItems.add("Centered", False, "")

            # 5. Rotate 90 degrees (flat vs on-edge / swap W & L)
            inputs.addBoolValueInput(
                "lumberRotate", "On Edge (Rotate 90°)", True, "", False
            )

            # 6. Optional Start Plane / Face
            plane_sel = inputs.addSelectionInput(
                "lumberPlane",
                "Start Plane / Face",
                "Optional: select a planar face or construction plane",
            )
            plane_sel.addSelectionFilter("PlanarFaces")
            plane_sel.addSelectionFilter("ConstructionPlanes")
            plane_sel.setSelectionLimits(0, 1)

            # 7. Ease Edges (1/8" radius, lumber only)
            inputs.addBoolValueInput(
                "lumberEase", 'Ease Edges (1/8" Radius)', True, "", False
            )

            # 8. Create New Component (off by default: each board is a named body)
            inputs.addBoolValueInput(
                "lumberNewComp", "Create New Component", True, "", False
            )

            on_execute = LumberExecuteHandler()
            cmd.execute.add(on_execute)
            _handlers.append(on_execute)

            on_preview = LumberPreviewHandler()
            cmd.executePreview.add(on_preview)
            _handlers.append(on_preview)

            on_input_changed = LumberInputChangedHandler()
            cmd.inputChanged.add(on_input_changed)
            _handlers.append(on_input_changed)

            on_validate = LumberValidateHandler()
            cmd.validateInputs.add(on_validate)
            _handlers.append(on_validate)

        except Exception:
            ui = adsk.core.Application.get().userInterface
            if ui:
                ui.messageBox(
                    f"Failed to initialize Create Lumber dialog:\n{traceback.format_exc()}"
                )


def run(context):
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface

        fusion_ui.register_panel_command(
            ui=ui,
            panel_id=PANEL_ID,
            cmd_id=CMD_ID,
            cmd_name=CMD_NAME,
            cmd_desc=CMD_DESCRIPTION,
            resource_dir=RESOURCE_FOLDER,
            created_handler_factory=LumberCommandCreatedHandler,
            handlers=_handlers,
        )
        attach_command.register_attach_command(ui, PANEL_ID, ADDIN_DIR, _handlers)
        joinery_command.register_joinery_command(ui, PANEL_ID, ADDIN_DIR, _handlers)
        kerf_command.register_kerf_command(ui, PANEL_ID, ADDIN_DIR, _handlers)
        operations_command.register_ops_command(ui, PANEL_ID, ADDIN_DIR, _handlers)

    except Exception:
        ui = adsk.core.Application.get().userInterface
        if ui:
            ui.messageBox(f"Add-In startup failed:\n{traceback.format_exc()}")


def stop(context):
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface

        attach_command.unregister_attach_command(ui, PANEL_ID)
        joinery_command.unregister_joinery_command(ui, PANEL_ID)
        kerf_command.unregister_kerf_command(ui, PANEL_ID)
        operations_command.unregister_ops_command(ui, PANEL_ID)
        fusion_ui.unregister_panel_command(ui, PANEL_ID, CMD_ID)

        _handlers.clear()
    except Exception:
        ui = adsk.core.Application.get().userInterface
        if ui:
            ui.messageBox(f"Add-In stop failed:\n{traceback.format_exc()}")

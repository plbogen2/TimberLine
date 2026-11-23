"""Autodesk Fusion command: Create Frame (8'x4' table/box frames with joinery)."""

import os
import traceback

import adsk.core
import adsk.fusion

import frame_planner
import fusion_ui
import lumber_catalog

FRAME_CMD_ID = "TimberLineFrameCmd"
FRAME_CMD_NAME = "Create Frame"
FRAME_CMD_DESC = (
    "Build an assembled 4-sided rectangular frame (e.g. 8' x 4' table frame) "
    "with automatic rail lengths, 45° miters, or interlocking half-lap corners."
)


def _create_member_component(
    design: adsk.fusion.Design, name: str, create_new: bool
) -> adsk.fusion.Component:
    if not create_new:
        return design.activeComponent
    try:
        occ = design.rootComponent.occurrences.addNewComponent(
            adsk.core.Matrix3D.create()
        )
        occ.component.name = name
        return occ.component
    except RuntimeError:
        return design.activeComponent


def _cut_member_profiles(
    comp: adsk.fusion.Component,
    sketch: adsk.fusion.Sketch,
    body: adsk.fusion.BRepBody,
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
    ext_in.participantBodies = [body]
    extrudes.add(ext_in)


def _build_frame(inputs: adsk.core.CommandInputs) -> None:
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if not design:
        return

    size_label = adsk.core.DropDownCommandInput.cast(
        inputs.itemById("frameLumberSize")
    ).selectedItem.name
    lumber = lumber_catalog.LUMBER_BY_LABEL[size_label]
    outer_len_cm = adsk.core.ValueCommandInput.cast(
        inputs.itemById("frameLength")
    ).value
    outer_wid_cm = adsk.core.ValueCommandInput.cast(
        inputs.itemById("frameWidth")
    ).value
    on_edge = adsk.core.BoolValueCommandInput.cast(
        inputs.itemById("frameOnEdge")
    ).value
    corner_style = adsk.core.DropDownCommandInput.cast(
        inputs.itemById("frameCornerStyle")
    ).selectedItem.name
    new_comp = adsk.core.BoolValueCommandInput.cast(
        inputs.itemById("frameNewComp")
    ).value

    members = frame_planner.compute_frame_members(
        lumber=lumber,
        outer_length_cm=outer_len_cm,
        outer_width_cm=outer_wid_cm,
        on_edge=on_edge,
        corner_style=corner_style,
    )

    for member in members:
        comp = _create_member_component(design, member.name, new_comp)
        xy_plane = comp.xYConstructionPlane

        sketch = comp.sketches.add(xy_plane)
        sketch.name = f"{member.name} Profile"
        sketch.sketchCurves.sketchLines.addTwoPointRectangle(
            adsk.core.Point3D.create(member.x0_cm, member.y0_cm, 0.0),
            adsk.core.Point3D.create(
                member.x0_cm + member.dx_cm, member.y0_cm + member.dy_cm, 0.0
            ),
        )
        if sketch.profiles.count == 0:
            continue
        extrudes = comp.features.extrudeFeatures
        ext_in = extrudes.createInput(
            sketch.profiles.item(0),
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        )
        ext_in.setDistanceExtent(
            False, adsk.core.ValueInput.createByReal(member.dz_cm)
        )
        feat = extrudes.add(ext_in)
        body = feat.bodies.item(0)
        body.name = member.name

        if member.miter_triangles_xy:
            m_sketch = comp.sketches.add(xy_plane)
            m_sketch.name = "Miter Cuts"
            lines = m_sketch.sketchCurves.sketchLines
            for (x0, y0), (x1, y1), (x2, y2) in member.miter_triangles_xy:
                p0 = adsk.core.Point3D.create(x0, y0, 0.0)
                p1 = adsk.core.Point3D.create(x1, y1, 0.0)
                p2 = adsk.core.Point3D.create(x2, y2, 0.0)
                lines.addByTwoPoints(p0, p1)
                lines.addByTwoPoints(p1, p2)
                lines.addByTwoPoints(p2, p0)
            _cut_member_profiles(comp, m_sketch, body, member.dz_cm)

        if member.lap_cuts_xy:
            if member.lap_from_top:
                p_in = comp.constructionPlanes.createInput()
                p_in.setByOffset(
                    xy_plane, adsk.core.ValueInput.createByReal(member.dz_cm)
                )
                cut_plane = comp.constructionPlanes.add(p_in)
                cut_dist = -member.dz_cm / 2.0
            else:
                cut_plane = xy_plane
                cut_dist = member.dz_cm / 2.0

            l_sketch = comp.sketches.add(cut_plane)
            l_sketch.name = "Half-Lap Cuts"
            for x0, y0, x1, y1 in member.lap_cuts_xy:
                l_sketch.sketchCurves.sketchLines.addTwoPointRectangle(
                    adsk.core.Point3D.create(x0, y0, 0.0),
                    adsk.core.Point3D.create(x1, y1, 0.0),
                )
            _cut_member_profiles(comp, l_sketch, body, cut_dist)


class FrameExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args: adsk.core.CommandEventArgs):
        try:
            _build_frame(args.command.commandInputs)
        except Exception:
            ui = adsk.core.Application.get().userInterface
            if ui:
                ui.messageBox(f"Failed to create frame:\n{traceback.format_exc()}")


class FramePreviewHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args: adsk.core.CommandEventArgs):
        try:
            _build_frame(args.command.commandInputs)
            args.isValidResult = True
        except Exception:
            pass


class FrameValidateHandler(adsk.core.ValidateInputsEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args: adsk.core.ValidateInputsEventArgs):
        try:
            inputs = args.inputs
            size_label = adsk.core.DropDownCommandInput.cast(
                inputs.itemById("frameLumberSize")
            ).selectedItem.name
            lumber = lumber_catalog.LUMBER_BY_LABEL[size_label]
            length_cm = adsk.core.ValueCommandInput.cast(
                inputs.itemById("frameLength")
            ).value
            width_cm = adsk.core.ValueCommandInput.cast(
                inputs.itemById("frameWidth")
            ).value
            on_edge = adsk.core.BoolValueCommandInput.cast(
                inputs.itemById("frameOnEdge")
            ).value
            thick = lumber.thickness_cm if on_edge else lumber.width_cm
            args.areInputsValid = length_cm > 2.0 * thick and width_cm > 2.0 * thick
        except Exception:
            args.areInputsValid = False


class FrameCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self, handlers: list):
        super().__init__()
        self._handlers = handlers

    def notify(self, args: adsk.core.CommandCreatedEventArgs):
        try:
            cmd = args.command
            inputs = cmd.commandInputs

            size_dd = inputs.addDropDownCommandInput(
                "frameLumberSize",
                "Lumber Size",
                adsk.core.DropDownStyles.TextListDropDownStyle,
            )
            for idx, item in enumerate(lumber_catalog.LUMBER_SIZES):
                size_dd.listItems.add(item.label, idx == 0, "")

            inputs.addValueInput(
                "frameLength",
                "Outer Length (X)",
                "in",
                adsk.core.ValueInput.createByString("96 in"),
            )
            inputs.addValueInput(
                "frameWidth",
                "Outer Width (Y)",
                "in",
                adsk.core.ValueInput.createByString("48 in"),
            )

            style_dd = inputs.addDropDownCommandInput(
                "frameCornerStyle",
                "Corner Joinery",
                adsk.core.DropDownStyles.TextListDropDownStyle,
            )
            for idx, style in enumerate(frame_planner.CORNER_STYLES):
                style_dd.listItems.add(style, idx == 0, "")

            inputs.addBoolValueInput(
                "frameOnEdge", "Rails On Edge (Apron)", True, "", True
            )
            inputs.addBoolValueInput(
                "frameNewComp", "Create New Components", True, "", True
            )

            on_exec = FrameExecuteHandler()
            cmd.execute.add(on_exec)
            self._handlers.append(on_exec)

            on_prev = FramePreviewHandler()
            cmd.executePreview.add(on_prev)
            self._handlers.append(on_prev)

            on_val = FrameValidateHandler()
            cmd.validateInputs.add(on_val)
            self._handlers.append(on_val)
        except Exception:
            ui = adsk.core.Application.get().userInterface
            if ui:
                ui.messageBox(
                    f"Failed to initialize Create Frame dialog:\n{traceback.format_exc()}"
                )


def register_frame_command(
    ui: adsk.core.UserInterface,
    panel_id: str,
    addin_dir: str,
    handlers: list,
) -> None:
    fusion_ui.register_panel_command(
        ui=ui,
        panel_id=panel_id,
        cmd_id=FRAME_CMD_ID,
        cmd_name=FRAME_CMD_NAME,
        cmd_desc=FRAME_CMD_DESC,
        resource_dir=os.path.join(addin_dir, "resources", "FrameIcon"),
        created_handler_factory=lambda: FrameCommandCreatedHandler(handlers),
        handlers=handlers,
    )


def unregister_frame_command(ui: adsk.core.UserInterface, panel_id: str) -> None:
    fusion_ui.unregister_panel_command(ui, panel_id, FRAME_CMD_ID)

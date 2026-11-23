"""Autodesk Fusion command: Add Joinery (Rabbet, Dado, Half-Lap, Tenon, Mortise, Pocket Holes, Dowels)."""

import math
import os
import traceback

import adsk.core
import adsk.fusion

import joinery_tools

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
    "Tenon",
    "Mortise",
    "Pocket Holes (15°)",
    "Dowel Holes",
]

_EDGE_REQUIRED_JOINTS = {"Rabbet", "Dado / Groove", "Half-Lap", "Pocket Holes (15°)"}


def _face_bounds_2d(
    sketch: adsk.fusion.Sketch, face: adsk.fusion.BRepFace
) -> joinery_tools.Rect2D:
    us = []
    vs = []
    for i in range(face.vertices.count):
        pt = sketch.modelToSketchSpace(face.vertices.item(i).geometry)
        us.append(pt.x)
        vs.append(pt.y)
    return (min(us), min(vs), max(us), max(vs))


def _target_component_for_face(
    design: adsk.fusion.Design, face: adsk.fusion.BRepFace
) -> adsk.fusion.Component:
    body = face.body
    if body and body.parentComponent:
        return body.parentComponent
    return design.activeComponent


def _cut_rect_on_face(
    comp: adsk.fusion.Component,
    face: adsk.fusion.BRepFace,
    rect: joinery_tools.Rect2D,
    depth_cm: float,
    name: str,
) -> None:
    sketch = comp.sketches.add(face)
    sketch.name = name
    u0, v0, u1, v1 = rect
    sketch.sketchCurves.sketchLines.addTwoPointRectangle(
        adsk.core.Point3D.create(u0, v0, 0.0),
        adsk.core.Point3D.create(u1, v1, 0.0),
    )
    if sketch.profiles.count == 0:
        return
    extrudes = comp.features.extrudeFeatures
    ext_input = extrudes.createInput(
        sketch.profiles.item(0), adsk.fusion.FeatureOperations.CutFeatureOperation
    )
    ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(-depth_cm))
    extrudes.add(ext_input)


def _cut_tenon(
    comp: adsk.fusion.Component,
    face: adsk.fusion.BRepFace,
    thickness_cm: float,
    width_cm: float,
    length_cm: float,
) -> None:
    sketch = comp.sketches.add(face)
    sketch.name = "Tenon Profile"
    bounds = _face_bounds_2d(sketch, face)
    u_min, v_min, u_max, v_max = bounds

    lines = sketch.sketchCurves.sketchLines
    lines.addTwoPointRectangle(
        adsk.core.Point3D.create(u_min - 0.01, v_min - 0.01, 0.0),
        adsk.core.Point3D.create(u_max + 0.01, v_max + 0.01, 0.0),
    )
    iu0, iv0, iu1, iv1 = joinery_tools.compute_centered_rect(
        bounds, thickness_cm, width_cm
    )
    lines.addTwoPointRectangle(
        adsk.core.Point3D.create(iu0, iv0, 0.0),
        adsk.core.Point3D.create(iu1, iv1, 0.0),
    )

    outer_profile = None
    for i in range(sketch.profiles.count):
        prof = sketch.profiles.item(i)
        if prof.profileLoops.count >= 2:
            outer_profile = prof
            break
    if outer_profile is None:
        return

    extrudes = comp.features.extrudeFeatures
    ext_input = extrudes.createInput(
        outer_profile, adsk.fusion.FeatureOperations.CutFeatureOperation
    )
    ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(-length_cm))
    extrudes.add(ext_input)


def _cut_dowel_holes(
    comp: adsk.fusion.Component,
    face: adsk.fusion.BRepFace,
    count: int,
    dia_cm: float,
    depth_cm: float,
    inset_cm: float,
) -> None:
    sketch = comp.sketches.add(face)
    sketch.name = "Dowel Holes"
    bounds = _face_bounds_2d(sketch, face)
    centers = joinery_tools.compute_dowel_centers(bounds, count, inset_cm)
    circles = sketch.sketchCurves.sketchCircles
    radius = dia_cm / 2.0
    for cx, cy in centers:
        circles.addByCenterRadius(adsk.core.Point3D.create(cx, cy, 0.0), radius)

    if sketch.profiles.count == 0:
        return
    profs = adsk.core.ObjectCollection.create()
    for i in range(sketch.profiles.count):
        profs.add(sketch.profiles.item(i))

    extrudes = comp.features.extrudeFeatures
    ext_input = extrudes.createInput(
        profs, adsk.fusion.FeatureOperations.CutFeatureOperation
    )
    ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(-depth_cm))
    extrudes.add(ext_input)


def _cut_pocket_holes(
    comp: adsk.fusion.Component,
    face: adsk.fusion.BRepFace,
    edge: adsk.fusion.BRepEdge,
    count: int,
    setback_cm: float,
    inset_cm: float,
    pocket_dia_cm: float,
    pilot_dia_cm: float,
    pocket_depth_cm: float,
) -> None:
    base_sketch = comp.sketches.add(face)
    base_sketch.name = "Pocket Hole Layout"
    bounds = _face_bounds_2d(base_sketch, face)
    p0_3d = base_sketch.modelToSketchSpace(edge.startVertex.geometry)
    p1_3d = base_sketch.modelToSketchSpace(edge.endVertex.geometry)

    lp0, lp1, to_edge_2d, centers_2d = joinery_tools.compute_pocket_hole_line_and_centers(
        bounds, (p0_3d.x, p0_3d.y), (p1_3d.x, p1_3d.y), setback_cm, count, inset_cm
    )

    line = base_sketch.sketchCurves.sketchLines.addByTwoPoints(
        adsk.core.Point3D.create(lp0[0], lp0[1], 0.0),
        adsk.core.Point3D.create(lp1[0], lp1[1], 0.0),
    )
    line.isConstruction = True

    origin_3d = base_sketch.sketchToModelSpace(adsk.core.Point3D.create(0.0, 0.0, 0.0))
    dir_pt_3d = base_sketch.sketchToModelSpace(
        adsk.core.Point3D.create(to_edge_2d[0], to_edge_2d[1], 0.0)
    )
    to_edge_vec = origin_3d.vectorTo(dir_pt_3d)
    to_edge_vec.normalize()

    # Create 15-degree angled construction plane tilted toward the edge.
    planes = comp.constructionPlanes
    plane_input = planes.createInput()
    plane_input.setByAngle(line, adsk.core.ValueInput.createByString("15 deg"), face)
    angled_plane = planes.add(plane_input)

    # Cut direction is -plane_normal; verify it points toward the edge.
    if (-angled_plane.geometry.normal.x * to_edge_vec.x
        - angled_plane.geometry.normal.y * to_edge_vec.y
        - angled_plane.geometry.normal.z * to_edge_vec.z) < 0:
        angled_plane.deleteMe()
        plane_input = planes.createInput()
        plane_input.setByAngle(
            line, adsk.core.ValueInput.createByString("-15 deg"), face
        )
        angled_plane = planes.add(plane_input)

    centers_3d = [
        base_sketch.sketchToModelSpace(adsk.core.Point3D.create(cx, cy, 0.0))
        for cx, cy in centers_2d
    ]

    # 1. Cut 3/8" pocket bore
    pocket_sketch = comp.sketches.add(angled_plane)
    pocket_sketch.name = "Pocket Bore"
    for c3 in centers_3d:
        cp = pocket_sketch.modelToSketchSpace(c3)
        pocket_sketch.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(cp.x, cp.y, 0.0), pocket_dia_cm / 2.0
        )
    if pocket_sketch.profiles.count > 0:
        profs = adsk.core.ObjectCollection.create()
        for i in range(pocket_sketch.profiles.count):
            profs.add(pocket_sketch.profiles.item(i))
        ext_in = comp.features.extrudeFeatures.createInput(
            profs, adsk.fusion.FeatureOperations.CutFeatureOperation
        )
        ext_in.setDistanceExtent(
            False, adsk.core.ValueInput.createByReal(-pocket_depth_cm)
        )
        comp.features.extrudeFeatures.add(ext_in)

    # 2. Cut 5/32" pilot hole through the edge
    pilot_depth_cm = setback_cm / math.cos(math.radians(15.0)) + 1.0
    pilot_sketch = comp.sketches.add(angled_plane)
    pilot_sketch.name = "Pocket Pilot"
    for c3 in centers_3d:
        cp = pilot_sketch.modelToSketchSpace(c3)
        pilot_sketch.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(cp.x, cp.y, 0.0), pilot_dia_cm / 2.0
        )
    if pilot_sketch.profiles.count > 0:
        profs = adsk.core.ObjectCollection.create()
        for i in range(pilot_sketch.profiles.count):
            profs.add(pilot_sketch.profiles.item(i))
        ext_in = comp.features.extrudeFeatures.createInput(
            profs, adsk.fusion.FeatureOperations.CutFeatureOperation
        )
        ext_in.setDistanceExtent(
            False, adsk.core.ValueInput.createByReal(-pilot_depth_cm)
        )
        comp.features.extrudeFeatures.add(ext_in)


def _execute_joinery(inputs: adsk.core.CommandInputs) -> None:
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if not design:
        return

    joint_type = adsk.core.DropDownCommandInput.cast(
        inputs.itemById("jointType")
    ).selectedItem.name
    face_sel = adsk.core.SelectionCommandInput.cast(inputs.itemById("jointFace"))
    if face_sel.selectionCount == 0:
        return
    face = adsk.fusion.BRepFace.cast(face_sel.selection(0).entity)
    comp = _target_component_for_face(design, face)

    edge_sel = adsk.core.SelectionCommandInput.cast(inputs.itemById("jointEdge"))
    edge = (
        adsk.fusion.BRepEdge.cast(edge_sel.selection(0).entity)
        if edge_sel.selectionCount > 0
        else None
    )

    def _val(input_id: str) -> float:
        return adsk.core.ValueCommandInput.cast(inputs.itemById(input_id)).value

    def _int(input_id: str) -> int:
        return adsk.core.IntegerSpinnerCommandInput.cast(
            inputs.itemById(input_id)
        ).value

    if joint_type in ("Rabbet", "Half-Lap", "Dado / Groove"):
        if edge is None:
            return
        sketch = comp.sketches.add(face)
        bounds = _face_bounds_2d(sketch, face)
        p0 = sketch.modelToSketchSpace(edge.startVertex.geometry)
        p1 = sketch.modelToSketchSpace(edge.endVertex.geometry)
        sketch.deleteMe()

        offset = _val("jointOffset") if joint_type == "Dado / Groove" else 0.0
        rect = joinery_tools.compute_edge_strip_rect(
            bounds, (p0.x, p0.y), (p1.x, p1.y), _val("jointWidth"), offset=offset
        )
        _cut_rect_on_face(comp, face, rect, _val("jointDepth"), joint_type)

    elif joint_type == "Tenon":
        _cut_tenon(
            comp,
            face,
            _val("tenonThick"),
            _val("tenonWidth"),
            _val("tenonLength"),
        )

    elif joint_type == "Mortise":
        sketch = comp.sketches.add(face)
        bounds = _face_bounds_2d(sketch, face)
        sketch.deleteMe()
        rect = joinery_tools.compute_centered_rect(
            bounds, _val("jointWidth"), _val("tenonWidth")
        )
        _cut_rect_on_face(comp, face, rect, _val("jointDepth"), "Mortise")

    elif joint_type == "Pocket Holes (15°)":
        if edge is None:
            return
        _cut_pocket_holes(
            comp,
            face,
            edge,
            _int("holeCount"),
            _val("jointOffset"),
            _val("holeInset"),
            _val("holeDia"),
            _val("pilotDia"),
            _val("jointDepth"),
        )

    elif joint_type == "Dowel Holes":
        _cut_dowel_holes(
            comp,
            face,
            _int("holeCount"),
            _val("holeDia"),
            _val("jointDepth"),
            _val("holeInset"),
        )


class JoineryExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args: adsk.core.CommandEventArgs):
        try:
            _execute_joinery(args.command.commandInputs)
        except Exception:
            ui = adsk.core.Application.get().userInterface
            if ui:
                ui.messageBox(f"Failed to add joinery:\n{traceback.format_exc()}")


class JoineryInputChangedHandler(adsk.core.InputChangedEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args: adsk.core.InputChangedEventArgs):
        try:
            if args.input.id != "jointType":
                return
            inputs = args.inputs
            jt = adsk.core.DropDownCommandInput.cast(args.input).selectedItem.name

            edge_sel = adsk.core.SelectionCommandInput.cast(
                inputs.itemById("jointEdge")
            )
            edge_sel.isVisible = jt in _EDGE_REQUIRED_JOINTS

            w_in = adsk.core.ValueCommandInput.cast(inputs.itemById("jointWidth"))
            d_in = adsk.core.ValueCommandInput.cast(inputs.itemById("jointDepth"))
            off_in = adsk.core.ValueCommandInput.cast(inputs.itemById("jointOffset"))
            t_thick = adsk.core.ValueCommandInput.cast(inputs.itemById("tenonThick"))
            t_width = adsk.core.ValueCommandInput.cast(inputs.itemById("tenonWidth"))
            t_len = adsk.core.ValueCommandInput.cast(inputs.itemById("tenonLength"))
            h_cnt = adsk.core.IntegerSpinnerCommandInput.cast(
                inputs.itemById("holeCount")
            )
            h_dia = adsk.core.ValueCommandInput.cast(inputs.itemById("holeDia"))
            p_dia = adsk.core.ValueCommandInput.cast(inputs.itemById("pilotDia"))
            h_ins = adsk.core.ValueCommandInput.cast(inputs.itemById("holeInset"))

            for item in (w_in, d_in, off_in, t_thick, t_width, t_len, h_cnt, h_dia, p_dia, h_ins):
                item.isVisible = False

            if jt == "Rabbet":
                w_in.name, w_in.expression, w_in.isVisible = "Width", "0.5 in", True
                d_in.name, d_in.expression, d_in.isVisible = "Depth", "0.375 in", True
            elif jt == "Dado / Groove":
                off_in.name, off_in.expression, off_in.isVisible = "Offset from Edge", "6 in", True
                w_in.name, w_in.expression, w_in.isVisible = "Dado Width", "23/32 in", True
                d_in.name, d_in.expression, d_in.isVisible = "Depth", "0.375 in", True
            elif jt == "Half-Lap":
                w_in.name, w_in.expression, w_in.isVisible = "Lap Length", "3.5 in", True
                d_in.name, d_in.expression, d_in.isVisible = "Depth", "0.75 in", True
            elif jt == "Tenon":
                t_thick.isVisible = True
                t_width.name, t_width.expression, t_width.isVisible = "Tenon Width", "2.5 in", True
                t_len.isVisible = True
            elif jt == "Mortise":
                w_in.name, w_in.expression, w_in.isVisible = "Mortise Width", "0.5 in", True
                t_width.name, t_width.expression, t_width.isVisible = "Mortise Length", "2.5 in", True
                d_in.name, d_in.expression, d_in.isVisible = "Mortise Depth", "1.625 in", True
            elif jt == "Pocket Holes (15°)":
                h_cnt.isVisible = True
                off_in.name, off_in.expression, off_in.isVisible = "Setback from Edge", "1.25 in", True
                h_ins.isVisible = True
                h_dia.name, h_dia.expression, h_dia.isVisible = "Pocket Dia", "0.375 in", True
                p_dia.isVisible = True
                d_in.name, d_in.expression, d_in.isVisible = "Pocket Depth", "1.125 in", True
            elif jt == "Dowel Holes":
                h_cnt.isVisible = True
                h_dia.name, h_dia.expression, h_dia.isVisible = "Dowel Dia", "0.375 in", True
                d_in.name, d_in.expression, d_in.isVisible = "Hole Depth", "0.75 in", True
                h_ins.isVisible = True
        except Exception:
            pass


class JoineryValidateHandler(adsk.core.ValidateInputsEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args: adsk.core.ValidateInputsEventArgs):
        try:
            inputs = args.inputs
            face_sel = adsk.core.SelectionCommandInput.cast(
                inputs.itemById("jointFace")
            )
            if not face_sel or face_sel.selectionCount == 0:
                args.areInputsValid = False
                return
            jt = adsk.core.DropDownCommandInput.cast(
                inputs.itemById("jointType")
            ).selectedItem.name
            if jt in _EDGE_REQUIRED_JOINTS:
                edge_sel = adsk.core.SelectionCommandInput.cast(
                    inputs.itemById("jointEdge")
                )
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
                "jointType",
                "Joint Type",
                adsk.core.DropDownStyles.TextListDropDownStyle,
            )
            for idx, jt in enumerate(JOINT_TYPES):
                jt_dd.listItems.add(jt, idx == 0, "")

            face_sel = inputs.addSelectionInput(
                "jointFace", "Target Face", "Select the planar face to cut"
            )
            face_sel.addSelectionFilter("PlanarFaces")
            face_sel.setSelectionLimits(1, 1)

            edge_sel = inputs.addSelectionInput(
                "jointEdge", "Reference Edge", "Select the edge on that face"
            )
            edge_sel.addSelectionFilter("Edges")
            edge_sel.setSelectionLimits(0, 1)

            inputs.addValueInput(
                "jointOffset",
                "Offset from Edge",
                "in",
                adsk.core.ValueInput.createByString("6 in"),
            ).isVisible = False
            inputs.addValueInput(
                "jointWidth",
                "Width",
                "in",
                adsk.core.ValueInput.createByString("0.5 in"),
            )
            inputs.addValueInput(
                "jointDepth",
                "Depth",
                "in",
                adsk.core.ValueInput.createByString("0.375 in"),
            )

            inputs.addValueInput(
                "tenonThick",
                "Tenon Thickness",
                "in",
                adsk.core.ValueInput.createByString("0.5 in"),
            ).isVisible = False
            inputs.addValueInput(
                "tenonWidth",
                "Tenon Width",
                "in",
                adsk.core.ValueInput.createByString("2.5 in"),
            ).isVisible = False
            inputs.addValueInput(
                "tenonLength",
                "Tenon Length",
                "in",
                adsk.core.ValueInput.createByString("1.5 in"),
            ).isVisible = False

            inputs.addIntegerSpinnerCommandInput(
                "holeCount", "Hole Count", 1, 12, 1, 2
            ).isVisible = False
            inputs.addValueInput(
                "holeDia",
                "Pocket Dia",
                "in",
                adsk.core.ValueInput.createByString("0.375 in"),
            ).isVisible = False
            inputs.addValueInput(
                "pilotDia",
                "Pilot Dia",
                "in",
                adsk.core.ValueInput.createByString("0.15625 in"),
            ).isVisible = False
            inputs.addValueInput(
                "holeInset",
                "Edge Inset",
                "in",
                adsk.core.ValueInput.createByString("0.75 in"),
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
    res_dir = os.path.join(addin_dir, "resources", "JoineryIcon")
    resource_arg = res_dir if os.path.isdir(res_dir) else ""
    cmd_def = ui.commandDefinitions.itemById(JOINERY_CMD_ID)
    if not cmd_def:
        cmd_def = ui.commandDefinitions.addButtonDefinition(
            JOINERY_CMD_ID, JOINERY_CMD_NAME, JOINERY_CMD_DESC, resource_arg
        )
    on_created = JoineryCommandCreatedHandler(handlers)
    cmd_def.commandCreated.add(on_created)
    handlers.append(on_created)

    panel = ui.allToolbarPanels.itemById(panel_id)
    if panel and not panel.controls.itemById(JOINERY_CMD_ID):
        cntrl = panel.controls.addCommand(cmd_def)
        cntrl.isPromotedByDefault = True
        cntrl.isPromoted = True


def unregister_joinery_command(ui: adsk.core.UserInterface, panel_id: str) -> None:
    panel = ui.allToolbarPanels.itemById(panel_id)
    if panel:
        cntrl = panel.controls.itemById(JOINERY_CMD_ID)
        if cntrl:
            cntrl.deleteMe()
    cmd_def = ui.commandDefinitions.itemById(JOINERY_CMD_ID)
    if cmd_def:
        cmd_def.deleteMe()

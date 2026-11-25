import json
import os
import tempfile
import types
import unittest
from unittest.mock import MagicMock

from tests.adsk_mock import (
    FakeCollection,
    FakeCommand,
    FakePoint3D,
    install_adsk_mocks,
    make_fake_body,
    make_fake_component,
)

install_adsk_mocks()

import adsk.core  # noqa: E402
import TimberLine  # noqa: E402
import attach_command  # noqa: E402
import attach_planner  # noqa: E402
import corner_command  # noqa: E402
import corner_planner  # noqa: E402
import fusion_ui  # noqa: E402
import joinery_command  # noqa: E402
import kerf_command  # noqa: E402
import operation_log  # noqa: E402
import operations_command  # noqa: E402
import panel_command  # noqa: E402
import panel_planner  # noqa: E402


def _make_fake_design():
    root = make_fake_component("Root")
    return types.SimpleNamespace(rootComponent=root, activeComponent=root)


def _make_fake_face_and_edge(comp):
    body = make_fake_body(parent=comp)
    verts = FakeCollection([
        types.SimpleNamespace(geometry=FakePoint3D(0.0, 0.0, 0.0)),
        types.SimpleNamespace(geometry=FakePoint3D(10.0, 0.0, 0.0)),
        types.SimpleNamespace(geometry=FakePoint3D(10.0, 20.0, 0.0)),
        types.SimpleNamespace(geometry=FakePoint3D(0.0, 20.0, 0.0)),
    ])
    face = types.SimpleNamespace(vertices=verts, body=body)
    edge = types.SimpleNamespace(
        startVertex=types.SimpleNamespace(geometry=FakePoint3D(0.0, 0.0, 0.0)),
        endVertex=types.SimpleNamespace(geometry=FakePoint3D(0.0, 20.0, 0.0)),
    )
    return face, edge


class TestFusionCommands(unittest.TestCase):
    def setUp(self):
        self.design = _make_fake_design()
        self.mock_ui = MagicMock()
        app = MagicMock()
        app.activeProduct = self.design
        app.userInterface = self.mock_ui
        adsk.core.Application.get.return_value = app

    def test_manifest_uses_valid_fusion360_addin_schema(self):
        manifest_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "TimberLine.manifest",
        )
        with open(manifest_path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["autodeskProduct"], "Fusion360")
        self.assertEqual(data["type"], "addin")

    def test_joinery_ui_config_covers_all_joint_types(self):
        for jt in joinery_command.JOINT_TYPES:
            self.assertIn(jt, joinery_command._JOINT_UI_CONFIG)
            for input_id, _, _ in joinery_command._JOINT_UI_CONFIG[jt]:
                self.assertIn(input_id, joinery_command._ALL_PARAM_INPUT_IDS)

    def test_kerf_body_matching_and_collection(self):
        root = self.design.rootComponent
        root.bRepBodies.append(make_fake_body("Stud1", 3.81, 8.89, 243.84, visible=True))
        root.bRepBodies.append(make_fake_body("Hidden", 3.81, 8.89, 243.84, visible=False))
        occ = root.occurrences.addNewComponent(None)
        occ.component.bRepBodies.append(
            make_fake_body("Panel1", 1.825625, 60.96, 121.92, visible=True)
        )
        linear, sheets = kerf_command._collect_design_cuts(self.design)
        self.assertEqual(len(linear["2x4"]), 1)
        self.assertEqual(len(sheets['3/4" Plywood'][1]), 1)

    def test_addin_run_and_stop_register_all_three_commands(self):
        self.mock_ui.commandDefinitions.itemById.return_value = None
        mock_panel = MagicMock()
        mock_panel.controls.itemById.return_value = None
        self.mock_ui.allToolbarPanels.itemById.return_value = mock_panel

        TimberLine._handlers.clear()
        TimberLine.run({})
        self.assertEqual(self.mock_ui.commandDefinitions.addButtonDefinition.call_count, 7)
        self.assertEqual(mock_panel.controls.addCommand.call_count, 7)
        self.assertEqual(len(TimberLine._handlers), 7)

        # Unregister when items exist
        self.mock_ui.commandDefinitions.itemById.return_value = MagicMock()
        mock_panel.controls.itemById.return_value = MagicMock()
        mock_panel.controls.count = 0
        TimberLine.stop({})
        self.assertEqual(len(TimberLine._handlers), 0)

        # Panel auto-creation when TimberLinePanel does not exist yet
        panel_created = [False]
        legacy_panel = MagicMock()

        def _panel_lookup(pid):
            if pid == "SolidCreatePanel":
                return legacy_panel
            return mock_panel if panel_created[0] else None

        solid_tab = MagicMock()

        def _add_panel(*_args):
            panel_created[0] = True
            return mock_panel

        solid_tab.toolbarPanels.add.side_effect = _add_panel
        self.mock_ui.allToolbarPanels.itemById.side_effect = _panel_lookup
        self.mock_ui.allToolbarTabs.itemById.return_value = solid_tab
        self.mock_ui.commandDefinitions.itemById.return_value = None
        TimberLine.run({})
        solid_tab.toolbarPanels.add.assert_called_once_with(
            "TimberLinePanel", "TimberLine", "SolidCreatePanel", False
        )
        TimberLine.stop({})

    def test_lumber_command_lifecycle_lumber_and_sheet(self):
        cmd = FakeCommand()
        TimberLine.LumberCommandCreatedHandler().notify(
            types.SimpleNamespace(command=cmd)
        )
        inputs = cmd.commandInputs

        # Test inputChanged: switch to Sheet Stock, change sheetType, preset, width, plane
        chg = cmd.inputChanged.handlers[0]
        inputs.itemById("stockType").select("Sheet Stock")
        chg.notify(types.SimpleNamespace(input=inputs.itemById("stockType"), inputs=inputs))
        self.assertTrue(inputs.itemById("sheetType").isVisible)

        inputs.itemById("sheetType").select('18mm Baltic Birch (0.708661")')
        chg.notify(types.SimpleNamespace(input=inputs.itemById("sheetType"), inputs=inputs))
        self.assertIn('60" x 60"', inputs.itemById("sheetLimitNote").text)

        inputs.itemById("sheetPreset").select('30" x 60" Half Sheet')
        chg.notify(types.SimpleNamespace(input=inputs.itemById("sheetPreset"), inputs=inputs))
        self.assertAlmostEqual(inputs.itemById("sheetWidth").value, 30.0 * 2.54)

        inputs.itemById("sheetWidth").expression = "80 in"
        chg.notify(types.SimpleNamespace(input=inputs.itemById("sheetWidth"), inputs=inputs))
        self.assertIn("Exceeds", inputs.itemById("sheetLimitNote").text)

        # Test validateInputs
        val = cmd.validateInputs.handlers[0]
        v_args = types.SimpleNamespace(inputs=inputs, areInputsValid=True)
        val.notify(v_args)
        self.assertFalse(v_args.areInputsValid)  # exceeds 60x60

        inputs.itemById("sheetWidth").expression = "0 in"
        val.notify(v_args)
        self.assertFalse(v_args.areInputsValid)

        inputs.itemById("sheetWidth").expression = "30 in"
        inputs.itemById("lumberRotate").value = True
        inputs.itemById("lumberAnchor").select("Centered")
        inputs.itemById("lumberNewComp").value = False
        val.notify(v_args)
        self.assertTrue(v_args.areInputsValid)

        # Execute Sheet Stock + Preview
        prev_args = types.SimpleNamespace(command=cmd, isValidResult=False)
        cmd.executePreview.handlers[0].notify(prev_args)
        self.assertTrue(prev_args.isValidResult)
        cmd.execute.handlers[0].notify(types.SimpleNamespace(command=cmd))

        # Switch back to Dimensional Lumber with Ease Edges, New Component, X/Y/Z orientations
        inputs.itemById("stockType").select("Dimensional Lumber")
        chg.notify(types.SimpleNamespace(input=inputs.itemById("stockType"), inputs=inputs))
        inputs.itemById("lumberNewComp").value = True
        inputs.itemById("lumberEase").value = True
        for orient in ("Vertical (+Z)", "Along X (+X)", "Along Y (+Y)"):
            inputs.itemById("lumberOrient").select(orient)
            cmd.execute.handlers[0].notify(types.SimpleNamespace(command=cmd))

        # Custom plane selection disables orientation
        face, _ = _make_fake_face_and_edge(self.design.rootComponent)
        inputs.itemById("lumberPlane").set_entities([face])
        chg.notify(types.SimpleNamespace(input=inputs.itemById("lumberPlane"), inputs=inputs))
        self.assertFalse(inputs.itemById("lumberOrient").isEnabled)
        cmd.execute.handlers[0].notify(types.SimpleNamespace(command=cmd))

        # Part Design fallback: addNewComponent raises RuntimeError -> uses activeComponent
        orig_add_comp = self.design.rootComponent.occurrences.addNewComponent
        self.design.rootComponent.occurrences.addNewComponent = MagicMock(
            side_effect=RuntimeError("Part Design documents can only contain one component")
        )
        bodies_before = len(self.design.activeComponent.bRepBodies)
        cmd.execute.handlers[0].notify(types.SimpleNamespace(command=cmd))
        self.assertEqual(len(self.design.activeComponent.bRepBodies), bodies_before + 1)
        self.design.rootComponent.occurrences.addNewComponent = orig_add_comp

        # Invalid length validation
        inputs.itemById("lumberLength").expression = "0 in"
        val.notify(v_args)
        self.assertFalse(v_args.areInputsValid)

    def test_joinery_command_all_seven_joints(self):
        handlers = []
        cmd = FakeCommand()
        joinery_command.JoineryCommandCreatedHandler(handlers).notify(
            types.SimpleNamespace(command=cmd)
        )
        inputs = cmd.commandInputs
        face, edge = _make_fake_face_and_edge(self.design.rootComponent)
        face.body.boundingBox.minPoint.z = -3.81  # 1.5" board behind source face

        val = cmd.validateInputs.handlers[0]
        v_args = types.SimpleNamespace(inputs=inputs, areInputsValid=True)
        val.notify(v_args)
        self.assertFalse(v_args.areInputsValid)  # missing face

        inputs.itemById("jointFace").set_entities([face])
        val.notify(v_args)
        self.assertFalse(v_args.areInputsValid)  # Rabbet requires edge

        inputs.itemById("jointEdge").set_entities([edge])
        val.notify(v_args)
        self.assertTrue(v_args.areInputsValid)

        chg = cmd.inputChanged.handlers[0]
        exe = cmd.execute.handlers[0]
        for jt in joinery_command.JOINT_TYPES:
            inputs.itemById("jointType").select(jt)
            chg.notify(types.SimpleNamespace(input=inputs.itemById("jointType"), inputs=inputs))
            exe.notify(types.SimpleNamespace(command=cmd))

        # Pocket holes on right edge verifies 75-deg perpendicular plane + outward offset
        # and deterministically tests the plane normal flip branch (dotProduct > 0).
        angle_calls = []
        offset_calls = []
        orig_create_plane_in = self.design.rootComponent.constructionPlanes.createInput
        orig_add_plane = self.design.rootComponent.constructionPlanes.add

        def _spy_plane_input():
            return types.SimpleNamespace(
                setByAngle=lambda _l, a, _p: angle_calls.append(a),
                setByOffset=lambda _p, d: offset_calls.append(d),
            )

        normals = [
            types.SimpleNamespace(dotProduct=lambda _v: 1.0),
            types.SimpleNamespace(dotProduct=lambda _v: -1.0),
            types.SimpleNamespace(dotProduct=lambda _v: -1.0),
        ]

        def _spy_add_plane(_inp):
            n = normals.pop(0) if normals else types.SimpleNamespace(dotProduct=lambda _v: -1.0)
            return types.SimpleNamespace(
                geometry=types.SimpleNamespace(normal=n),
                deleteMe=lambda: None,
            )

        self.design.rootComponent.constructionPlanes.createInput = _spy_plane_input
        self.design.rootComponent.constructionPlanes.add = _spy_add_plane
        right_edge = types.SimpleNamespace(
            startVertex=types.SimpleNamespace(geometry=FakePoint3D(10.0, 0.0, 0.0)),
            endVertex=types.SimpleNamespace(geometry=FakePoint3D(10.0, 20.0, 0.0)),
        )
        inputs.itemById("jointEdge").set_entities([right_edge])
        inputs.itemById("jointType").select("Pocket Holes (15°)")
        chg.notify(types.SimpleNamespace(input=inputs.itemById("jointType"), inputs=inputs))
        exe.notify(types.SimpleNamespace(command=cmd))
        self.design.rootComponent.constructionPlanes.createInput = orig_create_plane_in
        self.design.rootComponent.constructionPlanes.add = orig_add_plane
        self.assertIn(("str", "75 deg"), angle_calls)
        self.assertIn(("str", "-75 deg"), angle_calls)
        self.assertTrue(any(val > 0 for _, val in offset_calls))

        # Horizontal edge triggers du >= dv branch in Scarf and Sliding Dovetail
        horiz_edge = types.SimpleNamespace(
            startVertex=types.SimpleNamespace(geometry=FakePoint3D(0.0, 0.0, 0.0)),
            endVertex=types.SimpleNamespace(geometry=FakePoint3D(10.0, 0.0, 0.0)),
        )
        inputs.itemById("jointEdge").set_entities([horiz_edge])
        for jt in ("Scarf Joint", "Sliding Dovetail"):
            inputs.itemById("jointType").select(jt)
            chg.notify(types.SimpleNamespace(input=inputs.itemById("jointType"), inputs=inputs))
            exe.notify(types.SimpleNamespace(command=cmd))
        inputs.itemById("jointEdge").set_entities([edge])

        # Edge-less fallback for target_component_for_face
        no_body_face = types.SimpleNamespace(vertices=face.vertices, body=None)
        self.assertIs(
            joinery_command.joinery_base.target_component_for_face(self.design, no_body_face),
            self.design.activeComponent,
        )

        # InputChanged for non-jointType input is a no-op, and missing edge guards
        chg.notify(types.SimpleNamespace(input=inputs.itemById("jointWidth"), inputs=inputs))
        inputs.itemById("jointEdge").set_entities([])
        for jt in ("Rabbet", "Pocket Holes (15°)"):
            inputs.itemById("jointType").select(jt)
            chg.notify(types.SimpleNamespace(input=inputs.itemById("jointType"), inputs=inputs))
            exe.notify(types.SimpleNamespace(command=cmd))

        # Reference Board auto-sizing for Dado / Groove, Rabbet, and cross Half-Lap
        inputs.itemById("jointEdge").set_entities([edge])
        mating_board = make_fake_body("Shelf", 1.825625, 20.0, 10.0)
        mating_board.boundingBox = types.SimpleNamespace(
            minPoint=FakePoint3D(3.0, 0.0, 0.0),
            maxPoint=FakePoint3D(4.825625, 20.0, 5.0),
        )
        inputs.itemById("refBoard").set_entities([mating_board])
        for jt in ("Dado / Groove", "Half-Lap", "Rabbet"):
            inputs.itemById("jointType").select(jt)
            chg.notify(types.SimpleNamespace(input=inputs.itemById("jointType"), inputs=inputs))
            chg.notify(types.SimpleNamespace(input=inputs.itemById("refBoard"), inputs=inputs))
            self.assertAlmostEqual(inputs.itemById("jointWidth").value, 1.825625)
            exe.notify(types.SimpleNamespace(command=cmd))
        self.assertTrue(inputs.itemById("jointOffset").isVisible or jt == "Rabbet")

        # Non-board-ref joint ignores _apply_board_reference
        inputs.itemById("jointType").select("Tenon")
        chg.notify(types.SimpleNamespace(input=inputs.itemById("jointType"), inputs=inputs))
        chg.notify(types.SimpleNamespace(input=inputs.itemById("refBoard"), inputs=inputs))

        # Two-board Housing / Dado validation and execution
        inputs.itemById("jointType").select("Housing / Dado (2-Board)")
        chg.notify(types.SimpleNamespace(input=inputs.itemById("jointType"), inputs=inputs))
        inputs.itemById("targetBoard").set_entities([])
        val.notify(v_args)
        self.assertFalse(v_args.areInputsValid)
        exe.notify(types.SimpleNamespace(command=cmd))

        target_board = make_fake_body("SidePanel", 1.825625, 30.0, 60.0, parent=self.design.rootComponent)
        inputs.itemById("targetBoard").set_entities([target_board])
        inputs.itemById("refBoard").set_entities([mating_board])
        val.notify(v_args)
        self.assertTrue(v_args.areInputsValid)
        exe.notify(types.SimpleNamespace(command=cmd))

    def test_kerf_command_execute_and_export(self):
        handlers = []
        cmd = FakeCommand()
        kerf_command.KerfCommandCreatedHandler(handlers).notify(
            types.SimpleNamespace(command=cmd)
        )
        self.design.rootComponent.bRepBodies.append(
            make_fake_body("Stud", 3.81, 8.89, 91.44, visible=True)
        )

        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, "plan.txt")
            dlg = MagicMock()
            dlg.showSave.return_value = adsk.core.DialogResults.DialogOK
            dlg.filename = out_path
            self.mock_ui.createFileDialog.return_value = dlg

            cmd.commandInputs.itemById("exportTxt").value = True
            cmd.execute.handlers[0].notify(types.SimpleNamespace(command=cmd))

            self.assertTrue(os.path.isfile(out_path))
            with open(out_path, encoding="utf-8") as f:
                self.assertIn("[2x4]", f.read())
            self.mock_ui.messageBox.assert_called()

    def test_error_and_guard_paths(self):
        # No active design guards
        app = adsk.core.Application.get.return_value
        app.activeProduct = None
        TimberLine._build_stock({"is_sheet": False, "length_cm": 10.0})
        joinery_command._execute_joinery(MagicMock())

        cmd = FakeCommand()
        kerf_command.KerfCommandCreatedHandler([]).notify(
            types.SimpleNamespace(command=cmd)
        )
        cmd.execute.handlers[0].notify(types.SimpleNamespace(command=cmd))

        # Restore design and test exception handlers
        app.activeProduct = self.design
        bad_cmd = types.SimpleNamespace(
            commandInputs=types.SimpleNamespace(itemById=MagicMock(side_effect=RuntimeError("boom")))
        )
        TimberLine.LumberExecuteHandler().notify(types.SimpleNamespace(command=bad_cmd))
        TimberLine.LumberPreviewHandler().notify(types.SimpleNamespace(command=bad_cmd))
        TimberLine.LumberInputChangedHandler().notify(
            types.SimpleNamespace(input=types.SimpleNamespace(id="lumberPlane"), inputs=bad_cmd.commandInputs)
        )
        v_args = types.SimpleNamespace(inputs=bad_cmd.commandInputs, areInputsValid=True)
        TimberLine.LumberValidateHandler().notify(v_args)
        self.assertFalse(v_args.areInputsValid)

        joinery_command.JoineryExecuteHandler().notify(types.SimpleNamespace(command=bad_cmd))
        joinery_command.JoineryInputChangedHandler().notify(
            types.SimpleNamespace(input=types.SimpleNamespace(id="jointType"), inputs=bad_cmd.commandInputs)
        )
        joinery_command.JoineryValidateHandler().notify(v_args)
        self.assertFalse(v_args.areInputsValid)

        kerf_command.KerfExecuteHandler().notify(types.SimpleNamespace(command=bad_cmd))
        self.mock_ui.messageBox.assert_called()

        # run() / stop() exception handlers
        self.mock_ui.commandDefinitions.itemById.side_effect = RuntimeError("ui boom")
        TimberLine.run({})
        TimberLine.stop({})

    def test_attach_and_list_operations_commands(self):
        operation_log.SESSION_LOG.clear()
        handlers = []
        cmd = FakeCommand()
        attach_command.AttachCommandCreatedHandler(handlers).notify(
            types.SimpleNamespace(command=cmd)
        )
        inputs = cmd.commandInputs
        face, edge = _make_fake_face_and_edge(self.design.rootComponent)
        face.body.boundingBox.minPoint.z = -3.81  # 1.5" board behind source face

        val = cmd.validateInputs.handlers[0]
        v_args = types.SimpleNamespace(inputs=inputs, areInputsValid=True)
        val.notify(v_args)
        self.assertFalse(v_args.areInputsValid)

        inputs.itemById("attachFace").set_entities([face])
        inputs.itemById("attachEdge").set_entities([edge])
        val.notify(v_args)
        self.assertTrue(v_args.areInputsValid)

        prev_args = types.SimpleNamespace(command=cmd, isValidResult=False)
        cmd.executePreview.handlers[0].notify(prev_args)
        self.assertTrue(prev_args.isValidResult)

        chg = cmd.inputChanged.handlers[0]
        chg.notify(types.SimpleNamespace(input=inputs.itemById("attachLength"), inputs=inputs))

        for jt in attach_planner.ATTACH_JOINT_TYPES:
            inputs.itemById("attachJointType").select(jt)
            chg.notify(types.SimpleNamespace(input=inputs.itemById("attachJointType"), inputs=inputs))
            cmd.execute.handlers[0].notify(types.SimpleNamespace(command=cmd))
        self.assertGreaterEqual(len(operation_log.SESSION_LOG.entries()), 5)

        # Horizontal edge + non-90 outer angle miter covers miter_axis_is_u=False & tilt branch
        horiz_edge = types.SimpleNamespace(
            startVertex=types.SimpleNamespace(geometry=FakePoint3D(0.0, 0.0, 0.0)),
            endVertex=types.SimpleNamespace(geometry=FakePoint3D(10.0, 0.0, 0.0)),
        )
        inputs.itemById("attachEdge").set_entities([horiz_edge])
        inputs.itemById("attachJointType").select("Miter")
        inputs.itemById("attachOuterAngle").expression = "120 deg"
        cmd.execute.handlers[0].notify(types.SimpleNamespace(command=cmd))
        inputs.itemById("attachEdge").set_entities([edge])

        # Part Design fallback & activeComponent mode
        inputs.itemById("attachNewComp").value = False
        cmd.execute.handlers[0].notify(types.SimpleNamespace(command=cmd))
        inputs.itemById("attachNewComp").value = True
        self.design.rootComponent.occurrences.addNewComponent = MagicMock(
            side_effect=RuntimeError("Part Design")
        )
        cmd.execute.handlers[0].notify(types.SimpleNamespace(command=cmd))

        # No active design, zero length, missing selection, and error handlers
        inputs.itemById("attachLength").expression = "0 in"
        attach_command._execute_attach(inputs)
        inputs.itemById("attachFace").set_entities([])
        attach_command._execute_attach(inputs)
        app = adsk.core.Application.get.return_value
        app.activeProduct = None
        attach_command._execute_attach(inputs)
        app.activeProduct = self.design

        bad_cmd = types.SimpleNamespace(
            commandInputs=types.SimpleNamespace(itemById=MagicMock(side_effect=RuntimeError("boom")))
        )
        attach_command.AttachExecuteHandler().notify(types.SimpleNamespace(command=bad_cmd))
        attach_command.AttachPreviewHandler().notify(types.SimpleNamespace(command=bad_cmd))
        attach_command.AttachInputChangedHandler().notify(
            types.SimpleNamespace(input=types.SimpleNamespace(id="attachJointType"), inputs=bad_cmd.commandInputs)
        )
        bad_v_args = types.SimpleNamespace(inputs=bad_cmd.commandInputs, areInputsValid=True)
        attach_command.AttachValidateHandler().notify(bad_v_args)
        self.assertFalse(bad_v_args.areInputsValid)

        # List Operations command with timeline + export + clear
        tl_item = types.SimpleNamespace(name="Extrude1", isSuppressed=False)
        self.design.timeline = FakeCollection([tl_item])
        ops_cmd = FakeCommand()
        operations_command.OpsCommandCreatedHandler(handlers).notify(
            types.SimpleNamespace(command=ops_cmd)
        )
        self.assertIn("Extrude1", ops_cmd.commandInputs.itemById("opsSummary").text)

        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, "ops.txt")
            dlg = MagicMock()
            dlg.showSave.return_value = adsk.core.DialogResults.DialogOK
            dlg.filename = out_path
            self.mock_ui.createFileDialog.return_value = dlg

            ops_cmd.commandInputs.itemById("opsExportTxt").value = True
            ops_cmd.commandInputs.itemById("opsClearLog").value = True
            ops_cmd.execute.handlers[0].notify(types.SimpleNamespace(command=ops_cmd))
            self.assertTrue(os.path.isfile(out_path))
            self.assertEqual(len(operation_log.SESSION_LOG.entries()), 0)

        operations_command.OpsExecuteHandler().notify(types.SimpleNamespace(command=bad_cmd))
        self.assertEqual(operations_command._read_design_timeline(types.SimpleNamespace()), [])
        operations_command.OpsCommandCreatedHandler(handlers).notify(
            types.SimpleNamespace(command=bad_cmd)
        )

    def test_convert_corner_command_all_types_and_guards(self):
        operation_log.SESSION_LOG.clear()
        handlers = []
        cmd = FakeCommand()
        corner_command.CornerCommandCreatedHandler(handlers).notify(
            types.SimpleNamespace(command=cmd)
        )
        inputs = cmd.commandInputs
        val = cmd.validateInputs.handlers[0]
        v_args = types.SimpleNamespace(inputs=inputs, areInputsValid=True)
        val.notify(v_args)
        self.assertFalse(v_args.areInputsValid)

        body_a = make_fake_body("RailA", 243.84, 3.81, 8.89, parent=self.design.rootComponent)
        body_b = make_fake_body("RailB", 3.81, 121.92, 8.89, parent=self.design.rootComponent)
        inputs.itemById("cornerBoardA").set_entities([body_a])
        inputs.itemById("cornerBoardB").set_entities([body_a])
        val.notify(v_args)
        self.assertFalse(v_args.areInputsValid)  # same body invalid

        corner_command._execute_convert_corner(inputs)  # same body guard

        inputs.itemById("cornerBoardB").set_entities([body_b])
        val.notify(v_args)
        self.assertTrue(v_args.areInputsValid)

        prev_args = types.SimpleNamespace(command=cmd, isValidResult=False)
        cmd.executePreview.handlers[0].notify(prev_args)
        self.assertTrue(prev_args.isValidResult)

        inputs.itemById("cornerAxis").select("Z")
        for jt in corner_planner.CORNER_CONVERT_TYPES:
            inputs.itemById("cornerJointType").select(jt)
            cmd.execute.handlers[0].notify(types.SimpleNamespace(command=cmd))
        self.assertEqual(len(operation_log.SESSION_LOG.entries()), 5)

        # Touching boards (non-overlapping Butt) trigger extend_a_box / extend_b_box join
        b_touch = make_fake_body("TouchB", 3.81, 121.92, 8.89, parent=self.design.rootComponent)
        b_touch.boundingBox.minPoint.y = 3.81
        inputs.itemById("cornerBoardB").set_entities([b_touch])
        inputs.itemById("cornerJointType").select("Half-Lap")
        cmd.execute.handlers[0].notify(types.SimpleNamespace(command=cmd))

        inputs.itemById("cornerBoardA").set_entities([b_touch])
        inputs.itemById("cornerBoardB").set_entities([body_a])
        cmd.execute.handlers[0].notify(types.SimpleNamespace(command=cmd))

        # No active design, missing selections, and error handlers
        inputs.itemById("cornerBoardA").set_entities([])
        corner_command._execute_convert_corner(inputs)
        app = adsk.core.Application.get.return_value
        app.activeProduct = None
        corner_command._execute_convert_corner(inputs)
        app.activeProduct = self.design

        bad_cmd = types.SimpleNamespace(
            commandInputs=types.SimpleNamespace(itemById=MagicMock(side_effect=RuntimeError("boom")))
        )
        corner_command.CornerExecuteHandler().notify(types.SimpleNamespace(command=bad_cmd))
        corner_command.CornerPreviewHandler().notify(types.SimpleNamespace(command=bad_cmd))
        bad_v_args = types.SimpleNamespace(inputs=bad_cmd.commandInputs, areInputsValid=True)
        corner_command.CornerValidateHandler().notify(bad_v_args)
        self.assertFalse(bad_v_args.areInputsValid)

    def test_fill_panel_command_and_guards(self):
        operation_log.SESSION_LOG.clear()
        handlers = []
        cmd = FakeCommand()
        panel_command.PanelCommandCreatedHandler(handlers).notify(
            types.SimpleNamespace(command=cmd)
        )
        inputs = cmd.commandInputs
        val = cmd.validateInputs.handlers[0]
        v_args = types.SimpleNamespace(inputs=inputs, areInputsValid=True)
        val.notify(v_args)
        self.assertFalse(v_args.areInputsValid)

        b1 = make_fake_body("Left", 3.81, 100.0, 8.89, parent=self.design.rootComponent)
        b2 = make_fake_body("Right", 3.81, 100.0, 8.89, parent=self.design.rootComponent)
        b2.boundingBox.minPoint.x = 50.0
        b2.boundingBox.maxPoint.x = 53.81
        inputs.itemById("panelBoards").set_entities([b1, b2])
        val.notify(v_args)
        self.assertTrue(v_args.areInputsValid)

        prev_args = types.SimpleNamespace(command=cmd, isValidResult=False)
        cmd.executePreview.handlers[0].notify(prev_args)
        self.assertTrue(prev_args.isValidResult)

        cmd.execute.handlers[0].notify(types.SimpleNamespace(command=cmd))
        self.assertEqual(len(operation_log.SESSION_LOG.entries()), 1)

        # combine RuntimeError guard (non-intersecting board) + z0==0 + no design + error handlers
        inputs.itemById("panelAlignment").select("Flush Back (-Normal Rabbet)")
        self.design.rootComponent.features.combineFeatures.add = MagicMock(
            side_effect=RuntimeError("No intersection")
        )
        cmd.execute.handlers[0].notify(types.SimpleNamespace(command=cmd))

        inputs.itemById("panelBoards").set_entities([])
        panel_command._execute_fill_panel(inputs)
        app = adsk.core.Application.get.return_value
        app.activeProduct = None
        panel_command._execute_fill_panel(inputs)
        app.activeProduct = self.design

        bad_cmd = types.SimpleNamespace(
            commandInputs=types.SimpleNamespace(itemById=MagicMock(side_effect=RuntimeError("boom")))
        )
        panel_command.PanelExecuteHandler().notify(types.SimpleNamespace(command=bad_cmd))
        panel_command.PanelPreviewHandler().notify(types.SimpleNamespace(command=bad_cmd))
        bad_v_args = types.SimpleNamespace(inputs=bad_cmd.commandInputs, areInputsValid=True)
        panel_command.PanelValidateHandler().notify(bad_v_args)
        self.assertFalse(bad_v_args.areInputsValid)


if __name__ == "__main__":
    unittest.main()

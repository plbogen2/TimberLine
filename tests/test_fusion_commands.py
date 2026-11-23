import unittest
from unittest.mock import MagicMock

from tests.adsk_mock import install_adsk_mocks

install_adsk_mocks()

import adsk.core  # noqa: E402
import TimberLine  # noqa: E402
import joinery_command  # noqa: E402
import kerf_command  # noqa: E402


class TestFusionCommands(unittest.TestCase):
    def test_joinery_ui_config_covers_all_joint_types(self):
        for jt in joinery_command.JOINT_TYPES:
            self.assertIn(jt, joinery_command._JOINT_UI_CONFIG)
            for input_id, _, _ in joinery_command._JOINT_UI_CONFIG[jt]:
                self.assertIn(input_id, joinery_command._ALL_PARAM_INPUT_IDS)

    def test_kerf_body_matching(self):
        lumber = kerf_command._match_lumber(1.5, 3.5)
        self.assertIsNotNone(lumber)
        self.assertEqual(lumber.nominal, "2x4")

        self.assertIsNone(kerf_command._match_lumber(1.0, 1.0))

        sheet = kerf_command._match_sheet(23.0 / 32.0)
        self.assertIsNotNone(sheet)
        self.assertEqual(sheet.name, '3/4" Plywood')

    def test_addin_run_and_stop_register_all_three_commands(self):
        mock_ui = MagicMock()
        mock_ui.commandDefinitions.itemById.return_value = None
        mock_panel = MagicMock()
        mock_panel.controls.itemById.return_value = None
        mock_ui.allToolbarPanels.itemById.return_value = mock_panel
        adsk.core.Application.get.return_value.userInterface = mock_ui

        TimberLine._handlers.clear()
        TimberLine.run({})
        self.assertEqual(mock_ui.commandDefinitions.addButtonDefinition.call_count, 3)
        self.assertEqual(mock_panel.controls.addCommand.call_count, 3)
        self.assertEqual(len(TimberLine._handlers), 3)

        TimberLine.stop({})
        self.assertEqual(len(TimberLine._handlers), 0)


if __name__ == "__main__":
    unittest.main()

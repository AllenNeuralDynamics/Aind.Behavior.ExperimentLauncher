import unittest
from pathlib import Path
from unittest.mock import MagicMock, create_autospec, patch

from aind_behavior_experiment_launcher.launcher.behavior_launcher import (
    BehaviorLauncher,
    BehaviorServicesFactoryManager,
)


class TestBehaviorLauncher(unittest.TestCase):
    def setUp(self):
        self.launcher = create_autospec(BehaviorLauncher)
        self.launcher.services_factory_manager = create_autospec(BehaviorServicesFactoryManager)
        self.launcher.services_factory_manager.resource_monitor = MagicMock()
        self.launcher.services_factory_manager.bonsai_app = MagicMock()
        self.launcher.services_factory_manager.data_mapper = MagicMock()
        self.launcher.services_factory_manager.data_transfer = MagicMock()
        self.launcher.session_schema_model = MagicMock()
        self.launcher.rig_schema_model = MagicMock()
        self.launcher.task_logic_schema_model = MagicMock()
        self.launcher._ui_helper = MagicMock()
        self.launcher.config_library_dir = "/path/to/config"
        self.launcher._subject_dir = Path("/path/to/subject")
        self.launcher._rig_dir = Path("/path/to/rig")
        self.launcher._task_logic_dir = Path("/path/to/task_logic")
        self.launcher.data_dir = Path("/path/to/data")
        self.launcher.temp_dir = Path("/path/to/temp")
        self.launcher.repository = MagicMock()
        self.launcher.group_by_subject_log = False
        self.launcher._debug_mode = False
        self.launcher.allow_dirty = False
        self.launcher.skip_hardware_validation = False
        self.launcher._subject_db_data = None
        self.launcher._subject_info = None

    @patch("aind_behavior_experiment_launcher.launcher.behavior_launcher.model_from_json_file")
    @patch("aind_behavior_experiment_launcher.launcher.behavior_launcher.glob.glob")
    def test_prompt_rig_input(self, mock_glob, mock_model_from_json_file):
        mock_glob.return_value = ["/path/to/rig1.json"]
        mock_model_from_json_file.return_value = MagicMock()
        rig = self.launcher._prompt_rig_input("/path/to/directory")
        self.assertIsNotNone(rig)

    @patch("aind_behavior_experiment_launcher.launcher.behavior_launcher.model_from_json_file")
    @patch("aind_behavior_experiment_launcher.launcher.behavior_launcher.glob.glob")
    def test_prompt_task_logic_input(self, mock_glob, mock_model_from_json_file):
        mock_glob.return_value = ["/path/to/task1.json"]
        mock_model_from_json_file.return_value = MagicMock()
        task_logic = self.launcher._prompt_task_logic_input("/path/to/directory")
        self.assertIsNotNone(task_logic)


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import MagicMock, create_autospec, patch

from aind_behavior_experiment_launcher.launcher.behavior_launcher import (
    BehaviorLauncher,
    BehaviorServicesFactoryManager,
    DefaultBehaviorPicker,
)
from aind_behavior_experiment_launcher.ui import DefaultUIHelper
from tests import suppress_stdout


class TestDefaultPicker(unittest.TestCase):
    def setUp(self):
        self.services_factory_manager = create_autospec(BehaviorServicesFactoryManager)
        self.launcher = BehaviorLauncher(
            rig_schema_model=MagicMock(),
            task_logic_schema_model=MagicMock(),
            session_schema_model=MagicMock(),
            data_dir="/path/to/data",
            config_library_dir="/path/to/config",
            temp_dir="/path/to/temp",
            repository_dir=None,
            allow_dirty=False,
            skip_hardware_validation=False,
            debug_mode=False,
            group_by_subject_log=False,
            services=self.services_factory_manager,
            validate_init=False,
            attached_logger=None,
            picker_factory=lambda x: DefaultBehaviorPicker(
                x, DefaultUIHelper(print_func=MagicMock(), input_func=input)
            ),
        )
        self.picker = self.launcher.picker

    @patch("builtins.input", side_effect=["1"])
    def test_prompt_pick_file_from_list(self, mock_input):
        files = ["file1.txt", "file2.txt"]
        result = self.picker.prompt_pick_file_from_list(files)
        self.assertEqual(result, "file1.txt")

    @patch("builtins.input", side_effect=["0", "manual_entry"])
    def test_prompt_pick_file_from_list_manual_entry(self, mock_input):
        files = ["file1.txt", "file2.txt"]
        result = self.picker.prompt_pick_file_from_list(files, zero_label="Manual Entry", zero_as_input=True)
        self.assertEqual(result, "manual_entry")

    @patch("os.path.isdir", return_value=True)
    @patch("os.listdir", return_value=["subjects/subject1", "subjects/subject2"])
    @patch("builtins.input", side_effect=["1"])
    def test_choose_subject(self, mock_input, mock_listdir, mock_isdir):
        result = self.picker.choose_subject("")
        self.assertEqual(result, "subject1")

    @patch("builtins.input", side_effect=["John Doe"])
    def test_prompt_experimenter(self, mock_input):
        result = self.picker.prompt_experimenter()
        self.assertEqual(result, ["John", "Doe"])

    @patch("aind_behavior_experiment_launcher.launcher.behavior_launcher.model_from_json_file")
    @patch("aind_behavior_experiment_launcher.launcher.behavior_launcher.glob.glob")
    def test_prompt_rig_input(self, mock_glob, mock_model_from_json_file):
        with suppress_stdout():
            mock_glob.return_value = ["/path/to/rig1.json"]
            mock_model_from_json_file.return_value = MagicMock()
            rig = self.picker.pick_rig()
            self.assertIsNotNone(rig)

    @patch("aind_behavior_experiment_launcher.launcher.behavior_launcher.model_from_json_file")
    @patch("aind_behavior_experiment_launcher.launcher.behavior_launcher.glob.glob")
    @patch("os.path.isfile", return_value=True)
    @patch("builtins.input", return_value="1")
    def test_prompt_task_logic_input(self, mock_input, mock_is_file, mock_glob, mock_model_from_json_file):
        with suppress_stdout():
            mock_glob.return_value = ["/path/to/task1.json"]
            mock_model_from_json_file.return_value = MagicMock()
            task_logic = self.picker.pick_task_logic()
            self.assertIsNotNone(task_logic)


if __name__ == "__main__":
    unittest.main()

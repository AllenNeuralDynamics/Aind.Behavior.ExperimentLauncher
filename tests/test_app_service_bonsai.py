import subprocess
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from aind_behavior_experiment_launcher.apps.app_service import BonsaiApp


class TestBonsaiApp(unittest.TestCase):
    def setUp(self):
        self.workflow = Path("test_workflow.bonsai")
        self.executable = Path("bonsai/bonsai.exe")
        self.app = BonsaiApp(workflow=self.workflow, executable=self.executable)

    @patch("aind_behavior_experiment_launcher.apps.app_service.run_bonsai_process")
    @patch("pathlib.Path.exists", return_value=True)
    def test_run(self, mock_pathlib, mock_run_bonsai_process):
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_run_bonsai_process.return_value = mock_result

        result = self.app.run()

        self.assertEqual(result, mock_result)
        self.assertEqual(self.app._result, mock_result)
        mock_run_bonsai_process.assert_called_once_with(
            workflow_file=self.workflow.resolve(),
            bonsai_exe=self.executable.resolve(),
            is_editor_mode=self.app.is_editor_mode,
            is_start_flag=self.app.is_start_flag,
            layout=self.app.layout,
            additional_properties=self.app.additional_properties,
            cwd=self.app.cwd,
            timeout=self.app.timeout,
            print_cmd=self.app.print_cmd,
        )

    def test_validate(self):
        with patch("pathlib.Path.exists", return_value=True):
            self.assertTrue(self.app.validate())

    def test_validate_missing_executable(self):
        with patch("pathlib.Path.exists", side_effect=[False, True, True]):
            with self.assertRaises(FileNotFoundError):
                self.app.validate()

    def test_validate_missing_workflow(self):
        with patch("pathlib.Path.exists", side_effect=[True, False, True]):
            with self.assertRaises(FileNotFoundError):
                self.app.validate()

    def test_validate_missing_layout(self):
        self.app.layout = Path("missing_layout.bonsai.layout")
        with patch("pathlib.Path.exists", side_effect=[True, True, False]):
            with self.assertRaises(FileNotFoundError):
                self.app.validate()

    def test_result_property(self):
        with self.assertRaises(RuntimeError):
            _ = self.app.result

        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        self.app._result = mock_result
        self.assertEqual(self.app.result, mock_result)

    @patch("aind_behavior_experiment_launcher.apps.app_service.UIHelper.prompt_yes_no_question", return_value=True)
    def test_output_from_result(self, mock_prompt):
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.stdout = "output"
        mock_result.stderr = ""
        self.app._result = mock_result

        with patch.object(mock_result, "check_returncode", side_effect=subprocess.CalledProcessError(1, "cmd")):
            with self.assertRaises(subprocess.CalledProcessError):
                self.app.output_from_result(allow_stderr=True)

        with patch.object(mock_result, "check_returncode", return_value=None):
            self.assertEqual(self.app.output_from_result(allow_stderr=True), self.app)

    @patch(
        "aind_behavior_experiment_launcher.apps.app_service.UIHelper.prompt_pick_file_from_list",
        return_value="picked_layout.bonsai.layout",
    )
    def test_prompt_visualizer_layout_input(self, mock_prompt_pick_file_from_list):
        with patch("glob.glob", return_value=["layout1.bonsai.layout", "layout2.bonsai.layout"]):
            layout = self.app.prompt_visualizer_layout_input()
            self.assertEqual(layout, "picked_layout.bonsai.layout")
            self.assertEqual(self.app.layout, "picked_layout.bonsai.layout")

    def test_prompt_input(self):
        with patch.object(self.app, "prompt_visualizer_layout_input", return_value="picked_layout.bonsai.layout"):
            self.app.prompt_input()
            self.assertEqual(self.app.layout, "picked_layout.bonsai.layout")


if __name__ == "__main__":
    unittest.main()

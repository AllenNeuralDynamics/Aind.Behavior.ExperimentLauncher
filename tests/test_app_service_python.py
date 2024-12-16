import subprocess
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from aind_behavior_experiment_launcher.apps import PythonScriptApp


class TestPythonScriptApp(unittest.TestCase):
    def setUp(self):
        self.app = PythonScriptApp(
            script="test_script.py",
            project_directory=Path("/test/project").as_posix(),
            optional_toml_dependencies=["dep1", "dep2"],
            append_python_exe=True,
            timeout=30,
        )

    @patch("subprocess.run")
    def test_create_environment(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        result = self.app.create_environment()
        mock_run.assert_called_once()
        self.assertEqual(result.returncode, 0)

    @patch("subprocess.run")
    @patch("aind_behavior_experiment_launcher.apps.python_script.PythonScriptApp._has_venv", return_value=True)
    def test_run_with_python_exe(self, mock_has_env, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        result = self.app.run()
        mock_run.assert_called_once()
        self.assertEqual(result.returncode, 0)

    @patch("subprocess.run")
    @patch("aind_behavior_experiment_launcher.apps.python_script.PythonScriptApp._has_venv", return_value=True)
    def test_run_without_python_exe(self, mock_has_env, mock_run):
        self.app._append_python_exe = False
        mock_run.return_value = MagicMock(returncode=0)
        result = self.app.run()
        mock_run.assert_called_once()
        self.assertEqual(result.returncode, 0)

    @patch("aind_behavior_experiment_launcher.apps.python_script.PythonScriptApp._log_process_std_output")
    def test_output_from_result_success(self, mock_log):
        mock_log.return_value = None
        self.app._result = subprocess.CompletedProcess(args="test", returncode=0, stdout="output", stderr="")
        result = self.app.output_from_result()
        self.assertEqual(result, self.app)

    @patch("aind_behavior_experiment_launcher.apps.python_script.PythonScriptApp._log_process_std_output")
    def test_output_from_result_failure(self, mock_log):
        mock_log.return_value = None
        self.app._result = subprocess.CompletedProcess(args="test", returncode=1, stdout="output", stderr="error")
        with self.assertRaises(subprocess.CalledProcessError):
            self.app.output_from_result()

    def test_result_property(self):
        with self.assertRaises(RuntimeError):
            _ = self.app.result

    def test_prompt_input(self):
        with self.assertRaises(NotImplementedError):
            self.app.prompt_input()

    def test_add_uv_project_directory(self):
        self.assertEqual(self.app._add_uv_project_directory(), " --directory /test/project")

    def test_add_uv_optional_toml_dependencies(self):
        self.assertEqual(self.app._add_uv_optional_toml_dependencies(), "--extra dep1 --extra dep2")

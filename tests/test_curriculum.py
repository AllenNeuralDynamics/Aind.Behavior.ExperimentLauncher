import unittest
from pathlib import Path

from aind_behavior_curriculum import TrainerState
from semver import Version

from aind_behavior_experiment_launcher.apps import PythonScriptApp
from aind_behavior_experiment_launcher.launcher import git_manager


class TestCurriculumIntegration(unittest.TestCase):
    def setUp(self):
        self.submodule_path = Path(__file__).parents[0] / "assets" / "Aind.Behavior.curriculumTemplate"
        self.repo = git_manager.GitRepository(self.submodule_path)
        self.repo.full_reset().force_update_submodules()

    def test_can_create_venv(self):
        curriculum_app = PythonScriptApp("curriculum", project_directory=self.submodule_path, timeout=20)
        proc = curriculum_app.create_environment()
        proc.check_returncode()

    def test_curriculum_pkg_version(self):
        curriculum_app = PythonScriptApp("curriculum version", project_directory=self.submodule_path, timeout=20)
        curriculum_app.run()
        output = curriculum_app.result.stdout
        self.assertEqual(Version.parse(output), Version.parse("0.0.0"))
        curriculum_app.result.check_returncode()

    def test_curriculum_aind_behavior_curriculum_version(self):
        curriculum_app = PythonScriptApp("curriculum abc-version", project_directory=self.submodule_path, timeout=20)
        curriculum_app.run()
        output = curriculum_app.result.stdout
        Version.parse(output)
        curriculum_app.result.check_returncode()

    def test_curriculum_run(self):
        curriculum_app = PythonScriptApp(
            "curriculum run this_is_not_a_path --skip-upload", project_directory=self.submodule_path, timeout=20
        )
        curriculum_app.run()
        curriculum_app.result.check_returncode()
        output = curriculum_app.result.stdout
        deserialized = TrainerState.model_validate_json(output)
        expected = """
        {
          "stage": {
            "name": "stage_b",
            "task": {
              "name": "TemplateTask",
              "description": "A template task",
              "task_parameters": {
            "example_parameter": 1.0,
            "mode": "bar"
              },
              "version": "0.0.0",
              "stage_name": null
            },
            "graph": {
              "nodes": {},
              "graph": {}
            },
            "start_policies": []
          },
          "is_on_curriculum": true,
          "active_policies": []
        }
        """
        self.assertEqual(deserialized, TrainerState.model_validate_json(expected))


if __name__ == "__main__":
    unittest.main()

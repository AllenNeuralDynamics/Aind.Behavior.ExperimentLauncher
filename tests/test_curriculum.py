import unittest

from aind_behavior_curriculum import Metrics, TrainerState
from semver import Version

from aind_behavior_experiment_launcher.apps import PythonScriptApp
from tests import TESTS_ASSETS, SubmoduleManager

SubmoduleManager.initialize_submodules()


class TestCurriculumIntegration(unittest.TestCase):
    def setUp(self):
        self.submodule_path = TESTS_ASSETS / "Aind.Behavior.curriculumTemplate"

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
            "curriculum run this_is_not_a_path this_is_not_a_path --demo",
            project_directory=self.submodule_path,
            timeout=20,
        )

        curriculum_app.run()
        curriculum_app.result.check_returncode()
        output: str = curriculum_app.result.stdout
        lines = [line.strip() for line in output.strip().split("\n")]
        trainer_state = TrainerState.model_validate_json(lines[0])
        metrics = Metrics.model_validate_json(lines[1])

        with open(TESTS_ASSETS / "expected_curriculum_suggestion.json", "r", encoding="utf-8") as f:
            expected = f.read()
            self.assertEqual(trainer_state, TrainerState.model_validate_json(expected))

        with open(TESTS_ASSETS / "expected_curriculum_metrics.json", "r", encoding="utf-8") as f:
            expected = f.read()
            self.assertEqual(metrics, Metrics.model_validate_json(expected))


if __name__ == "__main__":
    unittest.main()

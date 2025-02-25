import unittest

from aind_behavior_curriculum import TrainerState
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
            "curriculum run this_is_not_a_path --skip-upload", project_directory=self.submodule_path, timeout=20
        )
        curriculum_app.run()
        curriculum_app.result.check_returncode()
        output = curriculum_app.result.stdout
        with open(TESTS_ASSETS / "expected_curriculum_suggestion.json", "r", encoding="utf-8") as f:
            expected = f.read()
        output: str = output.replace("\n", "").strip()
        expected = expected.replace("\n", "").strip()
        deserialized = TrainerState.model_validate_json(output)

        self.assertEqual(deserialized, TrainerState.model_validate_json(expected))
        self.assertEqual(output, expected)


if __name__ == "__main__":
    unittest.main()

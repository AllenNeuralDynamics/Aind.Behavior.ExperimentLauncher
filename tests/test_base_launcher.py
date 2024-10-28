import argparse
import unittest
from pathlib import Path
from unittest.mock import create_autospec, patch

from aind_behavior_services import AindBehaviorRigModel, AindBehaviorSessionModel, AindBehaviorTaskLogicModel

from aind_behavior_experiment_launcher.launcher import BaseLauncher
from aind_behavior_experiment_launcher.services import ServicesFactoryManager


class TestBaseLauncher(unittest.TestCase):
    @patch("aind_behavior_experiment_launcher.launcher.BaseLauncher.validate", return_value=True)
    def setUp(self, mock_validate):
        self.rig_schema_model = create_autospec(AindBehaviorRigModel)
        self.session_schema_model = create_autospec(AindBehaviorSessionModel)
        self.task_logic_schema_model = create_autospec(AindBehaviorTaskLogicModel)
        self.data_dir = Path("/fake/data/dir")
        self.config_library_dir = Path("/fake/config/dir")
        self.temp_dir = Path("/fake/temp/dir")
        self.launcher = BaseLauncher(
            rig_schema_model=self.rig_schema_model,
            session_schema_model=self.session_schema_model,
            task_logic_schema_model=self.task_logic_schema_model,
            data_dir=self.data_dir,
            config_library_dir=self.config_library_dir,
            temp_dir=self.temp_dir,
        )

    def test_init(self):
        self.assertEqual(self.launcher.rig_schema_model, self.rig_schema_model)
        self.assertEqual(self.launcher.session_schema_model, self.session_schema_model)
        self.assertEqual(self.launcher.task_logic_schema_model, self.task_logic_schema_model)
        self.assertEqual(self.launcher.data_dir, self.data_dir.resolve())
        self.assertEqual(self.launcher.config_library_dir, self.config_library_dir.resolve())
        self.assertTrue(self.launcher.temp_dir.exists())

    def test_rig_schema_property(self):
        with self.assertRaises(ValueError):
            _ = self.launcher.rig_schema
        self.launcher._rig_schema = self.rig_schema_model
        self.assertEqual(self.launcher.rig_schema, self.rig_schema_model)

    def test_session_schema_property(self):
        with self.assertRaises(ValueError):
            _ = self.launcher.session_schema
        self.launcher._session_schema = self.session_schema_model
        self.assertEqual(self.launcher.session_schema, self.session_schema_model)

    def test_task_logic_schema_property(self):
        with self.assertRaises(ValueError):
            _ = self.launcher.task_logic_schema
        self.launcher._task_logic_schema = self.task_logic_schema_model
        self.assertEqual(self.launcher.task_logic_schema, self.task_logic_schema_model)

    def test_services_factory_manager_property(self):
        with self.assertRaises(ValueError):
            _ = self.launcher.services_factory_manager
        services_manager = create_autospec(ServicesFactoryManager)
        self.launcher._services_factory_manager = services_manager
        self.assertEqual(self.launcher.services_factory_manager, services_manager)

    @patch("os.makedirs")
    @patch("os.path.exists", return_value=False)
    def test_create_directory(self, mock_path_exists, mock_makedirs):
        directory = Path("/fake/directory")
        BaseLauncher._create_directory(directory)
        mock_makedirs.assert_called_once_with(directory)

    @patch("aind_behavior_experiment_launcher.launcher.BaseLauncher._create_directory")
    @patch("os.path.exists", return_value=False)
    def test_create_directory_structure(self, mock_path_exists, mock_makedirs):
        self.launcher._create_directory_structure()
        mock_makedirs.assert_called()

    @patch("argparse.ArgumentParser.parse_known_args")
    def test_cli_wrapper(self, mock_parse_known_args):
        mock_parse_known_args.return_value = (
            argparse.Namespace(
                data_dir="/fake/data/dir",
                repository_dir=None,
                config_library_dir=None,
                create_directories=False,
                debug=False,
                allow_dirty=False,
                skip_hardware_validation=False,
            ),
            [],
        )
        args = BaseLauncher._cli_wrapper()
        self.assertEqual(args.data_dir, "/fake/data/dir")
        self.assertFalse(args.create_directories)
        self.assertFalse(args.debug)
        self.assertFalse(args.allow_dirty)
        self.assertFalse(args.skip_hardware_validation)

    @patch("argparse.ArgumentParser.parse_known_args")
    def test_cli_args_integration(self, mock_parse_known_args):
        mock_parse_known_args.return_value = (
            argparse.Namespace(
                data_dir="/fake/data/dir",
                repository_dir=None,
                config_library_dir=None,
                create_directories=True,
                debug=True,
                allow_dirty=True,
                skip_hardware_validation=True,
            ),
            [],
        )
        launcher = BaseLauncher(
            rig_schema_model=self.rig_schema_model,
            session_schema_model=self.session_schema_model,
            task_logic_schema_model=self.task_logic_schema_model,
            data_dir=self.data_dir,
            config_library_dir=self.config_library_dir,
            temp_dir=self.temp_dir,
        )
        self.assertTrue(launcher._cli_args.create_directories)
        self.assertTrue(launcher._cli_args.debug)
        self.assertTrue(launcher._cli_args.allow_dirty)
        self.assertTrue(launcher._cli_args.skip_hardware_validation)


if __name__ == "__main__":
    unittest.main()

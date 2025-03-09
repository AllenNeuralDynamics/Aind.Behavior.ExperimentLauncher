import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, create_autospec, patch

from aind_behavior_experiment_launcher.launcher.behavior_launcher import (
    BehaviorLauncher,
    BehaviorServicesFactoryManager,
    BonsaiApp,
    DataMapper,
    DataTransfer,
    ResourceMonitor,
)


class TestBehaviorLauncher(unittest.TestCase):
    def setUp(self):
        self.services_factory_manager = create_autospec(BehaviorServicesFactoryManager)
        self.services_factory_manager.resource_monitor = MagicMock()
        self.services_factory_manager.bonsai_app = MagicMock()
        self.services_factory_manager.data_mapper = MagicMock()
        self.services_factory_manager.data_transfer = MagicMock()

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
            task_logic_schema=None,
        )

    @patch("aind_behavior_experiment_launcher.launcher.behavior_launcher.os.makedirs")
    def test_save_temp_model(self, mock_makedirs):
        model = MagicMock()
        model.__class__.__name__ = "TestModel"
        model.model_dump_json.return_value = '{"key": "value"}'
        path = self.launcher._save_temp_model(model, "/path/to/temp")
        self.assertTrue(path.endswith("TestModel.json"))

    @patch("aind_behavior_experiment_launcher.launcher.behavior_launcher.os.makedirs")
    def test_save_temp_model_default_directory(self, mock_makedirs):
        model = MagicMock()
        model.__class__.__name__ = "TestModel"
        model.model_dump_json.return_value = '{"key": "value"}'
        path = self.launcher._save_temp_model(model, None)
        self.assertTrue(path.endswith("TestModel.json"))

    @patch("aind_behavior_experiment_launcher.launcher.behavior_launcher.os.makedirs")
    def test_save_temp_model_creates_directory(self, mock_makedirs):
        model = MagicMock()
        model.__class__.__name__ = "TestModel"
        model.model_dump_json.return_value = '{"key": "value"}'
        self.launcher._save_temp_model(model, "/path/to/temp")
        mock_makedirs.assert_called_once_with(Path("/path/to/temp"), exist_ok=True)


class TestBehaviorServicesFactoryManager(unittest.TestCase):
    def setUp(self):
        self.launcher = create_autospec(BehaviorLauncher)
        self.factory_manager = BehaviorServicesFactoryManager(self.launcher)

    def test_attach_bonsai_app(self):
        bonsai_app = BonsaiApp("test.bonsai")
        self.factory_manager.attach_bonsai_app(bonsai_app)
        self.assertEqual(self.factory_manager.bonsai_app, bonsai_app)

    def test_attach_data_mapper(self):
        class DataMapperServiceConcrete(DataMapper):
            def map(self):
                return None

            def is_mapped(self):
                return False

            def mapped(self):
                return None

        data_mapper = DataMapperServiceConcrete()
        self.factory_manager.attach_data_mapper(data_mapper)
        self.assertEqual(self.factory_manager.data_mapper, data_mapper)

    def test_attach_resource_monitor(self):
        resource_monitor = ResourceMonitor()
        self.factory_manager.attach_resource_monitor(resource_monitor)
        self.assertEqual(self.factory_manager.resource_monitor, resource_monitor)

    def test_attach_data_transfer(self):
        class DataTransferServiceConcrete(DataTransfer):
            def transfer(self) -> None:
                pass

            def validate(self) -> bool:
                return True

        data_transfer = DataTransferServiceConcrete()
        self.factory_manager.attach_data_transfer(data_transfer)
        self.assertEqual(self.factory_manager.data_transfer, data_transfer)

    def test_validate_service_type(self):
        service = MagicMock()
        validated_service = self.factory_manager._validate_service_type(service, MagicMock)
        self.assertEqual(validated_service, service)

    def test_validate_service_type_invalid(self):
        service = MagicMock()
        with self.assertRaises(ValueError):
            self.factory_manager._validate_service_type(service, str)


class TestBehaviorLauncherSaveTempModel(unittest.TestCase):
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
        )

    @patch("aind_behavior_experiment_launcher.launcher.behavior_launcher.os.makedirs")
    def test_save_temp_model_creates_directory(self, mock_makedirs):
        model = MagicMock()
        model.__class__.__name__ = "TestModel"
        model.model_dump_json.return_value = '{"key": "value"}'
        self.launcher._save_temp_model(model, "/path/to/temp")
        mock_makedirs.assert_called_once_with(Path("/path/to/temp"), exist_ok=True)

    @patch("aind_behavior_experiment_launcher.launcher.behavior_launcher.os.makedirs")
    def test_save_temp_model_default_directory(self, mock_makedirs):
        model = MagicMock()
        model.__class__.__name__ = "TestModel"
        model.model_dump_json.return_value = '{"key": "value"}'
        path = self.launcher._save_temp_model(model, None)
        self.assertTrue(path.endswith("TestModel.json"))

    @patch("aind_behavior_experiment_launcher.launcher.behavior_launcher.os.makedirs")
    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    def test_save_temp_model_returns_correct_path(self, mock_open, mock_makedirs):
        model = MagicMock()
        model.__class__.__name__ = "TestModel"
        model.model_dump_json.return_value = '{"key": "value"}'
        path = self.launcher._save_temp_model(model, Path("/path/to/temp"))
        expected_path = os.path.join(Path("/path/to/temp"), "TestModel.json")
        self.assertEqual(path, expected_path)


if __name__ == "__main__":
    unittest.main()

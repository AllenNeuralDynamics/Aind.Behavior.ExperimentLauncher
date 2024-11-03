import os
import unittest
from datetime import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from aind_data_schema_models.modalities import Modality
from aind_data_schema_models.platforms import Platform
from aind_watchdog_service.models.manifest_config import BucketType

from aind_behavior_experiment_launcher.data_mappers.aind_data_schema import AindDataSchemaSessionDataMapper
from aind_behavior_experiment_launcher.data_transfer.watchdog_service import (
    ManifestConfig,
    WatchConfig,
    WatchdogDataTransferService,
)


class TestWatchdogDataTransferService(unittest.TestCase):
    def setUp(self):
        os.environ["WATCHDOG_EXE"] = "watchdog.exe"
        os.environ["WATCHDOG_CONFIG"] = "watchdog_config.yml"
        self.source = "source_path"
        self.destination = "destination_path"
        self.aind_data_mapper = MagicMock(spec=AindDataSchemaSessionDataMapper)
        self.schedule_time = time(hour=20)
        self.project_name = "test_project"
        self.platform = Platform.BEHAVIOR
        self.capsule_id = "capsule_id"
        self.script = {"script_key": ["script_value"]}
        self.s3_bucket = BucketType.PRIVATE
        self.mount = "mount_path"
        self.force_cloud_sync = True
        self.transfer_endpoint = "http://aind-data-transfer-service/api/v1/submit_jobs"
        self.validate = False

        self.service = WatchdogDataTransferService(
            self.source,
            destination=self.destination,
            aind_session_data_mapper=self.aind_data_mapper,
            schedule_time=self.schedule_time,
            project_name=self.project_name,
            platform=self.platform,
            capsule_id=self.capsule_id,
            script=self.script,
            s3_bucket=self.s3_bucket,
            mount=self.mount,
            force_cloud_sync=self.force_cloud_sync,
            transfer_endpoint=self.transfer_endpoint,
            validate=self.validate,
        )

    def test_initialization(self):
        self.assertEqual(self.service.destination, self.destination)
        self.assertEqual(self.service.project_name, self.project_name)
        self.assertEqual(self.service.schedule_time, self.schedule_time)
        self.assertEqual(self.service.platform, self.platform)
        self.assertEqual(self.service.capsule_id, self.capsule_id)
        self.assertEqual(self.service.script, self.script)
        self.assertEqual(self.service.s3_bucket, self.s3_bucket)
        self.assertEqual(self.service.mount, self.mount)
        self.assertEqual(self.service.force_cloud_sync, self.force_cloud_sync)
        self.assertEqual(self.service.transfer_endpoint, self.transfer_endpoint)

    @patch("aind_behavior_experiment_launcher.data_transfer.watchdog_service.subprocess.check_output")
    def test_is_running(self, mock_check_output):
        mock_check_output.return_value = (
            "Image Name                     PID Session Name        Session#    Mem Usage\n"
            "========================= ======== ================ =========== ============\n"
            "watchdog.exe                1234 Console                    1    10,000 K\n"
        )
        self.assertTrue(self.service.is_running())

    @patch("aind_behavior_experiment_launcher.data_transfer.watchdog_service.subprocess.check_output")
    def test_is_not_running(self, mock_check_output):
        mock_check_output.return_value = "INFO: No tasks are running which match the specified criteria."
        self.assertFalse(self.service.is_running())

    @patch("aind_behavior_experiment_launcher.data_transfer.watchdog_service.requests.get")
    def test_get_project_names(self, mock_get):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.content = '{"data": ["test_project"]}'
        mock_get.return_value = mock_response
        project_names = self.service._get_project_names()
        self.assertIn("test_project", project_names)

    @patch("aind_behavior_experiment_launcher.data_transfer.watchdog_service.requests.get")
    def test_get_project_names_fail(self, mock_get):
        mock_response = MagicMock()
        mock_response.ok = False
        mock_get.return_value = mock_response
        with self.assertRaises(Exception):
            self.service._get_project_names()

    @patch(
        "aind_behavior_experiment_launcher.data_transfer.watchdog_service.WatchdogDataTransferService.is_running",
        return_value=True,
    )
    @patch(
        "aind_behavior_experiment_launcher.data_transfer.watchdog_service.WatchdogDataTransferService.is_valid_project_name",
        return_value=True,
    )
    @patch("aind_behavior_experiment_launcher.data_transfer.watchdog_service.WatchdogDataTransferService._read_yaml")
    def test_validate_success(self, mock_read_yaml, mock_is_valid_project_name, mock_is_running):
        mock_read_yaml.return_value = WatchConfig(
            flag_dir="mock_flag_dir", manifest_complete="manifest_complete_dir"
        ).model_dump()
        with patch.object(Path, "exists", return_value=True):
            self.assertTrue(self.service.validate(create_config=False))

    @patch(
        "aind_behavior_experiment_launcher.data_transfer.watchdog_service.WatchdogDataTransferService.is_running",
        return_value=False,
    )
    def test_validate_fail(self, mock_is_running):
        with patch.object(Path, "exists", return_value=False):
            with self.assertRaises(FileNotFoundError):
                self.service.validate()

    def test_missing_env_variables(self):
        del os.environ["WATCHDOG_EXE"]
        del os.environ["WATCHDOG_CONFIG"]
        with self.assertRaises(ValueError):
            WatchdogDataTransferService(
                self.source,
                destination=self.destination,
                aind_session_data_mapper=self.aind_data_mapper,
                schedule_time=self.schedule_time,
                project_name=self.project_name,
                platform=self.platform,
                capsule_id=self.capsule_id,
                script=self.script,
                s3_bucket=self.s3_bucket,
                mount=self.mount,
                force_cloud_sync=self.force_cloud_sync,
                transfer_endpoint=self.transfer_endpoint,
                validate=self.validate,
            )

    @patch("aind_behavior_experiment_launcher.data_transfer.watchdog_service.Path.exists", return_value=True)
    def test_find_ads_schemas(self, mock_exists):
        # TODO this test should be updated once the corresponding tested method is also updated
        source = "mock_source_path"
        expected_files = [
            Path(source) / "subject.json",
            Path(source) / "data_description.json",
            Path(source) / "procedures.json",
            Path(source) / "session.json",
            Path(source) / "rig.json",
            Path(source) / "processing.json",
            Path(source) / "acquisition.json",
            Path(source) / "instrument.json",
            Path(source) / "quality_control.json",
        ]

        result = WatchdogDataTransferService._find_ads_schemas(source)
        self.assertEqual(result, expected_files)

    @patch("aind_behavior_experiment_launcher.data_transfer.watchdog_service.Path.mkdir")
    @patch("aind_behavior_experiment_launcher.data_transfer.watchdog_service.WatchdogDataTransferService._write_yaml")
    def test_dump_manifest_config(self, mock_write_yaml, mock_mkdir):
        self.service._manifest_config = ManifestConfig(
            name="test_manifest",
            modalities={Modality.BEHAVIOR: ["path/to/modality"]},
            subject_id=1,
            acquisition_datetime="2023-01-01T00:00:00",
            schemas=["path/to/schema"],
            destination="path/to/destination",
            mount="mount_path",
            processor_full_name="processor_name",
            project_name="test_project",
            schedule_time=self.schedule_time,
            platform=Platform.BEHAVIOR,
            capsule_id="capsule_id",
            s3_bucket=BucketType.PRIVATE,
            script={"script_key": ["script_value"]},
            force_cloud_sync=True,
            transfer_endpoint="http://aind-data-transfer-service/api/v1/submit_jobs",
        )
        self.service._watch_config = WatchConfig(
            flag_dir="flag_dir",
            manifest_complete="manifest_complete",
        )

        path = Path("flag_dir/manifest_test_manifest.yaml")
        result = self.service.dump_manifest_config()

        self.assertIsInstance(result, Path)
        self.assertIsInstance(path, Path)
        self.assertEqual(result.resolve(), path.resolve())

        mock_write_yaml.assert_called_once()
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    @patch("aind_behavior_experiment_launcher.data_transfer.watchdog_service.Path.mkdir")
    @patch("aind_behavior_experiment_launcher.data_transfer.watchdog_service.WatchdogDataTransferService._write_yaml")
    def test_dump_manifest_config_custom_path(self, mock_write_yaml, mock_mkdir):
        self.service._manifest_config = ManifestConfig(
            name="test_manifest",
            modalities={Modality.BEHAVIOR: ["path/to/modality"]},
            subject_id=1,
            acquisition_datetime="2023-01-01T00:00:00",
            schemas=["path/to/schema"],
            destination="path/to/destination",
            mount="mount_path",
            processor_full_name="processor_name",
            project_name="test_project",
            schedule_time=self.schedule_time,
            platform=Platform.BEHAVIOR,
            capsule_id="capsule_id",
            s3_bucket=BucketType.PRIVATE,
            script={"script_key": ["script_value"]},
            force_cloud_sync=True,
            transfer_endpoint="http://aind-data-transfer-service/api/v1/submit_jobs",
        )
        self.service._watch_config = WatchConfig(
            flag_dir="flag_dir",
            manifest_complete="manifest_complete",
        )

        custom_path = Path("custom_path/manifest_test_manifest.yaml")
        result = self.service.dump_manifest_config(path=custom_path)

        self.assertIsInstance(result, Path)
        self.assertIsInstance(custom_path, Path)
        self.assertEqual(result.resolve(), custom_path.resolve())
        mock_write_yaml.assert_called_once()
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    def test_dump_manifest_config_no_manifest_config(self):
        self.service._manifest_config = None
        self.service._watch_config = WatchConfig(
            flag_dir="flag_dir",
            manifest_complete="manifest_complete",
        )

        with self.assertRaises(ValueError):
            self.service.dump_manifest_config()

    def test_dump_manifest_config_no_watch_config(self):
        self.service._manifest_config = ManifestConfig(
            name="test_manifest",
            modalities={Modality.BEHAVIOR_VIDEOS: ["path/to/modality"]},
            subject_id=1,
            acquisition_datetime="2023-01-01T00:00:00",
            schemas=["path/to/schema"],
            destination="path/to/destination",
            mount="mount_path",
            processor_full_name="processor_name",
            project_name="test_project",
            schedule_time=self.schedule_time,
            platform=Platform.BEHAVIOR,
            capsule_id="capsule_id",
            s3_bucket=BucketType.PRIVATE,
            script={"script_key": ["script_value"]},
            force_cloud_sync=True,
            transfer_endpoint="http://aind-data-transfer-service/api/v1/submit_jobs",
        )
        self.service._watch_config = None

        with self.assertRaises(ValueError):
            self.service.dump_manifest_config()


if __name__ == "__main__":
    unittest.main()

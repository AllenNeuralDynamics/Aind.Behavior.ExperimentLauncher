import os
import unittest
from datetime import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from aind_data_schema_models.platforms import Platform
from aind_watchdog_service.models.manifest_config import BucketType

from aind_behavior_experiment_launcher.data_mappers.aind_data_schema import AindDataSchemaSessionDataMapper
from aind_behavior_experiment_launcher.data_transfer.watchdog_service import WatchConfig, WatchdogDataTransferService


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
            aind_data_mapper=self.aind_data_mapper,
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


if __name__ == "__main__":
    unittest.main()

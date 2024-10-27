import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from aind_behavior_experiment_launcher.data_transfer.robocopy_service import RobocopyService


class TestRobocopyService(unittest.TestCase):
    def setUp(self):
        self.source = "source_path"
        self.destination = "destination_path"
        self.log = "log_path"
        self.extra_args = "/MIR"
        self.service = RobocopyService(
            source=self.source,
            destination=self.destination,
            log=self.log,
            extra_args=self.extra_args,
            delete_src=True,
            overwrite=True,
            force_dir=False,
        )

    def test_initialization(self):
        self.assertEqual(self.service.source, self.source)
        self.assertEqual(self.service.destination, self.destination)
        self.assertEqual(self.service.log, self.log)
        self.assertEqual(self.service.extra_args, self.extra_args)
        self.assertTrue(self.service.delete_src)
        self.assertTrue(self.service.overwrite)
        self.assertFalse(self.service.force_dir)

    @patch("src.aind_behavior_experiment_launcher.data_transfer.robocopy_service.subprocess.Popen")
    def test_transfer(self, mock_popen):
        mock_process = MagicMock()
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process
        self.service.transfer()

    @patch("src.aind_behavior_experiment_launcher.data_transfer.robocopy_service.shutil.which", return_value=None)
    def test_validate_fail(self, mock_which):
        result = self.service.validate()
        self.assertFalse(result)

    @patch("src.aind_behavior_experiment_launcher.data_transfer.robocopy_service.shutil.which", return_value="robocopy")
    def test_validate_success(self, mock_which):
        result = self.service.validate()
        self.assertTrue(result)

    def test_solve_src_dst_mapping_single_path(self):
        result = self.service._solve_src_dst_mapping(self.source, self.destination)
        self.assertEqual(result, {Path(self.source): Path(self.destination)})

    def test_solve_src_dst_mapping_dict(self):
        source_dict = {self.source: self.destination}
        result = self.service._solve_src_dst_mapping(source_dict, None)
        self.assertEqual(result, source_dict)

    def test_solve_src_dst_mapping_invalid(self):
        with self.assertRaises(ValueError):
            self.service._solve_src_dst_mapping(self.source, None)


if __name__ == "__main__":
    unittest.main()

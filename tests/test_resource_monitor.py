import logging
import unittest
import warnings
from shutil import _ntuple_diskusage
from unittest.mock import MagicMock, patch

from aind_behavior_experiment_launcher.resource_monitor.resource_monitor_service import (
    Constraint,
    ResourceMonitor,
    available_storage_constraint_factory,
    remote_dir_exists_constraint_factory,
)


class TestResourceMonitor(unittest.TestCase):
    def setUp(self):
        self.monitor = ResourceMonitor()
        warnings.simplefilter("ignore")
        logging.disable(logging.CRITICAL)

    def test_add_constraint(self):
        constraint = MagicMock(spec=Constraint)
        self.monitor.add_constraint(constraint)
        self.assertIn(constraint, self.monitor.constraints)

    def test_remove_constraint(self):
        constraint = MagicMock(spec=Constraint)
        self.monitor.add_constraint(constraint)
        self.monitor.remove_constraint(constraint)
        self.assertNotIn(constraint, self.monitor.constraints)

    def test_evaluate_constraints_all_pass(self):
        constraint = MagicMock(spec=Constraint)
        constraint.return_value = True
        self.monitor.add_constraint(constraint)
        self.assertTrue(self.monitor.evaluate_constraints())

    def test_evaluate_constraints_one_fails(self):
        constraint1 = MagicMock(spec=Constraint)
        constraint1.return_value = True
        constraint2 = MagicMock(spec=Constraint)
        constraint2.return_value = False
        constraint2.on_fail.return_value = "Constraint failed"
        self.monitor.add_constraint(constraint1)
        self.monitor.add_constraint(constraint2)
        self.assertFalse(self.monitor.evaluate_constraints())

    @patch("shutil.disk_usage")
    def test_available_storage_constraint_factory(self, mock_disk_usage):
        mock_disk_usage.return_value = _ntuple_diskusage(total=500e9, used=100e9, free=400e9)
        constraint = available_storage_constraint_factory(drive="C:\\", min_bytes=2e11)
        self.assertTrue(constraint())
        constraint = available_storage_constraint_factory(drive="C:\\", min_bytes=2e13)
        self.assertFalse(constraint())

    @patch("os.path.exists")
    def test_remote_dir_exists_constraint_factory(self, mock_exists):
        mock_exists.return_value = True
        constraint = remote_dir_exists_constraint_factory(dir_path="/some/remote/dir")
        self.assertTrue(constraint())


if __name__ == "__main__":
    unittest.main()

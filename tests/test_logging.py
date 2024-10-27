import logging
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from aind_behavior_experiment_launcher.logging.logging_helper import default_logger_builder


class TestLoggingHelper(unittest.TestCase):
    def setUp(self):
        self.logger = logging.getLogger("test_logger")
        self.logger.handlers = []  # Clear existing handlers

    def test_default_logger_builder_no_output_path(self):
        logger = default_logger_builder(self.logger, None)
        self.assertEqual(logger.level, logging.INFO)
        self.assertEqual(len(logger.handlers), 1)
        self.assertIsInstance(logger.handlers[0], logging.StreamHandler)

    @patch("logging.FileHandler")
    def test_default_logger_builder_with_output_path(self, mock_file_handler):
        mock_file_handler_instance = MagicMock()
        mock_file_handler.return_value = mock_file_handler_instance

        output_path = Path("/fake/path/to/logfile.log")
        logger = default_logger_builder(self.logger, output_path)

        self.assertEqual(logger.level, logging.INFO)
        self.assertEqual(len(logger.handlers), 2)
        self.assertIsInstance(logger.handlers[0], logging.StreamHandler)
        self.assertEqual(logger.handlers[1], mock_file_handler_instance)
        mock_file_handler.assert_called_once_with(output_path, encoding="utf-8", mode="w")


if __name__ == "__main__":
    unittest.main()

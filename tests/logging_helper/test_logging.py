import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from clabe.logging_helper import add_file_handler


@pytest.fixture
def logger():
    test_logger = logging.getLogger("test_logger")
    test_logger.handlers = []  # Clear existing handlers
    return test_logger


class TestLoggingHelper:
    @patch("logging.FileHandler")
    def test_default_logger_builder_with_output_path(self, mock_file_handler, logger):
        mock_file_handler_instance = MagicMock()
        mock_file_handler.return_value = mock_file_handler_instance

        output_path = Path("/tmp/fake/path/to/logfile.log")
        result_logger = add_file_handler(logger, output_path)

        assert len(result_logger.handlers) == 1
        assert result_logger.handlers[0] == mock_file_handler_instance
        mock_file_handler.assert_called_once_with(output_path, encoding="utf-8", mode="w")

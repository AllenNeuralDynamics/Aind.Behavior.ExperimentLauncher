import datetime
import logging
import os
from pathlib import Path
from typing import TypeVar

import aind_behavior_services.utils as utils

from aind_behavior_experiment_launcher import fmt

TLogger = TypeVar("TLogger", bound=logging.Logger)


class _TzFormatter(logging.Formatter):
    """
    A custom logging formatter that supports timezone-aware timestamps.

    Attributes:
        _tz: The timezone to use for formatting timestamps.
    """

    def __init__(self, *args, **kwargs):
        """
        Initializes the formatter with optional timezone information.

        Args:
            *args: Positional arguments for the base Formatter class.
            **kwargs: Keyword arguments for the base Formatter class.
                      The 'tz' keyword can be used to specify a timezone.
        """
        self._tz = kwargs.pop("tz", None)
        super().__init__(*args, **kwargs)

    def formatTime(self, record, datefmt=None) -> str:
        """
        Formats the time of a log record using the specified timezone.

        Args:
            record: The log record to format.
            datefmt: An optional date format string.

        Returns:
            A string representation of the formatted time.
        """
        record_time = datetime.datetime.fromtimestamp(record.created, tz=self._tz)
        return utils.format_datetime(record_time)


utc_formatter = _TzFormatter(fmt, tz=datetime.timezone.utc)


def add_file_logger(logger: TLogger, output_path: os.PathLike) -> TLogger:
    """
    Adds a file handler to the logger to write logs to a file.

    Args:
        logger: The logger to which the file handler will be added.
        output_path: The path to the log file.

    Returns:
        The logger with the added file handler.
    """
    file_handler = logging.FileHandler(Path(output_path), encoding="utf-8", mode="w")
    file_handler.setFormatter(utc_formatter)
    logger.addHandler(file_handler)
    return logger


def shutdown_logger(logger: TLogger) -> None:
    """
    Shuts down the logger by closing all file handlers and calling logging.shutdown().

    Args:
        logger: The logger to shut down.
    """
    close_file_handlers(logger)
    logging.shutdown()


def close_file_handlers(logger: TLogger) -> TLogger:
    """
    Closes all file handlers associated with the logger.

    Args:
        logger: The logger whose file handlers will be closed.

    Returns:
        The logger with closed file handlers.
    """
    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler):
            handler.close()
    return logger

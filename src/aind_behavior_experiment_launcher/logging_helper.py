import datetime
import logging
import os
from pathlib import Path
from typing import TypeVar

import aind_behavior_services.utils as utils

from aind_behavior_experiment_launcher import fmt

TLogger = TypeVar("TLogger", bound=logging.Logger)


class _TzFormatter(logging.Formatter):
    def __init__(self, *args, **kwargs):
        self._tz = kwargs.pop("tz", None)
        super().__init__(*args, **kwargs)

    def formatTime(self, record, datefmt=None) -> str:
        record_time = datetime.datetime.fromtimestamp(record.created, tz=self._tz)
        return utils.format_datetime(record_time)


utc_formatter = _TzFormatter(fmt, tz=datetime.timezone.utc)


def add_file_logger(logger: TLogger, output_path: os.PathLike) -> TLogger:
    file_handler = logging.FileHandler(Path(output_path), encoding="utf-8", mode="w")
    file_handler.setFormatter(utc_formatter)
    logger.addHandler(file_handler)
    return logger


def shutdown_logger(logger: TLogger) -> None:
    close_file_handlers(logger)
    logging.shutdown()


def close_file_handlers(logger: TLogger) -> TLogger:
    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler):
            handler.close()
    return logger

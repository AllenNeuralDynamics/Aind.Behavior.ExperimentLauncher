import logging
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("aind-clabe")
except PackageNotFoundError:
    __version__ = "0.0.0"

logger = logging.getLogger(__name__)

from .logging import configure_console_logging

configure_console_logging()

__version__ = "0.4.2"

import logging
import logging.config

import rich.logging
from rich.highlighter import NullHighlighter

logger = logging.getLogger(__name__)

fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

logging.basicConfig(
    level=logging.INFO,
    format=fmt,
    datefmt="%Y-%m-%dT%H%M%S%z",
    handlers=[rich.logging.RichHandler(rich_tracebacks=True, show_time=False, highlighter=NullHighlighter())],
)

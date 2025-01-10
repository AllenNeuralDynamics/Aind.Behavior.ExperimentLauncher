__version__ = "0.3.0"

import logging
import logging.config

logger = logging.getLogger(__name__)

fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

logging.basicConfig(level=logging.INFO, format=fmt, datefmt="%Y-%m-%dT%H%M%S%z")

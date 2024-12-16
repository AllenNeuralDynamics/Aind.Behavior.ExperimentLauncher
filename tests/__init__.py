import contextlib
import glob
import importlib.util
import io
import logging
import os
import sys
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).parents[1]

EXAMPLES_DIR = REPO_ROOT / "examples"
TESTS_ASSETS = REPO_ROOT / "tests" / "assets"

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
logging.disable(logging.CRITICAL)
os.environ["WATCHDOG_EXE"] = "watchdog.exe"
os.environ["WATCHDOG_CONFIG"] = "watchdog_config.yml"


def build_example(script_path: str) -> ModuleType:
    module_name = Path(script_path).stem
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None:
        raise ImportError(f"Can't find {script_path}")
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise ImportError(f"Can't load {script_path}")
    spec.loader.exec_module(module)
    return module


def build_examples(examples_dir: Path = EXAMPLES_DIR):
    for script_path in glob.glob(str(examples_dir / "*.py")):
        _ = build_example(script_path)


@contextlib.contextmanager
def suppress_stdout():
    original_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        yield
    finally:
        sys.stdout = original_stdout

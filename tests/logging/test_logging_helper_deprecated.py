"""``clabe.logging_helper`` is a deprecated alias for :mod:`clabe.logging`."""

import importlib
import sys

import pytest


def test_logging_helper_warns_and_reexports():
    """Importing the alias warns and exposes the same objects as ``clabe.logging``."""
    sys.modules.pop("clabe.logging_helper", None)

    with pytest.deprecated_call():
        logging_helper = importlib.import_module("clabe.logging_helper")

    import clabe.logging as clabe_logging

    assert logging_helper.add_file_handler is clabe_logging.add_file_handler
    assert logging_helper.clabe_console is clabe_logging.clabe_console

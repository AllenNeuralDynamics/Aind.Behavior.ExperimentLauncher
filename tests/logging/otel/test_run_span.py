"""Tests for the span-name resolution order in run_span()."""

from unittest.mock import MagicMock, patch

import clabe.logging.otel as otel_mod


def _make_settings(run_name=None):
    settings = MagicMock()
    settings.enabled = False  # skip SDK configure()
    settings.run_name = run_name
    return settings


def _captured_span_name(experiment_name, settings):
    """Run run_span() with mocked OTEL and return the name passed to start_span."""
    captured = {}

    def fake_start_span(name):
        captured["name"] = name
        return MagicMock()

    with (
        patch.object(otel_mod, "_tracer", MagicMock(start_span=fake_start_span)),
        patch("clabe.logging.otel.AindOtelSettings", return_value=settings),
    ):
        launcher = MagicMock()
        with otel_mod.run_span(launcher, experiment_name=experiment_name):
            pass

    return captured["name"]


# --- resolution order ---


def test_run_name_takes_precedence_over_experiment_name():
    """Explicit run_name in config beats the experiment callable's name."""
    settings = _make_settings(run_name="config_name")
    assert _captured_span_name("callable_name", settings) == "config_name"


def test_experiment_name_used_when_run_name_absent():
    """Experiment callable's name is used when run_name is None."""
    settings = _make_settings(run_name=None)
    assert _captured_span_name("callable_name", settings) == "callable_name"


def test_defaults_to_experiment_when_neither_set():
    """Falls back to 'experiment' when both run_name and experiment_name are absent."""
    settings = _make_settings(run_name=None)
    assert _captured_span_name(None, settings) == "experiment"

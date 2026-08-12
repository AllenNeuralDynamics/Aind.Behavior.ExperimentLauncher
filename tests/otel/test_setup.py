import logging
from unittest.mock import patch

import pytest

from clabe.otel._settings import OtelSettings
from clabe.otel._setup import configure


@pytest.fixture(autouse=True)
def _restore_root_handlers():
    """``configure`` attaches a handler to the root logger; undo that after each test."""
    root = logging.getLogger()
    before = list(root.handlers)
    yield
    for handler in list(root.handlers):
        if handler not in before:
            root.removeHandler(handler)


def test_configure_uses_http_exporter_and_per_signal_paths():
    """Default protocol keeps the pre-existing HTTP behavior: '/v1/traces' and '/v1/logs'."""
    settings = OtelSettings(enabled=True, protocol="http", endpoint="http://collector:4318")

    with (
        patch("opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter") as mock_span_exporter,
        patch("opentelemetry.exporter.otlp.proto.http._log_exporter.OTLPLogExporter") as mock_log_exporter,
        patch("opentelemetry.trace.set_tracer_provider"),
        patch("opentelemetry._logs.set_logger_provider"),
    ):
        configure(settings)

    mock_span_exporter.assert_called_once_with(endpoint="http://collector:4318/v1/traces", headers=None)
    mock_log_exporter.assert_called_once_with(endpoint="http://collector:4318/v1/logs", headers=None)


def test_configure_uses_grpc_exporter_and_raw_endpoint():
    """protocol='grpc' switches exporters, does not append a per-signal path, and passes insecure explicitly."""
    settings = OtelSettings(enabled=True, protocol="grpc", endpoint="collector:4317", insecure=False)

    with (
        patch("opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter") as mock_span_exporter,
        patch("opentelemetry.exporter.otlp.proto.grpc._log_exporter.OTLPLogExporter") as mock_log_exporter,
        patch("opentelemetry.trace.set_tracer_provider"),
        patch("opentelemetry._logs.set_logger_provider"),
    ):
        configure(settings)

    mock_span_exporter.assert_called_once_with(endpoint="collector:4317", headers=None, insecure=False)
    mock_log_exporter.assert_called_once_with(endpoint="collector:4317", headers=None, insecure=False)


def test_configure_forwards_headers():
    settings = OtelSettings(
        enabled=True, protocol="http", endpoint="http://collector:4318", headers={"Authorization": "Bearer x"}
    )

    with (
        patch("opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter") as mock_span_exporter,
        patch("opentelemetry.exporter.otlp.proto.http._log_exporter.OTLPLogExporter"),
        patch("opentelemetry.trace.set_tracer_provider"),
        patch("opentelemetry._logs.set_logger_provider"),
    ):
        configure(settings)

    mock_span_exporter.assert_called_once_with(
        endpoint="http://collector:4318/v1/traces", headers={"Authorization": "Bearer x"}
    )

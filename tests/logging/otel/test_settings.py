import pydantic
import pytest

from clabe.logging.otel import OtelSettings


def test_protocol_defaults_to_grpc():
    settings = OtelSettings()
    assert settings.protocol == "grpc"
    assert settings.endpoint == "localhost:4317"
    assert settings.insecure is True


def test_protocol_accepts_http():
    settings = OtelSettings(protocol="http", endpoint="http://localhost:4318")
    assert settings.protocol == "http"


def test_protocol_rejects_unknown_value():
    with pytest.raises(pydantic.ValidationError):
        OtelSettings(protocol="quic")

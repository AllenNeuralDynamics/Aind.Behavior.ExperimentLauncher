from contextlib import contextmanager
from typing import Generator

from opentelemetry import trace
from opentelemetry.trace import Span, Status, StatusCode
from opentelemetry.util.types import Attributes, AttributeValue

_TRACER_NAME = "clabe.otel"


@contextmanager
def span(name: str, attributes: Attributes = None) -> Generator[Span, None, None]:
    """Open a span nested under the current experiment trace.

    Args:
        name: Name of the span.
        attributes: Optional attributes set when the span starts.

    Yields:
        The started span, so callers can enrich it further.
    """
    with trace.get_tracer(_TRACER_NAME).start_as_current_span(name, attributes=attributes) as current:
        yield current


def event(name: str, attributes: Attributes = None) -> None:
    """Record a timestamped event on the current span."""
    trace.get_current_span().add_event(name, attributes=attributes)


def set_attribute(key: str, value: AttributeValue) -> None:
    """Set a single attribute on the current span."""
    trace.get_current_span().set_attribute(key, value)


def record_exception(exception: BaseException) -> None:
    """Record an exception on the current span and mark it as failed.

    Takes ``BaseException`` so interrupts (``KeyboardInterrupt``), which OTel's own span
    handling skips, can be recorded as failures too.
    """
    current = trace.get_current_span()
    current.record_exception(exception)
    current.set_status(Status(StatusCode.ERROR))

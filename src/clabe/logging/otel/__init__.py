import contextlib
import logging
from collections.abc import Generator
from typing import TYPE_CHECKING

from opentelemetry import trace
from opentelemetry.trace import Span
from opentelemetry.util.types import AttributeValue

from ._api import event, record_exception, set_attribute, span
from ._settings import AindOtelSettings, OtelSettings
from ._setup import merge_attributes, set_attributes

if TYPE_CHECKING:
    from aind_behavior_services.session import Session

    from ...launcher import Launcher

__all__ = [
    "AindOtelSettings",
    "OtelSettings",
    "bind_session",
    "enrich_attribute",
    "event",
    "record_exception",
    "run_span",
    "set_attribute",
    "span",
]

logger = logging.getLogger(__name__)
_tracer = trace.get_tracer("clabe.launcher")
_active_span: Span | None = None
_active_settings: OtelSettings | None = None


@contextlib.contextmanager
def run_span(launcher: "Launcher") -> Generator[Span, None, None]:
    """Instrument a launcher run: install telemetry if enabled, then open the root span.

    Reads :class:`AindOtelSettings` from clabe.yml. When enabled, the SDK is configured
    before the span opens (so ``@runnable`` app spans nest under it) and the OTLP log bridge
    is attached. The run's attribute bag is seeded from the profile's config-and-defaults
    (:meth:`~clabe.logging.otel._settings.OtelSettings.initial_attributes`) before the root span
    starts, so the root span and every child carry it. Telemetry is best effort — a missing
    SDK or bad config is logged and the run proceeds untraced. The span is ended on exit,
    before the caller's cleanup.

    Args:
        launcher: The launcher being instrumented.

    Yields:
        The root span for the run.
    """
    global _active_span, _active_settings
    try:
        settings: OtelSettings | None = AindOtelSettings()
    except Exception:  # observability must never break a run
        logger.warning("Failed to load otel settings; telemetry disabled", exc_info=True)
        settings = None

    if settings is not None and settings.enabled:
        try:
            from ._setup import configure

            configure(settings)
            set_attributes(settings.initial_attributes())
        except Exception:  # observability must never break a run
            logger.warning("Failed to set up telemetry; continuing without it", exc_info=True)

    root = _tracer.start_span(settings.run_name if settings is not None else "experiment")
    _active_span, _active_settings = root, settings
    try:
        with trace.use_span(root, end_on_exit=False):
            yield root
    finally:
        _active_span, _active_settings = None, None
        set_attributes({})
        root.end()


def bind_session(session: "Session") -> None:
    """Enrich the active run with the session identity, as soon as it is registered.

    Called by the launcher from :meth:`~clabe.launcher.Launcher.register_session`, this is
    the first point the session (subject, experimenter, ...) is known — stage 3 of attribute
    population. A no-op outside a run or when telemetry is off.

    Args:
        session: The session model just registered with the launcher.
    """
    if _active_span is None or _active_settings is None:
        return
    try:
        _enrich(_active_settings.session_attributes(session))
    except Exception:  # observability must never break a run
        logger.warning("Failed to bind session identity to telemetry", exc_info=True)


def enrich_attribute(name: str, value: AttributeValue) -> None:
    """Set or override a single telemetry attribute at any point during a run.

    Stage 4 of attribute population: the escape hatch for values that have no dedicated
    config field (e.g. ``instrument_id``) or that become known mid-run. The attribute is
    added to the run's bag — so it appears on every subsequent span and log — and stamped on
    the currently open root span immediately. A no-op outside a run or when telemetry is off.

    Args:
        name: The attribute key, emitted verbatim (use log-schema snake_case, e.g. ``rig_id``).
        value: The attribute value.
    """
    if _active_span is None:
        return
    _enrich({name: value})


def _enrich(attributes: dict[str, AttributeValue]) -> None:
    """Merge attributes into the run's bag and stamp them on the active root span."""
    merge_attributes(attributes)
    if _active_span is not None:
        for key, value in attributes.items():
            _active_span.set_attribute(key, value)

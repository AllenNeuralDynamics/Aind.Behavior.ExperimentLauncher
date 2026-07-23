from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Optional, TypeVar
from urllib.parse import quote

import requests

if TYPE_CHECKING:
    from aind_behavior_services.rig import Rig

    TRig = TypeVar("TRig", bound=Rig)
else:
    TRig = TypeVar("TRig")

logger = logging.getLogger(__name__)

_ACTIVEDIRECTORY_ENDPOINT = "http://aind-metadata-service/api/v2/active_directory"

_RIG_NAME_ENV_VAR = "aibs_comp_id"


def get_aind_rig_name(*, required: bool = False) -> Optional[str]:
    """Return the AIND rig name from the ``aibs_comp_id`` environment variable.

    Single source of truth for reading the rig identifier from the environment; prefer this
    over reading ``aibs_comp_id`` directly so the variable name lives in exactly one place.

    Args:
        required: When True, raise :class:`ValueError` if the variable is unset instead of
            returning ``None``.

    Returns:
        The rig name, or ``None`` if the variable is unset and ``required`` is False.
    """
    rig_name = os.environ.get(_RIG_NAME_ENV_VAR)
    if rig_name is None and required:
        raise ValueError(f"Environment variable '{_RIG_NAME_ENV_VAR}' is not set.")
    return rig_name


def validate_username(
    username: str,
    timeout: Optional[float] = 2,
) -> bool:
    """
    Validates if the given username exists in the AIND Active Directory.

    Queries the AIND metadata service to verify the username exists.
    Returns False (instead of raising) on network errors so callers can
    decide how to handle the degraded state.

    Args:
        username: The username to validate.
        timeout: Timeout in seconds for the HTTP request. Defaults to 2.

    Returns:
        bool: True if the username was found, False otherwise.

    Example:
        ```python
        is_valid = validate_username("j.doe")
        ```
    """
    try:
        response = requests.get(f"{_ACTIVEDIRECTORY_ENDPOINT}/{quote(username, safe='')}", timeout=timeout)
        return response.ok
    except requests.RequestException as e:
        logger.warning("Failed to validate username '%s': %s", username, e)
        return False


def validate_rig_computer_name(rig: TRig) -> TRig:
    """Ensures rig and computer name are set from environment variables if available, otherwise defaults to rig configuration values."""
    rig_name = get_aind_rig_name()
    computer_name = os.environ.get("hostname", None)

    if rig_name is None:
        logger.warning(
            "'%s' environment variable not set. Defaulting to rig name from configuration. %s",
            _RIG_NAME_ENV_VAR,
            rig.rig_name,
        )
        rig_name = rig.rig_name
    if computer_name is None:
        computer_name = rig.computer_name
        logger.warning(
            "'hostname' environment variable not set. Defaulting to computer name from configuration. %s",
            rig.computer_name,
        )

    if rig_name != rig.rig_name or computer_name != rig.computer_name:
        logger.warning(
            "Rig name or computer name from environment variables do not match the rig configuration. "
            "Forcing rig name: %s and computer name: %s from environment variables.",
            rig_name,
            computer_name,
        )
    _rig = rig.model_copy(update={"rig_name": rig_name, "computer_name": computer_name})
    return _rig

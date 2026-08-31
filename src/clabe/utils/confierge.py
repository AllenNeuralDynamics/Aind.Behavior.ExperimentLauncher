import importlib.util

if importlib.util.find_spec("confierge") is None:
    raise ImportError(
        "The 'confierge' package is required to use this module. \
            Install the optional dependencies defined in `project.toml' \
                by running `pip install .[aind-services]`"
    )

from pathlib import Path
from typing import ClassVar, TypeVar

from confierge import Confierge
from pydantic import BaseModel, Field

from ..services import Service, ServiceSettings

_TModel = TypeVar("_TModel", bound=BaseModel)


class ConfiergeSettings(ServiceSettings):
    """
    Settings for the Confierge service.

    Configuration settings for accessing Confierge password databases, supporting
    authentication using both keyfiles and passwords.
    """

    __yml_section__: ClassVar[str] = "confierge"

    base_url: str | None = Field(
        default=None,
        description="Base URL for the Confierge service. If not provided, `FICUS_BASE_URL` environment variable will be used instead.",
    )
    cache_dir: Path | None = Field(
        default=None,
        description="Directory for caching configuration data. If not provided, a default cache directory will be used instead.",
    )
    raise_connection_errors: bool = Field(
        default=False,
        description="Whether to raise connection errors when using Confierge or attempt to resolve via local cache.",
    )
    namespace: str = Field(
        description="Abstract identifier to group config files across scopes. One convention is to make a namespace for the target software that will use the config."
    )


class ConfiergeService(Service):
    """
    Service for interacting with Confierge password databases.

    This service provides methods for accessing and managing configuration data
    stored in Confierge password databases, supporting authentication using both
    keyfiles and passwords.
    """

    _DEFAULT_RIG_SCOPE = "comp_id"
    settings: ConfiergeSettings

    def __init__(self, settings: ConfiergeSettings):
        self._client = Confierge(
            base_url=settings.base_url,
            cache_dir=settings.cache_dir,
            raise_connection_errors=settings.raise_connection_errors,
        )
        self._namespace = settings.namespace

    @property
    def client(self) -> Confierge:
        """
        Get the Confierge client instance.

        Returns:
            Confierge: The Confierge client instance for interacting with the service.
        """
        return self._client

    @property
    def namespace(self) -> str:
        """
        Get the namespace for the Confierge service.

        Returns:
            str: The namespace for grouping config files across scopes.
        """
        return self._namespace

    def get_config(
        self, namespace: str | None = None, mode: str | None = None, scopes: dict[str, str] | None = None
    ) -> dict:
        return self._client.get_config(namespace=namespace or self._namespace, mode=mode, scopes=scopes)

    def get_config_safe(
        self,
        namespace: str | None = None,
        mode: str | None = None,
        scopes: dict[str, str] | None = None,
        model: type[_TModel] | None = None,
    ) -> _TModel | dict:
        return self._client.get_config_safe(
            namespace=namespace or self._namespace, mode=mode, scopes=scopes, model=model
        )

    def get_rig_config_safe(
        self,
        mode: str | None = None,
        additional_scopes: dict[str, str] | None = None,
        model: type[_TModel] | None = None,
    ):
        """Attempts to get the rig config from confierge, falling back to local cache if not available.
        It will infer the namespace and rig names from the existing configuration/environment.
        If additional scopes are provided, they will be added to the `rig_id` scope."""
        from .aind_validators import get_aind_rig_name

        scopes = additional_scopes.copy() if additional_scopes else {}
        scopes[self._DEFAULT_RIG_SCOPE] = get_aind_rig_name(required=True)
        return self.get_config_safe(mode=mode, scopes=scopes, model=model)

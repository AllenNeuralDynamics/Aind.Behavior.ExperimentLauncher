from __future__ import annotations

try:
    import aind_data_schema
except ImportError as _e:
    _e.add_note(
        "The 'aind-data-schema' package is required to use this module. \
            Install the optional dependencies defined in `project.toml' \
                by running `pip install .[aind-services]`"
    )
    raise _e

import abc
import logging
from typing import Generic, TypeVar, Union

import aind_data_schema.components.devices
import aind_data_schema.core.rig
import aind_data_schema.core.session

from . import _base

TAdsObject = TypeVar("TAdsObject", bound=Union[aind_data_schema.core.session.Session, aind_data_schema.core.rig.Rig])

logger = logging.getLogger(__name__)


class AindDataSchemaDataMapper(_base.DataMapper[TAdsObject], abc.ABC, Generic[TAdsObject]):
    @property
    @abc.abstractmethod
    def session_name(self) -> str: ...


class AindDataSchemaSessionDataMapper(AindDataSchemaDataMapper[aind_data_schema.core.session.Session], abc.ABC): ...


class AindDataSchemaRigDataMapper(AindDataSchemaDataMapper[aind_data_schema.core.rig.Rig], abc.ABC): ...

from __future__ import annotations

import importlib.util

if importlib.util.find_spec("aind_data_schema") is None:
    raise ImportError(
        "The 'aind-data-schema' package is required to use this module. "
        "Install the optional dependencies defined in `project.toml` "
        "by running `pip install .[aind-services]`"
    )

import abc
import logging
from typing import Generic, TypeVar, Union

from aind_data_schema.core import rig as ads_rig
from aind_data_schema.core import session as ads_session

from aind_behavior_experiment_launcher.data_mapper import _base

logger = logging.getLogger(__name__)

_TAdsObject = TypeVar("_TAdsObject", bound=Union[ads_session.Session, ads_rig.Rig])


class AindDataSchemaDataMapper(_base.DataMapper[_TAdsObject], abc.ABC, Generic[_TAdsObject]):
    @property
    @abc.abstractmethod
    def session_name(self) -> str: ...


class AindDataSchemaSessionDataMapper(AindDataSchemaDataMapper[ads_session.Session], abc.ABC): ...


class AindDataSchemaRigDataMapper(AindDataSchemaDataMapper[ads_rig.Rig], abc.ABC): ...

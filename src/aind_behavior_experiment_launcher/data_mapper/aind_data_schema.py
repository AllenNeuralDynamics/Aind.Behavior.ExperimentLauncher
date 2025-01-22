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
from typing import Any, Generic, Type, TypeVar, Union

from aind_data_schema.core import rig as ads_rig
from aind_data_schema.core import session as ads_session
from pydantic import BaseModel, create_model, model_validator

from aind_behavior_experiment_launcher.data_mapper import _base

logger = logging.getLogger(__name__)

_TAdsObject = TypeVar("_TAdsObject", bound=Union[ads_session.Session, ads_rig.Rig])


class AindDataSchemaDataMapper(_base.DataMapper[_TAdsObject], abc.ABC, Generic[_TAdsObject]):
    @property
    @abc.abstractmethod
    def session_name(self) -> str: ...


class AindDataSchemaSessionDataMapper(AindDataSchemaDataMapper[ads_session.Session], abc.ABC): ...


class AindDataSchemaRigDataMapper(AindDataSchemaDataMapper[ads_rig.Rig], abc.ABC): ...


_TModel = TypeVar("_TModel", bound=BaseModel)


def create_encoding_model(model: Type[_TModel]) -> Type[_TModel]:
    """Creates a new BaseModel by wrapping the incoming model and adding a Before
    ModelValidator to replace _SPECIAL_CHARACTERS with the unicode, escaped,
    representation"""

    _SPECIAL_CHARACTERS = ".$"

    def _to_unicode_repr(character: str):
        if len(character) != 1:
            raise ValueError(f"Expected a single character, got {character}")
        return f"\\u{ord(character):04x}"

    def _aind_data_schema_encoder(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return _sanitize_dict(data)
        return data

    def _sanitize_dict(value: dict) -> dict:
        if isinstance(value, dict):
            _keys = list(value.keys())
            for key in _keys:
                if isinstance(value[key], dict):
                    value[key] = _sanitize_dict(value[key])
                if isinstance(sanitized_key := key, str):
                    for char in _SPECIAL_CHARACTERS:
                        if char in sanitized_key:
                            sanitized_key = sanitized_key.replace(char, _to_unicode_repr(char))
                    value[sanitized_key] = value.pop(key)
        return value

    return create_model(
        f"_Wrapped{model.__class__.__name__}",
        __base__=model,
        __validators__={
            "encoder": model_validator(mode="before")(_aind_data_schema_encoder)  # type: ignore
        },
    )

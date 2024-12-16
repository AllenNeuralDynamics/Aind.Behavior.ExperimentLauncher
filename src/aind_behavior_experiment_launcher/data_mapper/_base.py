from __future__ import annotations

import abc
import logging
from typing import Any, Generic, Optional, TypeVar

from aind_behavior_experiment_launcher.services import IService

logger = logging.getLogger(__name__)


T = TypeVar("T")

TMapTo = TypeVar("TMapTo", bound=Any)


class DataMapper(IService, abc.ABC, Generic[TMapTo]):
    _mapped: Optional[TMapTo]

    @abc.abstractmethod
    def map(self) -> TMapTo:
        pass

    @abc.abstractmethod
    def is_mapped(self) -> bool: ...

    @property
    @abc.abstractmethod
    def mapped(self) -> TMapTo: ...

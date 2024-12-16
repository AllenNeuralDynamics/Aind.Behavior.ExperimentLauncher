from __future__ import annotations

import abc
import logging

from aind_behavior_experiment_launcher.services import IService

logger = logging.getLogger(__name__)


class DataTransfer(IService, abc.ABC):
    @abc.abstractmethod
    def transfer(self) -> None:
        pass

    @abc.abstractmethod
    def validate(self) -> bool:
        pass

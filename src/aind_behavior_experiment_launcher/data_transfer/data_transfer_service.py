from __future__ import annotations

import abc
import logging
from typing import TypeVar

from aind_behavior_services.session import AindBehaviorSessionModel

from aind_behavior_experiment_launcher.services import IService

logger = logging.getLogger(__name__)

TSession = TypeVar("TSession", bound=AindBehaviorSessionModel)


class DataTransferService(IService, abc.ABC):
    @abc.abstractmethod
    def transfer(self) -> None:
        pass

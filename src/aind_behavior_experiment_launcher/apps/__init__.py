import abc
import logging
import subprocess
from typing import Optional, Self

from aind_behavior_experiment_launcher.services import IService

logger = logging.getLogger(__name__)


class App(IService, abc.ABC):
    @abc.abstractmethod
    def run(self) -> subprocess.CompletedProcess: ...

    @abc.abstractmethod
    def output_from_result(self, allow_stderr: Optional[bool]) -> Self: ...

    @abc.abstractmethod
    def prompt_input(self, *args, **kwargs) -> Self: ...

    @property
    @abc.abstractmethod
    def result(self) -> subprocess.CompletedProcess: ...

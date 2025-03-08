import abc
from typing import Generic, Optional, TypeVar, cast

from aind_behavior_services.rig import AindBehaviorRigModel
from aind_behavior_services.session import AindBehaviorSessionModel
from aind_behavior_services.task_logic import AindBehaviorTaskLogicModel

from aind_behavior_experiment_launcher.launcher import BaseLauncher
from aind_behavior_experiment_launcher.ui_helper import DefaultUIHelper, UiHelperBase

R = TypeVar("R", bound=AindBehaviorRigModel)
S = TypeVar("S", bound=AindBehaviorSessionModel)
T = TypeVar("T", bound=AindBehaviorTaskLogicModel)


class PickerBase(abc.ABC, Generic[R, S, T]):
    def __init__(self, launcher: BaseLauncher[R, S, T], ui_helper: Optional[UiHelperBase] = None) -> None:
        self._launcher = launcher
        _ui_helper = ui_helper
        if _ui_helper is None:
            _ui_helper = DefaultUIHelper()
        self._ui_helper = _ui_helper

    @property
    def launcher(self) -> BaseLauncher[R, S, T]:
        return self._launcher

    @property
    def ui_helper(self) -> UiHelperBase:
        return self._ui_helper

    @abc.abstractmethod
    def pick_rig(self) -> R:
        ...

    @abc.abstractmethod
    def pick_session(self) -> S:
        ...

    @abc.abstractmethod
    def pick_task_logic(self) -> T:
        ...


class DefaultPicker(PickerBase[R, S, T]):
    """Default picker implementation. This is just to make other abstract classes happy. """
    def pick_rig(self) -> R:
        raise NotImplementedError("pick_rig method is not implemented")

    def pick_session(self) -> S:
        raise NotImplementedError("pick_session method is not implemented")

    def pick_task_logic(self) -> T:
        raise NotImplementedError("pick_task_logic method is not implemented")


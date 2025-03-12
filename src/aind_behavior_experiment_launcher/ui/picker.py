import abc
from typing import TYPE_CHECKING, Generic, Optional, Self, TypeVar

from aind_behavior_services.rig import AindBehaviorRigModel
from aind_behavior_services.session import AindBehaviorSessionModel
from aind_behavior_services.task_logic import AindBehaviorTaskLogicModel

from .ui_helper import _UiHelperBase

if TYPE_CHECKING:
    from aind_behavior_experiment_launcher.launcher import BaseLauncher
else:
    BaseLauncher = "BaseLauncher"

_L = TypeVar("_L", bound=BaseLauncher)
_R = TypeVar("_R", bound=AindBehaviorRigModel)
_S = TypeVar("_S", bound=AindBehaviorSessionModel)
_T = TypeVar("_T", bound=AindBehaviorTaskLogicModel)


class PickerBase(abc.ABC, Generic[_L, _R, _S, _T]):
    def __init__(self, launcher: Optional[_L] = None, *, ui_helper: Optional[_UiHelperBase] = None, **kwargs) -> None:
        self._launcher = launcher
        self._ui_helper = ui_helper

    def register_launcher(self, launcher: _L) -> Self:
        if self._launcher is None:
            self._launcher = launcher
        else:
            raise ValueError("Launcher is already registered")
        return self

    @property
    def has_launcher(self) -> bool:
        return self._launcher is not None

    def register_ui_helper(self, ui_helper: _UiHelperBase) -> Self:
        if self._ui_helper is None:
            self._ui_helper = ui_helper
        else:
            raise ValueError("UI Helper is already registered")
        return self

    @property
    def has_ui_helper(self) -> bool:
        return self._ui_helper is not None

    @property
    def launcher(self) -> _L:
        if self._launcher is None:
            raise ValueError("Launcher is not registered")
        return self._launcher

    @property
    def ui_helper(self) -> _UiHelperBase:
        if self._ui_helper is None:
            raise ValueError("UI Helper is not registered")
        return self._ui_helper

    @abc.abstractmethod
    def pick_rig(self) -> _R: ...

    @abc.abstractmethod
    def pick_session(self) -> _S: ...

    @abc.abstractmethod
    def pick_task_logic(self) -> _T: ...

    @abc.abstractmethod
    def initialize(self) -> None: ...


class DefaultPicker(PickerBase[_L, _R, _S, _T]):
    """Default picker implementation. This is just to make other abstract classes happy."""

    def pick_rig(self) -> _R:
        raise NotImplementedError("pick_rig method is not implemented")

    def pick_session(self) -> _S:
        raise NotImplementedError("pick_session method is not implemented")

    def pick_task_logic(self) -> _T:
        raise NotImplementedError("pick_task_logic method is not implemented")

    def initialize(self) -> None:
        return

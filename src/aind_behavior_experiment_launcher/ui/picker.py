import abc
from typing import TYPE_CHECKING, Generic, Optional, TypeVar

from aind_behavior_services.rig import AindBehaviorRigModel
from aind_behavior_services.session import AindBehaviorSessionModel
from aind_behavior_services.task_logic import AindBehaviorTaskLogicModel

from .ui_helper import DefaultUIHelper, _UiHelperBase

if TYPE_CHECKING:
    from aind_behavior_experiment_launcher.launcher import BaseLauncher
else:
    BaseLauncher = "BaseLauncher"

_L = TypeVar("_L", bound=BaseLauncher)
_R = TypeVar("_R", bound=AindBehaviorRigModel)
_S = TypeVar("_S", bound=AindBehaviorSessionModel)
_T = TypeVar("_T", bound=AindBehaviorTaskLogicModel)


class PickerBase(abc.ABC, Generic[_L, _R, _S, _T]):
    def __init__(self, launcher: _L, ui_helper: Optional[_UiHelperBase] = None) -> None:
        self._launcher = launcher
        _ui_helper = ui_helper
        if _ui_helper is None:
            _ui_helper = DefaultUIHelper()
        self._ui_helper = _ui_helper

    @property
    def launcher(self) -> _L:
        return self._launcher

    @property
    def ui_helper(self) -> _UiHelperBase:
        return self._ui_helper

    @abc.abstractmethod
    def pick_rig(self) -> _R: ...

    @abc.abstractmethod
    def pick_session(self) -> _S: ...

    @abc.abstractmethod
    def pick_task_logic(self) -> _T: ...


class DefaultPicker(PickerBase[_L, _R, _S, _T]):
    """Default picker implementation. This is just to make other abstract classes happy."""

    def pick_rig(self) -> _R:
        raise NotImplementedError("pick_rig method is not implemented")

    def pick_session(self) -> _S:
        raise NotImplementedError("pick_session method is not implemented")

    def pick_task_logic(self) -> _T:
        raise NotImplementedError("pick_task_logic method is not implemented")

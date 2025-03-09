import abc
from typing import TYPE_CHECKING, Generic, Optional, TypeVar

from .ui_helper import DefaultUIHelper, _UiHelperBase

if TYPE_CHECKING:
    from aind_behavior_experiment_launcher.launcher import BaseLauncher
else:
    BaseLauncher = "BaseLauncher"

_L = TypeVar("_L", bound=BaseLauncher)


class PickerBase(abc.ABC, Generic[_L]):
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
    def pick_rig(self): ...

    @abc.abstractmethod
    def pick_session(self): ...

    @abc.abstractmethod
    def pick_task_logic(self): ...


class DefaultPicker(PickerBase[_L]):
    """Default picker implementation. This is just to make other abstract classes happy."""

    def pick_rig(self):
        raise NotImplementedError("pick_rig method is not implemented")

    def pick_session(self):
        raise NotImplementedError("pick_session method is not implemented")

    def pick_task_logic(self):
        raise NotImplementedError("pick_task_logic method is not implemented")

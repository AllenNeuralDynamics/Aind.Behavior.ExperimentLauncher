import abc
import logging
from typing import TYPE_CHECKING, Any, Callable, Generic, List, Optional, TypeVar

from pydantic import BaseModel, TypeAdapter

if TYPE_CHECKING:
    from aind_behavior_experiment_launcher.launcher import BaseLauncher
else:
    BaseLauncher = "BaseLauncher"

logger = logging.getLogger(__name__)

_PrintFunc = Callable[[str], Any]
_InputFunc = Callable[[str], str]
_DEFAULT_PRINT_FUNC: _PrintFunc = print
_DEFAULT_INPUT_FUNC: _InputFunc = input
_T = TypeVar("_T", bound=Any)
_L = TypeVar("_L", bound=BaseLauncher)
_TModel = TypeVar("_TModel", bound=BaseModel)


class UiHelperBase(abc.ABC):
    _print: _PrintFunc
    _input: _InputFunc

    def __init__(
        self, *args, print_func: Optional[_PrintFunc] = None, input_func: Optional[_PrintFunc] = None, **kwargs
    ):
        self._print = print_func if print_func is not None else _DEFAULT_PRINT_FUNC
        self._input = input_func if input_func is not None else _DEFAULT_INPUT_FUNC

    def print(self, message: str) -> Any:
        return self._print(message)

    def input(self, prompt: str) -> str:
        return self._input(prompt)

    @abc.abstractmethod
    def prompt_pick_from_list(self, value: List[str], prompt: str, **kwargs) -> Optional[str]: ...

    @abc.abstractmethod
    def prompt_yes_no_question(self, prompt: str) -> bool: ...

    @abc.abstractmethod
    def prompt_text(self, prompt: str) -> str: ...


UiHelper = UiHelperBase


class PickerBase(abc.ABC, Generic[_L]):
    def __init__(self, launcher: _L, ui_helper: Optional[UiHelperBase] = None) -> None:
        self._launcher = launcher
        _ui_helper = ui_helper
        if _ui_helper is None:
            _ui_helper = DefaultUIHelper()
        self._ui_helper = _ui_helper

    @property
    def launcher(self) -> _L:
        return self._launcher

    @property
    def ui_helper(self) -> UiHelperBase:
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


class DefaultUIHelper(UiHelperBase):
    def prompt_pick_from_list(
        self, value: List[str], prompt: str, allow_0_as_none: bool = True, **kwargs
    ) -> Optional[str]:
        while True:
            try:
                self.print(prompt)
                if allow_0_as_none:
                    self.print("0: None")
                for i, item in enumerate(value):
                    self.print(f"{i + 1}: {item}")
                choice = int(input("Choice: "))
                if choice < 0 or choice >= len(value) + 1:
                    raise ValueError
                if choice == 0:
                    if allow_0_as_none:
                        return None
                    else:
                        raise ValueError
                return value[choice - 1]
            except ValueError as e:
                logger.error("Invalid choice. Try again. %s", e)

    def prompt_yes_no_question(self, prompt: str) -> bool:
        while True:
            reply = input(prompt + " (Y\\N): ").upper()
            if reply == "Y" or reply == "1":
                return True
            elif reply == "N" or reply == "0":
                return False
            else:
                self.print("Invalid input. Please enter 'Y' or 'N'.")

    def prompt_text(self, prompt: str) -> str:
        notes = str(input(prompt))
        return notes


def prompt_field_from_input(model: _TModel, field_name: str, default: Optional[_T] = None) -> Optional[_T]:
    _field = model.model_fields[field_name]
    _type_adaptor: TypeAdapter = TypeAdapter(_field.annotation)
    value: Optional[_T] | str
    _in = input(f"Enter {field_name} ({_field.description}): ")
    value = _in if _in != "" else default
    return _type_adaptor.validate_python(value)

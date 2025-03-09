import abc
import logging
from typing import Any, Callable, List, Optional, TypeVar

logger = logging.getLogger(__name__)

_PrintFunc = Callable[[str], Any]
_InputFunc = Callable[[str], str]
_DEFAULT_PRINT_FUNC: _PrintFunc = print
_DEFAULT_INPUT_FUNC: _InputFunc = input
T = TypeVar("T", bound=Any)


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

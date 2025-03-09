import logging
import os
from typing import Any, List, Optional, TypeVar

from pydantic import BaseModel, TypeAdapter

from ._base import UiHelperBase

logger = logging.getLogger(__name__)

_T = TypeVar("_T", bound=Any)


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


_TModel = TypeVar("TModel", bound=BaseModel)


def prompt_field_from_input(model: _TModel, field_name: str, default: Optional[_T] = None) -> Optional[_T]:
    _field = model.model_fields[field_name]
    _type_adaptor: TypeAdapter = TypeAdapter(_field.annotation)
    value: Optional[_T] | str
    _in = input(f"Enter {field_name} ({_field.description}): ")
    value = _in if _in != "" else default
    return _type_adaptor.validate_python(value)

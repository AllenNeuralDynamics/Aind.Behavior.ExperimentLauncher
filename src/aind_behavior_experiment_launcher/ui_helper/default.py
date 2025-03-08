import logging
import os
from typing import Any, List, Optional, TypeVar

from pydantic import BaseModel, TypeAdapter

from ._base import UiHelperBase

logger = logging.getLogger(__name__)

_T = TypeVar("_T", bound=Any)


class DefaultUIHelper(UiHelperBase):
    def prompt_pick_file_from_list(
        self,
        available_files: list[str],
        prompt: str = "Choose a file:",
        zero_label: Optional[str] = None,
        zero_value: Optional[_T] = None,
        zero_as_input: bool = True,
        zero_as_input_label: str = "Enter manually",
    ) -> Optional[str | _T]:
        self.print(prompt)
        if zero_label is not None:
            self.print(f"0: {zero_label}")
        for i, file in enumerate(available_files):
            self.print(f"{i + 1}: {os.path.split(file)[1]}")
        choice = int(input("Choice: "))
        if choice < 0 or choice >= len(available_files) + 1:
            raise ValueError
        if choice == 0:
            if zero_label is None:
                raise ValueError
            else:
                if zero_as_input:
                    return str(input(zero_as_input_label))
                else:
                    return zero_value
        else:
            return available_files[choice - 1]

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

    def choose_subject(self, directory: str | os.PathLike) -> str:
        subject = None
        while subject is None:
            subject = self.prompt_pick_from_list(
                [
                    os.path.basename(folder)
                    for folder in os.listdir(directory)
                    if os.path.isdir(os.path.join(directory, folder))
                ],
                prompt="Choose a subject:",
                allow_0_as_none=True,
            )
            if subject is None:
                subject = input("Enter subject name manually: ")
                if subject == "":
                    logger.error("Subject name cannot be empty.")
                    subject = None
        return subject

    def prompt_experimenter(self, strict: bool = True) -> Optional[List[str]]:
        experimenter: Optional[List[str]] = None
        while experimenter is None:
            _user_input = self.prompt_text("Experimenter name: ")
            experimenter = _user_input.replace(",", " ").split()
            if strict & (len(experimenter) == 0):
                logger.error("Experimenter name is not valid.")
                experimenter = None
            else:
                return experimenter
        return experimenter  # This line should be unreachable

    def prompt_notes(self) -> str:
        return self.prompt_text("Enter notes: ")

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

import logging
import os
from typing import Any, Callable, List, Optional, TypeVar

from aind_behavior_services.db_utils import SubjectDataBase
from aind_behavior_services.rig import AindBehaviorRigModel
from aind_behavior_services.session import AindBehaviorSessionModel
from aind_behavior_services.task_logic import AindBehaviorTaskLogicModel
from pydantic import BaseModel, TypeAdapter

logger = logging.getLogger(__name__)


class UIHelper:
    _print: Callable[[str], None]

    def __init__(self, print_func: Callable[[str], None] = print):
        self._print = print_func

    T = TypeVar("T", bound=Any)

    def prompt_pick_file_from_list(
        self,
        available_files: list[str],
        prompt: str = "Choose a file:",
        zero_label: Optional[str] = None,
        zero_value: Optional[T] = None,
        zero_as_input: bool = True,
        zero_as_input_label: str = "Enter manually",
    ) -> Optional[str | T]:
        self._print(prompt)
        if zero_label is not None:
            self._print(f"0: {zero_label}")
        for i, file in enumerate(available_files):
            self._print(f"{i+1}: {os.path.split(file)[1]}")
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

    def prompt_yes_no_question(self, prompt: str) -> bool:
        while True:
            reply = input(prompt + " (Y\\N): ").upper()
            if reply == "Y" or reply == "1":
                return True
            elif reply == "N" or reply == "0":
                return False
            else:
                self._print("Invalid input. Please enter 'Y' or 'N'.")

    def choose_subject(self, subject_list: SubjectDataBase) -> str:
        subject = None
        while subject is None:
            try:
                subject = self.prompt_pick_file_from_list(
                    list(subject_list.subjects.keys()), prompt="Choose a subject:", zero_label=None
                )
                if not isinstance(subject, str):
                    raise ValueError("Return value is not a string type.")
            except ValueError as e:
                logger.error("Invalid choice. Try again. %s", e)
        return subject

    @staticmethod
    def prompt_experimenter(strict: bool = True) -> Optional[List[str]]:
        experimenter: Optional[List[str]] = None
        while experimenter is None:
            _user_input = input("Experimenter name: ")
            experimenter = _user_input.replace(",", " ").split()
            if strict & (len(experimenter) == 0):
                logger.error("Experimenter name is not valid.")
                experimenter = None
            else:
                return experimenter
        return experimenter  # This line should be unreachable

    @staticmethod
    def prompt_get_notes() -> str:
        notes = str(input("Enter notes:"))
        return notes

    def make_header(
        self,
        task_logic_schema_model: type[AindBehaviorTaskLogicModel],
        rig_schema_model: type[AindBehaviorRigModel],
        session_schema_model: type[AindBehaviorSessionModel],
    ) -> str:
        _HEADER = r"""

        ██████╗██╗      █████╗ ██████╗ ███████╗
        ██╔════╝██║     ██╔══██╗██╔══██╗██╔════╝
        ██║     ██║     ███████║██████╔╝█████╗
        ██║     ██║     ██╔══██║██╔══██╗██╔══╝
        ╚██████╗███████╗██║  ██║██████╔╝███████╗
        ╚═════╝╚══════╝╚═╝  ╚═╝╚═════╝ ╚══════╝

        Command-line-interface Launcher for AIND Behavior Experiments
        Press Control+C to exit at any time.
        """

        _str = (
            "-------------------------------\n"
            f"{_HEADER}\n"
            f"TaskLogic ({task_logic_schema_model.__name__}) Schema Version: {task_logic_schema_model.model_construct().version}\n"
            f"Rig ({rig_schema_model.__name__}) Schema Version: {rig_schema_model.model_construct().version}\n"
            f"Session ({session_schema_model.__name__}) Schema Version: {session_schema_model.model_construct().version}\n"
            "-------------------------------"
        )

        return _str


TModel = TypeVar("TModel", bound=BaseModel)

T = TypeVar("T", bound=Any)


def prompt_field_from_input(model: TModel, field_name: str, default: Optional[T] = None) -> Optional[T]:
    _field = model.model_fields[field_name]
    _type_adaptor: TypeAdapter = TypeAdapter(_field.annotation)
    value: Optional[T] | str
    _in = input(f"Enter {field_name} ({_field.description}): ")
    value = _in if _in != "" else default
    return _type_adaptor.validate_python(value)

from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Generic, Optional, Self, Type, TypeVar

import pydantic
from aind_behavior_services import (
    AindBehaviorRigModel,
    AindBehaviorSessionModel,
    AindBehaviorTaskLogicModel,
)
from aind_behavior_services.utils import format_datetime, model_from_json_file, utcnow

from aind_behavior_experiment_launcher import logging_helper, ui_helper
from aind_behavior_experiment_launcher.services import ServicesFactoryManager

from .git_manager import GitRepository

TRig = TypeVar("TRig", bound=AindBehaviorRigModel)  # pylint: disable=invalid-name
TSession = TypeVar("TSession", bound=AindBehaviorSessionModel)  # pylint: disable=invalid-name
TTaskLogic = TypeVar("TTaskLogic", bound=AindBehaviorTaskLogicModel)  # pylint: disable=invalid-name

TModel = TypeVar("TModel", bound=pydantic.BaseModel)  # pylint: disable=invalid-name


logger = logging.getLogger(__name__)


class BaseLauncher(ABC, Generic[TRig, TSession, TTaskLogic]):
    RIG_DIR = "Rig"
    SUBJECT_DIR = "Subjects"
    TASK_LOGIC_DIR = "TaskLogic"

    def __init__(
        self,
        *,
        rig_schema_model: Type[TRig],
        session_schema_model: Type[TSession],
        task_logic_schema_model: Type[TTaskLogic],
        data_dir: os.PathLike,
        config_library_dir: os.PathLike,
        temp_dir: os.PathLike = Path("local/.temp"),
        repository_dir: Optional[os.PathLike] = None,
        allow_dirty: bool = False,
        skip_hardware_validation: bool = False,
        debug_mode: bool = False,
        group_by_subject_log: bool = False,
        services: Optional[ServicesFactoryManager] = None,
        validate_init: bool = True,
        attached_logger: Optional[logging.Logger] = None,
        rig_schema_path: Optional[os.PathLike] = None,
        task_logic_schema: Optional[os.PathLike] = None,
        subject: Optional[str] = None,
    ) -> None:
        self.temp_dir = self.abspath(temp_dir) / format_datetime(utcnow())
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        # Solve logger
        if attached_logger:
            _logger = logging_helper.add_file_logger(attached_logger, self.temp_dir / "launcher.log")
        else:
            root_logger = logging.getLogger()
            _logger = logging_helper.add_file_logger(root_logger, self.temp_dir / "launcher.log")

        if debug_mode:
            _logger.setLevel(logging.DEBUG)

        self._logger = _logger

        # Solve UI helper
        self._ui_helper = ui_helper.UIHelper()

        # Solve CLI arguments
        self._cli_args: _CliArgs = self._cli_wrapper()

        # Solve services and git repository
        self._bind_launcher_services(services)

        repository_dir = (
            Path(self._cli_args.repository_dir) if self._cli_args.repository_dir is not None else repository_dir
        )
        self.repository = GitRepository() if repository_dir is None else GitRepository(path=repository_dir)
        self._cwd = self.repository.working_dir
        os.chdir(self._cwd)

        # Schemas
        self.rig_schema_model = rig_schema_model
        self.session_schema_model = session_schema_model
        self.task_logic_schema_model = task_logic_schema_model

        # Schema instances
        self._rig_schema: Optional[TRig] = None
        self._session_schema: Optional[TSession] = None
        self._task_logic_schema: Optional[TTaskLogic] = None
        self._solve_schema_instances(rig_path_path=rig_schema_path, task_logic_path=task_logic_schema)
        self._subject: Optional[str] = self._cli_args.subject if self._cli_args.subject else subject

        # Directories
        self.data_dir = Path(self._cli_args.data_dir) if self._cli_args.data_dir is not None else self.abspath(data_dir)

        # Derived directories
        self.config_library_dir = (
            Path(self._cli_args.config_library_dir)
            if self._cli_args.config_library_dir is not None
            else self.abspath(Path(config_library_dir))
        )
        self.computer_name = os.environ["COMPUTERNAME"]
        self._debug_mode = self._cli_args.debug if self._cli_args.debug else debug_mode

        self._rig_dir = Path(os.path.join(self.config_library_dir, self.RIG_DIR, self.computer_name))
        self._subject_dir = Path(os.path.join(self.config_library_dir, self.SUBJECT_DIR))
        self._task_logic_dir = Path(os.path.join(self.config_library_dir, self.TASK_LOGIC_DIR))

        # Flags
        self.allow_dirty = self._cli_args.allow_dirty if self._cli_args.allow_dirty else allow_dirty
        self.skip_hardware_validation = (
            self._cli_args.skip_hardware_validation
            if self._cli_args.skip_hardware_validation
            else skip_hardware_validation
        )
        self.group_by_subject_log = group_by_subject_log

        self._run_hook_return: Any = None

        self._post_init(validate=validate_init)

    def _post_init(self, validate: bool = True) -> None:
        """Overridable method that runs at the end of the self.__init__ method"""
        cli_args = self._cli_args
        if cli_args.create_directories is True:
            self._create_directory_structure()
        if validate:
            self.validate()

    # Public properties / interfaces
    @property
    def rig_schema(self) -> TRig:
        if self._rig_schema is None:
            raise ValueError("Rig schema instance not set.")
        return self._rig_schema

    @property
    def session_schema(self) -> TSession:
        if self._session_schema is None:
            raise ValueError("Session schema instance not set.")
        return self._session_schema

    @property
    def task_logic_schema(self) -> TTaskLogic:
        if self._task_logic_schema is None:
            raise ValueError("Task logic schema instance not set.")
        return self._task_logic_schema

    @property
    def session_directory(self) -> Path:
        if self.session_schema.session_name is None:
            raise ValueError("session_schema.session_name is not set.")
        else:
            return Path(self.session_schema.root_path) / (
                self.session_schema.session_name if self.session_schema.session_name is not None else ""
            )

    @property
    def services_factory_manager(self) -> ServicesFactoryManager:
        if self._services_factory_manager is None:
            raise ValueError("Services instance not set.")
        return self._services_factory_manager

    def main(self) -> None:
        try:
            self._ui_prompt()
            self._run_hooks()
            self.dispose()
        except KeyboardInterrupt:
            logger.error("User interrupted the process.")
            self._exit(-1)
            return

    def _ui_prompt(self) -> Self:
        logger.info(
            self._ui_helper.make_header(
                task_logic_schema_model=self.task_logic_schema_model,
                rig_schema_model=self.rig_schema_model,
                session_schema_model=self.session_schema_model,
            )
        )
        if self._debug_mode:
            self._print_diagnosis()

        self._session_schema = self._prompt_session_input()
        if self._task_logic_schema is None:
            self._task_logic_schema = self._prompt_task_logic_input()
        if self._rig_schema is None:
            self._rig_schema = self._prompt_rig_input()
        return self

    @abstractmethod
    def _prompt_session_input(self) -> TSession:
        raise NotImplementedError("Method not implemented.")

    @abstractmethod
    def _prompt_task_logic_input(self) -> TTaskLogic:
        raise NotImplementedError("Method not implemented.")

    @abstractmethod
    def _prompt_rig_input(self) -> TRig:
        raise NotImplementedError("Method not implemented.")

    def _run_hooks(self) -> Self:
        self._pre_run_hook()
        logger.info("Pre-run hook completed.")
        self._run_hook()
        logger.info("Run hook completed.")
        self._post_run_hook()
        logger.info("Post-run hook completed.")
        return self

    @abstractmethod
    def _pre_run_hook(self, *args, **kwargs) -> Self:
        raise NotImplementedError("Method not implemented.")

    @abstractmethod
    def _run_hook(self, *args, **kwargs) -> Self:
        raise NotImplementedError("Method not implemented.")

    @abstractmethod
    def _post_run_hook(self, *args, **kwargs) -> Self:
        raise NotImplementedError("Method not implemented.")

    def _exit(self, code: int = 0) -> None:
        logger.info("Exiting with code %s", code)
        if logger is not None:
            logging_helper.shutdown_logger(logger)
        sys.exit(code)

    def _print_diagnosis(self) -> None:
        """
        Prints the diagnosis information for the launcher.

        This method prints the diagnosis information,
        including the computer name, data directory,
        and config library directory.

        Parameters:
            None

        Returns:
            None
        """
        logger.debug(
            "-------------------------------\n"
            "Diagnosis:\n"
            "-------------------------------\n"
            "Current Directory: %s\n"
            "Repository: %s\n"
            "Computer Name: %s\n"
            "Data Directory: %s\n"
            "Config Library Directory: %s\n"
            "Temporary Directory: %s\n"
            "-------------------------------",
            self._cwd,
            self.repository.working_dir,
            self.computer_name,
            self.data_dir,
            self.config_library_dir,
            self.temp_dir,
        )

    def validate(self) -> None:
        """
        Validates the dependencies required for the launcher to run.
        """
        try:
            if not (os.path.isdir(self.config_library_dir)):
                raise FileNotFoundError(f"Config library not found! Expected {self.config_library_dir}.")
            if not (os.path.isdir(os.path.join(self.config_library_dir, "Rig", self.computer_name))):
                raise FileNotFoundError(
                    f"Rig configuration not found! \
                        Expected {os.path.join(self.config_library_dir, self.RIG_DIR, self.computer_name)}."
                )

            if self.repository.is_dirty():
                logger.warning(
                    "Git repository is dirty. Discard changes before continuing unless you know what you are doing!"
                )
                if not self.allow_dirty:
                    self.repository.try_prompt_full_reset(self._ui_helper, force_reset=False)
                    if self.repository.is_dirty_with_submodules():
                        logger.error("Dirty repository not allowed. Exiting. Consider running with --allow-dirty flag.")
                        self._exit(-1)
                else:
                    logger.info("Untracked files: %s", self.repository.untracked_files_with_submodules())

        except Exception as e:
            logger.error("Failed to validate dependencies. %s", e)
            self._exit(-1)
            raise e

    def dispose(self) -> None:
        logger.info("Disposing...")
        self._exit(0)

    @classmethod
    def abspath(cls, path: os.PathLike) -> Path:
        return Path(path).resolve()

    def _create_directory_structure(self) -> None:
        try:
            self._create_directory(self.data_dir)
            self._create_directory(self.config_library_dir)
            self._create_directory(self.temp_dir)
            self._create_directory(self._task_logic_dir)
            self._create_directory(self._rig_dir)
            self._create_directory(self._subject_dir)
        except OSError as e:
            logger.error("Failed to create directory structure: %s", e)
            self._exit(-1)

    @classmethod
    def _create_directory(cls, directory: os.PathLike) -> None:
        if not os.path.exists(cls.abspath(directory)):
            logger.info("Creating  %s", directory)
            try:
                os.makedirs(directory)
            except OSError as e:
                logger.error("Failed to create directory %s: %s", directory, e)
                raise e

    @staticmethod
    def _get_default_arg_parser() -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser()

        parser.add_argument("--data-dir", help="Specify the data directory")
        parser.add_argument("--repository-dir", help="Specify the repository directory")
        parser.add_argument("--config-library-dir", help="Specify the configuration library directory")
        parser.add_argument(
            "--create-directories",
            help="Specify whether to force create directories",
            action="store_true",
            default=False,
        )
        parser.add_argument("--debug", help="Specify whether to run in debug mode", action="store_true", default=False)
        parser.add_argument(
            "--allow-dirty", help="Specify whether to allow a dirty repository", action="store_true", default=False
        )
        parser.add_argument(
            "--skip-hardware-validation",
            help="Specify whether to skip hardware validation",
            action="store_true",
            default=False,
        )

        # These should default to None
        parser.add_argument("--subject", help="Specifies the name of the subject")
        parser.add_argument("--task-logic-path", help="Specifies the path to a json file containing task logic")
        parser.add_argument("--rig-path", help="Specifies the path to a json file containing rig configuration")

        # Catch all additional arguments
        # Syntax is a bit clunky, but it works
        # e.g. "python script.py -- --arg1 --arg"
        # This will capture "--arg1 --arg2" in the "extras" list
        parser.add_argument(
            "extras", nargs=argparse.REMAINDER, help="Capture all remaining arguments after -- separator"
        )
        return parser

    @classmethod
    def _cli_wrapper(cls) -> _CliArgs:
        parser = cls._get_default_arg_parser()
        parsed, _ = parser.parse_known_args()
        args = vars(parsed)
        return _CliArgs(**args)

    def _copy_tmp_directory(self, dst: os.PathLike) -> None:
        dst = Path(dst) / ".launcher"
        shutil.copytree(self.temp_dir, dst, dirs_exist_ok=True)

    def _bind_launcher_services(
        self, services_factory_manager: Optional[ServicesFactoryManager]
    ) -> Optional[ServicesFactoryManager]:
        self._services_factory_manager = services_factory_manager
        if self._services_factory_manager is not None:
            self._services_factory_manager.register_launcher(self)
        return self._services_factory_manager

    def _solve_schema_instances(
        self, rig_path_path: Optional[os.PathLike] = None, task_logic_path: Optional[os.PathLike] = None
    ) -> None:
        rig_path_path = self._cli_args.rig_path if self._cli_args.rig_path is not None else rig_path_path
        task_logic_path = (
            self._cli_args.task_logic_path if self._cli_args.task_logic_path is not None else task_logic_path
        )
        if rig_path_path is not None:
            logging.info("Loading rig schema from %s", self._cli_args.rig_path)
            self._rig_schema = model_from_json_file(rig_path_path, self.rig_schema_model)
        if task_logic_path is not None:
            logging.info("Loading task logic schema from %s", self._cli_args.task_logic_path)
            self._task_logic_schema = model_from_json_file(task_logic_path, self.task_logic_schema_model)


@pydantic.dataclasses.dataclass
class _CliArgs:
    data_dir: Optional[os.PathLike] = None
    repository_dir: Optional[os.PathLike] = None
    config_library_dir: Optional[os.PathLike] = None
    create_directories: bool = False
    debug: bool = False
    allow_dirty: bool = False
    skip_hardware_validation: bool = False
    subject: Optional[str] = None
    task_logic_path: Optional[os.PathLike] = None
    rig_path: Optional[os.PathLike] = None
    extras: dict[str, str] = pydantic.Field(default_factory=dict)

    @pydantic.field_validator("extras", mode="before")
    @classmethod
    def _validate_extras(cls, v):
        if isinstance(v, list):
            v = cls._parse_extra_args(v)
        return v

    @staticmethod
    def _parse_extra_args(args: list[str]) -> dict[str, str]:
        extra_kwargs: dict[str, str] = {}
        if len(args) == 0:
            return extra_kwargs
        _ = args.pop(0)  # remove the "--" separator
        for arg in args:
            if arg.startswith("--"):
                key_value = arg.lstrip("--").split("=", 1)
                if len(key_value) == 2:
                    key, value = key_value
                    extra_kwargs[key] = value
                else:
                    logger.error("Skipping invalid argument format: %s", arg)
        return extra_kwargs

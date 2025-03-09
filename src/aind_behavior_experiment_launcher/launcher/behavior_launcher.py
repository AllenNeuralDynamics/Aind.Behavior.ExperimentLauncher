from __future__ import annotations

import datetime
import enum
import glob
import logging
import os
import subprocess
from functools import partial
from pathlib import Path
from typing import Any, Callable, Dict, Generic, Optional, Self, Type, TypeVar, Union, List, TypeAlias

import pydantic
from aind_behavior_services.utils import model_from_json_file
from typing_extensions import override

from aind_behavior_experiment_launcher import logging_helper
from aind_behavior_experiment_launcher.apps import BonsaiApp
from aind_behavior_experiment_launcher.data_mapper import DataMapper
from aind_behavior_experiment_launcher.data_mapper.aind_data_schema import AindDataSchemaSessionDataMapper
from aind_behavior_experiment_launcher.data_transfer import DataTransfer
from aind_behavior_experiment_launcher.data_transfer.aind_watchdog import WatchdogDataTransferService
from aind_behavior_experiment_launcher.data_transfer.robocopy import RobocopyService
from aind_behavior_experiment_launcher.resource_monitor import ResourceMonitor
from aind_behavior_experiment_launcher.services import IService, ServiceFactory, ServicesFactoryManager
from aind_behavior_experiment_launcher.ui_helper import pickers as pickers
from aind_behavior_experiment_launcher.ui_helper.default import DefaultUIHelper

from ._base import BaseLauncher, TRig, TSession, TTaskLogic

TService = TypeVar("TService", bound=IService)

logger = logging.getLogger(__name__)


class BehaviorLauncher(BaseLauncher, Generic[TRig, TSession, TTaskLogic]):
    services_factory_manager: BehaviorServicesFactoryManager

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def _post_init(self, validate: bool = True) -> None:
        super()._post_init(validate=validate)
        if validate:
            if self.services_factory_manager.resource_monitor is not None:
                self.services_factory_manager.resource_monitor.evaluate_constraints()

    @override
    def _pre_run_hook(self, *args, **kwargs) -> Self:
        logger.info("Pre-run hook started.")
        self.session_schema.experiment = self.task_logic_schema.name
        self.session_schema.experiment_version = self.task_logic_schema.version

        if self.services_factory_manager.bonsai_app.layout is None:
            self.services_factory_manager.bonsai_app.layout = self.services_factory_manager.bonsai_app.prompt_input()
        return self

    @override
    def _run_hook(self, *args, **kwargs) -> Self:
        logger.info("Running hook started.")
        if self._session_schema is None:
            raise ValueError("Session schema instance not set.")
        if self._task_logic_schema is None:
            raise ValueError("Task logic schema instance not set.")
        if self._rig_schema is None:
            raise ValueError("Rig schema instance not set.")

        settings = {
            "TaskLogicPath": os.path.abspath(
                self._save_temp_model(model=self._task_logic_schema, directory=self.temp_dir)
            ),
            "SessionPath": os.path.abspath(self._save_temp_model(model=self._session_schema, directory=self.temp_dir)),
            "RigPath": os.path.abspath(self._save_temp_model(model=self._rig_schema, directory=self.temp_dir)),
        }
        if self.services_factory_manager.bonsai_app.additional_properties is not None:
            self.services_factory_manager.bonsai_app.additional_properties.update(settings)
        else:
            self.services_factory_manager.bonsai_app.additional_properties = settings

        try:
            self.services_factory_manager.bonsai_app.run()
            _ = self.services_factory_manager.bonsai_app.output_from_result(allow_stderr=True)
        except subprocess.CalledProcessError as e:
            logger.error("Bonsai app failed to run. %s", e)
            self._exit(-1)
        return self

    @override
    def _post_run_hook(self, *args, **kwargs) -> Self:
        logger.info("Post-run hook started.")

        if self.services_factory_manager.data_mapper is not None:
            try:
                self.services_factory_manager.data_mapper.map()
                logger.info("Mapping successful.")
            except Exception as e:
                logger.error("Data mapper service has failed: %s", e)

        logging_helper.close_file_handlers(logger)

        try:
            self._copy_tmp_directory(self.session_directory / "Behavior" / "Logs")
        except ValueError:
            logger.error("Failed to copy temporary logs directory to session directory.")

        if self.services_factory_manager.data_transfer is not None:
            try:
                if not self.services_factory_manager.data_transfer.validate():
                    raise ValueError("Data transfer service failed validation.")
                self.services_factory_manager.data_transfer.transfer()
            except Exception as e:
                logger.error("Data transfer service has failed: %s", e)

        return self

    def _save_temp_model(self, model: Union[TRig, TSession, TTaskLogic], directory: Optional[os.PathLike]) -> str:
        directory = Path(directory) if directory is not None else Path(self.temp_dir)
        os.makedirs(directory, exist_ok=True)
        fname = model.__class__.__name__ + ".json"
        fpath = os.path.join(directory, fname)
        with open(fpath, "w+", encoding="utf-8") as f:
            f.write(model.model_dump_json(indent=3))
        return fpath


_ServiceFactoryIsh: TypeAlias = Union[ServiceFactory[TService], Callable[[BaseLauncher], TService], TService])


class BehaviorServicesFactoryManager(ServicesFactoryManager):
    def __init__(self, launcher: Optional[BehaviorLauncher] = None, **kwargs) -> None:
        super().__init__(launcher, **kwargs)
        self._add_to_services("bonsai_app", kwargs)
        self._add_to_services("data_transfer", kwargs)
        self._add_to_services("resource_monitor", kwargs)
        self._add_to_services("data_mapper", kwargs)

    def _add_to_services(self, name: str, input_kwargs: Dict[str, Any]) -> Optional[ServiceFactory]:
        srv = input_kwargs.pop(name, None)
        if srv is not None:
            self.attach_service_factory(name, srv)
        return srv

    @property
    def bonsai_app(self) -> BonsaiApp:
        srv = self.try_get_service("bonsai_app")
        srv = self._validate_service_type(srv, BonsaiApp)
        if srv is None:
            raise ValueError("BonsaiApp is not set.")
        return srv

    def attach_bonsai_app(self, value: _ServiceFactoryIsh[BonsaiApp] | BonsaiApp) -> None:
        self.attach_service_factory("bonsai_app", value)

    @property
    def data_mapper(self) -> Optional[DataMapper]:
        srv = self.try_get_service("data_mapper")
        return self._validate_service_type(srv, DataMapper)

    def attach_data_mapper(self, value: _ServiceFactoryIsh[DataMapper]) -> None:
        self.attach_service_factory("data_mapper", value)

    @property
    def resource_monitor(self) -> Optional[ResourceMonitor]:
        srv = self.try_get_service("resource_monitor")
        return self._validate_service_type(srv, ResourceMonitor)

    def attach_resource_monitor(self, value: _ServiceFactoryIsh[ResourceMonitor]) -> None:
        self.attach_service_factory("resource_monitor", value)

    @property
    def data_transfer(self) -> Optional[DataTransfer]:
        srv = self.try_get_service("data_transfer")
        return self._validate_service_type(srv, DataTransfer)

    def attach_data_transfer(self, value: _ServiceFactoryIsh[DataTransfer]) -> None:
        self.attach_service_factory("data_transfer", value)

    @staticmethod
    def _validate_service_type(value: Any, type_of: Type) -> Optional[TService]:
        if value is None:
            return None
        if not isinstance(value, type_of):
            raise ValueError(f"{type(value).__name__} is not of the correct type. Expected {type_of.__name__}.")
        return value


def watchdog_data_transfer_factory(
    *,
    destination: os.PathLike,
    schedule_time: Optional[datetime.time] = datetime.time(hour=20),
    project_name: Optional[str] = None,
    **watchdog_kwargs,
) -> Callable[[BehaviorLauncher], WatchdogDataTransferService]:
    return partial(
        _watchdog_data_transfer_factory,
        destination=destination,
        schedule_time=schedule_time,
        project_name=project_name,
        **watchdog_kwargs,
    )


def _watchdog_data_transfer_factory(launcher: BehaviorLauncher, **watchdog_kwargs) -> WatchdogDataTransferService:
    if launcher.services_factory_manager.data_mapper is None:
        raise ValueError("Data mapper service is not set. Cannot create watchdog.")
    if not isinstance(launcher.services_factory_manager.data_mapper, AindDataSchemaSessionDataMapper):
        raise ValueError(
            "Data mapper service is not of the correct type (AindDataSchemaSessionDataMapper). Cannot create watchdog."
        )

    watchdog = WatchdogDataTransferService(
        source=launcher.session_directory,
        aind_session_data_mapper=launcher.services_factory_manager.data_mapper,
        session_name=launcher.session_schema.session_name,
        **watchdog_kwargs,
    )
    return watchdog


def robocopy_data_transfer_factory(
    destination: os.PathLike,
    **robocopy_kwargs,
) -> Callable[[BehaviorLauncher], RobocopyService]:
    return partial(_robocopy_data_transfer_factory, destination=destination, **robocopy_kwargs)


def _robocopy_data_transfer_factory(
    launcher: BehaviorLauncher, destination: os.PathLike, **robocopy_kwargs
) -> RobocopyService:
    if launcher.group_by_subject_log:
        dst = Path(destination) / launcher.session_schema.subject / launcher.session_schema.session_name
    else:
        dst = Path(destination) / launcher.session_schema.session_name
    return RobocopyService(source=launcher.session_directory, destination=dst, **robocopy_kwargs)


class ByAnimalFiles(enum.Enum):
    TASK_LOGIC = "task_logic"


_BehaviorLauncher = TypeVar("_BehaviorLauncher", bound=BehaviorLauncher)
_T = TypeVar("_T", bound=Any)


class DefaultBehaviorPicker(pickers.PickerBase[_BehaviorLauncher]):

    def pick_rig(self, directory: Optional[str] = None) -> TRig:
        rig_schemas_path = (
            Path(os.path.join(self.launcher.config_library_dir, directory, self.launcher.computer_name))
            if directory is not None
            else self.launcher.rig_dir
        )
        available_rigs = glob.glob(os.path.join(rig_schemas_path, "*.json"))
        if len(available_rigs) == 1:
            logger.info("Found a single rig config file. Using %s.", {available_rigs[0]})
            return model_from_json_file(available_rigs[0], self.launcher.rig_schema_model)
        else:
            while True:
                try:
                    path = self.prompt_pick_file_from_list(
                        available_rigs, prompt="Choose a rig:", zero_label=None
                    )
                    if not isinstance(path, str):
                        raise ValueError("Invalid choice.")
                    rig = model_from_json_file(path, self.launcher.rig_schema_model)
                    logger.info("Using %s.", path)
                    return rig
                except pydantic.ValidationError as e:
                    logger.error("Failed to validate pydantic model. Try again. %s", e)
                except ValueError as e:
                    logger.error("Invalid choice. Try again. %s", e)


    def pick_session(self) -> TSession:
        experimenter = self.prompt_experimenter(strict=True)
        if self.launcher.subject is not None:
            logging.info("Subject provided via CLABE: %s", self.launcher.cli_args.subject)
            subject = self.launcher.subject
        else:
            subject = self.choose_subject(self.launcher.subject_dir)
            self.launcher.subject = subject
            if not (self.launcher.subject_dir / subject).exists():
                logger.warning("Directory for subject %s does not exist. Creating a new one.", subject)
                os.makedirs(self.launcher.subject_dir / subject)

        notes = self.ui_helper.prompt_text("Enter notes: ")

        return self.launcher.session_schema_model(
            experiment="",  # Will be set later
            root_path=str(self.launcher.data_dir.resolve())
            if not self.launcher.group_by_subject_log
            else str(self.launcher.data_dir.resolve() / subject),
            subject=subject,
            notes=notes,
            experimenter=experimenter if experimenter is not None else [],
            commit_hash=self.launcher.repository.head.commit.hexsha,
            allow_dirty_repo=self.launcher.is_debug_mode or self.launcher.allow_dirty,
            skip_hardware_validation=self.launcher.skip_hardware_validation,
            experiment_version="",  # Will be set later
        )

    def pick_task_logic(self) -> TTaskLogic:
        task_logic: Optional[TTaskLogic] = self.launcher.task_logic_schema
        # If the task logic is already set (e.g. from CLI), skip the prompt
        if task_logic is not None:
            return task_logic

        # Else, we check inside the subject folder for an existing task file
        try:
            f = self.launcher.subject_dir / self.launcher.session_schema.subject / ByAnimalFiles.TASK_LOGIC
            logger.info("Attempting to load task logic from subject folder: %s", f)
            task_logic = model_from_json_file(f, self.launcher.task_logic_schema_model)
        except (ValueError, FileNotFoundError, pydantic.ValidationError) as e:
            logger.warning("Failed to find a valid task logic file. %s", e)
        else:
            logger.info("Found a valid task logic file in subject folder!")
            _is_manual = self.ui_helper.prompt_yes_no_question("Would you like to use this task logic?")
            if not _is_manual:
                return task_logic
            else:
                task_logic = None

        # If not found, we prompt the user to choose/enter a task logic file
        while task_logic is None:
            try:
                _path = Path(os.path.join(self.launcher.config_library_dir, self.launcher.task_logic_dir))
                available_files = glob.glob(os.path.join(_path, "*.json"))
                path = self.prompt_pick_file_from_list(
                    available_files, prompt="Choose a task logic:", zero_label=None
                )
                if not isinstance(path, str):
                    raise ValueError("Invalid choice.")
                if not os.path.isfile(path):
                    raise FileNotFoundError(f"File not found: {path}")
                task_logic = model_from_json_file(path, self.launcher.task_logic_schema_model)
                logger.info("User entered: %s.", path)
            except pydantic.ValidationError as e:
                logger.error("Failed to validate pydantic model. Try again. %s", e)
            except (ValueError, FileNotFoundError) as e:
                logger.error("Invalid choice. Try again. %s", e)

        return task_logic


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

    def choose_subject(self, directory: str | os.PathLike) -> str:
        subject = None
        while subject is None:
            subject = self.ui_helper.prompt_pick_from_list(
                [
                    os.path.basename(folder)
                    for folder in os.listdir(directory)
                    if os.path.isdir(os.path.join(directory, folder))
                ],
                prompt="Choose a subject:",
                allow_0_as_none=True,
            )
            if subject is None:
                subject = self.ui_helper.input("Enter subject name manually: ")
                if subject == "":
                    logger.error("Subject name cannot be empty.")
                    subject = None
        return subject

    def prompt_experimenter(self, strict: bool = True) -> Optional[List[str]]:
        experimenter: Optional[List[str]] = None
        while experimenter is None:
            _user_input = self.ui_helper.prompt_text("Experimenter name: ")
            experimenter = _user_input.replace(",", " ").split()
            if strict & (len(experimenter) == 0):
                logger.error("Experimenter name is not valid.")
                experimenter = None
            else:
                return experimenter
        return experimenter  # This line should be unreachable

    def prompt_notes(self) -> str:
        return self.ui_helper.prompt_text("Enter notes: ")

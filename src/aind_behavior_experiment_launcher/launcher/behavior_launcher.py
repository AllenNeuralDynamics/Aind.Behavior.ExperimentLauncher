from __future__ import annotations

import datetime
import enum
import glob
import logging
import os
import subprocess
from functools import partial
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Self, Type, TypeAlias, TypeVar, Union

import pydantic
from aind_behavior_services.utils import model_from_json_file
from pydantic_settings import CliImplicitFlag
from typing_extensions import override

import aind_behavior_experiment_launcher.ui as ui
from aind_behavior_experiment_launcher import logging_helper
from aind_behavior_experiment_launcher.apps import App
from aind_behavior_experiment_launcher.data_mapper import DataMapper
from aind_behavior_experiment_launcher.data_mapper.aind_data_schema import AindDataSchemaSessionDataMapper
from aind_behavior_experiment_launcher.data_transfer import DataTransfer
from aind_behavior_experiment_launcher.data_transfer.aind_watchdog import WatchdogDataTransferService
from aind_behavior_experiment_launcher.data_transfer.robocopy import RobocopyService
from aind_behavior_experiment_launcher.resource_monitor import ResourceMonitor
from aind_behavior_experiment_launcher.services import IService, ServiceFactory, ServicesFactoryManager

from ._base import BaseLauncher, TRig, TSession, TTaskLogic
from .cli import BaseCliArgs

TService = TypeVar("TService", bound=IService)

logger = logging.getLogger(__name__)


class BehaviorCliArgs(BaseCliArgs):
    """Extends the base"""

    skip_data_transfer: CliImplicitFlag[bool] = pydantic.Field(
        default=False, description="Whether to skip data transfer after the experiment"
    )
    skip_data_mapping: CliImplicitFlag[bool] = pydantic.Field(
        default=False, description="Whether to skip data mapping after the experiment"
    )


class BehaviorLauncher(BaseLauncher[TRig, TSession, TTaskLogic]):
    """
    A launcher for behavior experiments that manages services, experiment configuration, and
    execution hooks.
    """

    settings: BehaviorCliArgs
    services_factory_manager: BehaviorServicesFactoryManager

    def __init__(  # pylint: disable=useless-parent-delegation
        self,
        *,
        settings: BehaviorCliArgs,
        rig_schema_model,
        session_schema_model,
        task_logic_schema_model,
        picker,
        services=None,
        attached_logger=None,
        **kwargs,
    ):
        super().__init__(
            settings=settings,
            rig_schema_model=rig_schema_model,
            session_schema_model=session_schema_model,
            task_logic_schema_model=task_logic_schema_model,
            picker=picker,
            services=services,
            attached_logger=attached_logger,
            **kwargs,
        )

    def _post_init(self, validate: bool = True) -> None:
        """
        Performs additional initialization after the constructor.

        Args:
            validate (bool): Whether to validate the launcher state.
        """
        super()._post_init(validate=validate)
        if validate:
            if self.services_factory_manager.resource_monitor is not None:
                self.services_factory_manager.resource_monitor.evaluate_constraints()

    @override
    def _pre_run_hook(self, *args, **kwargs) -> Self:
        """
        Hook executed before the main run logic.

        Returns:
            Self: The current instance for method chaining.
        """
        logger.info("Pre-run hook started.")
        self.session_schema.experiment = self.task_logic_schema.name
        self.session_schema.experiment_version = self.task_logic_schema.version
        return self

    @override
    def _run_hook(self, *args, **kwargs) -> Self:
        """
        Hook executed during the main run logic.

        Returns:
            Self: The current instance for method chaining.
        """
        logger.info("Running hook started.")
        if self._session_schema is None:
            raise ValueError("Session schema instance not set.")
        if self._task_logic_schema is None:
            raise ValueError("Task logic schema instance not set.")
        if self._rig_schema is None:
            raise ValueError("Rig schema instance not set.")

        self.services_factory_manager.app.add_app_settings(launcher=self)

        try:
            self.services_factory_manager.app.run()
            _ = self.services_factory_manager.app.output_from_result(allow_stderr=True)
        except subprocess.CalledProcessError as e:
            logger.error("Bonsai app failed to run. %s", e)
            self._exit(-1)
        return self

    @override
    def _post_run_hook(self, *args, **kwargs) -> Self:
        """
        Hook executed after the main run logic.

        Returns:
            Self: The current instance for method chaining.
        """
        logger.info("Post-run hook started.")

        if (self.services_factory_manager.data_mapper is not None) and (not self.settings.skip_data_mapping):
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

        if (self.services_factory_manager.data_transfer is not None) and (not self.settings.skip_data_transfer):
            try:
                if not self.services_factory_manager.data_transfer.validate():
                    raise ValueError("Data transfer service failed validation.")
                self.services_factory_manager.data_transfer.transfer()
            except Exception as e:
                logger.error("Data transfer service has failed: %s", e)

        return self

    def save_temp_model(self, model: Union[TRig, TSession, TTaskLogic], directory: Optional[os.PathLike]) -> str:
        """
        Saves a temporary JSON representation of a schema model.

        Args:
            model (Union[TRig, TSession, TTaskLogic]): The schema model to save.
            directory (Optional[os.PathLike]): The directory to save the file in.

        Returns:
            str: The path to the saved file.
        """
        directory = Path(directory) if directory is not None else Path(self.temp_dir)
        os.makedirs(directory, exist_ok=True)
        fname = model.__class__.__name__ + ".json"
        fpath = os.path.join(directory, fname)
        with open(fpath, "w+", encoding="utf-8") as f:
            f.write(model.model_dump_json(indent=3))
        return fpath


_ServiceFactoryIsh: TypeAlias = Union[
    ServiceFactory[TService, BehaviorLauncher], Callable[[BehaviorLauncher], TService], TService
]


class BehaviorServicesFactoryManager(ServicesFactoryManager[BehaviorLauncher]):
    """
    Manages the creation and attachment of services for the BehaviorLauncher.

    This class provides methods to attach and retrieve various services such as
    app, data transfer, resource monitor, and data mapper. It ensures that the
    services are of the correct type and properly initialized.
    """

    def __init__(self, launcher: Optional[BehaviorLauncher] = None, **kwargs) -> None:
        """
        Initializes the BehaviorServicesFactoryManager.

        Args:
            launcher (Optional[BehaviorLauncher]): The launcher instance to associate with the services.
            **kwargs: Additional keyword arguments for service initialization.
        """
        super().__init__(launcher, **kwargs)
        self._add_to_services("app", kwargs)
        self._add_to_services("data_transfer", kwargs)
        self._add_to_services("resource_monitor", kwargs)
        self._add_to_services("data_mapper", kwargs)

    def _add_to_services(self, name: str, input_kwargs: Dict[str, Any]) -> Optional[ServiceFactory]:
        """
        Adds a service to the manager by attaching it to the appropriate factory.

        Args:
            name (str): The name of the service to add.
            input_kwargs (Dict[str, Any]): The keyword arguments containing the service instance or factory.

        Returns:
            Optional[ServiceFactory]: The attached service factory, if any.
        """
        srv = input_kwargs.pop(name, None)
        if srv is not None:
            self.attach_service_factory(name, srv)
        return srv

    @property
    def app(self) -> App:
        """
        Retrieves the app service.

        Returns:
            App: The app service instance.

        Raises:
            ValueError: If the app service is not set.
        """
        srv = self.try_get_service("app")
        srv = self._validate_service_type(srv, App)
        if srv is None:
            raise ValueError("App is not set.")
        return srv

    def attach_app(self, value: _ServiceFactoryIsh[App, BehaviorLauncher]) -> None:
        """
        Attaches an app service factory.

        Args:
            value (_ServiceFactoryIsh[App]): The app service factory or instance.
        """
        self.attach_service_factory("app", value)

    @property
    def data_mapper(self) -> Optional[DataMapper]:
        """
        Retrieves the data mapper service.

        Returns:
            Optional[DataMapper]: The data mapper service instance.
        """
        srv = self.try_get_service("data_mapper")
        return self._validate_service_type(srv, DataMapper)

    def attach_data_mapper(self, value: _ServiceFactoryIsh[DataMapper, BehaviorLauncher]) -> None:
        """
        Attaches a data mapper service factory.

        Args:
            value (_ServiceFactoryIsh[DataMapper]): The data mapper service factory or instance.
        """
        self.attach_service_factory("data_mapper", value)

    @property
    def resource_monitor(self) -> Optional[ResourceMonitor]:
        """
        Retrieves the resource monitor service.

        Returns:
            Optional[ResourceMonitor]: The resource monitor service instance.
        """
        srv = self.try_get_service("resource_monitor")
        return self._validate_service_type(srv, ResourceMonitor)

    def attach_resource_monitor(self, value: _ServiceFactoryIsh[ResourceMonitor, BehaviorLauncher]) -> None:
        """
        Attaches a resource monitor service factory.

        Args:
            value (_ServiceFactoryIsh[ResourceMonitor]): The resource monitor service factory or instance.
        """
        self.attach_service_factory("resource_monitor", value)

    @property
    def data_transfer(self) -> Optional[DataTransfer]:
        """
        Retrieves the data transfer service.

        Returns:
            Optional[DataTransfer]: The data transfer service instance.
        """
        srv = self.try_get_service("data_transfer")
        return self._validate_service_type(srv, DataTransfer)

    def attach_data_transfer(self, value: _ServiceFactoryIsh[DataTransfer, BehaviorLauncher]) -> None:
        """
        Attaches a data transfer service factory.

        Args:
            value (_ServiceFactoryIsh[DataTransfer]): The data transfer service factory or instance.
        """
        self.attach_service_factory("data_transfer", value)

    @staticmethod
    def _validate_service_type(value: Any, type_of: Type) -> Optional[TService]:
        """
        Validates the type of a service.

        Args:
            value (Any): The service instance to validate.
            type_of (Type): The expected type of the service.

        Returns:
            Optional[TService]: The validated service instance.

        Raises:
            ValueError: If the service is not of the expected type.
        """
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
    """
    Creates a factory for the WatchdogDataTransferService.

    Args:
        destination (os.PathLike): The destination path for data transfer.
        schedule_time (Optional[datetime.time]): The scheduled time for data transfer.
        project_name (Optional[str]): The project name.
        **watchdog_kwargs: Additional keyword arguments for the watchdog service.

    Returns:
        Callable[[BehaviorLauncher], WatchdogDataTransferService]: A callable factory for the watchdog service.
    """
    return partial(
        _watchdog_data_transfer_factory,
        destination=destination,
        schedule_time=schedule_time,
        project_name=project_name,
        **watchdog_kwargs,
    )


def _watchdog_data_transfer_factory(launcher: BehaviorLauncher, **watchdog_kwargs) -> WatchdogDataTransferService:
    """
    Internal factory function for creating a WatchdogDataTransferService.

    Args:
        launcher (BehaviorLauncher): The launcher instance.
        **watchdog_kwargs: Additional keyword arguments for the watchdog service.

    Returns:
        WatchdogDataTransferService: The created watchdog service.

    Raises:
        ValueError: If the data mapper service is not set or is of the wrong type.
    """
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
    """
    Creates a factory for the RobocopyService.

    Args:
        destination (os.PathLike): The destination path for data transfer.
        **robocopy_kwargs: Additional keyword arguments for the robocopy service.

    Returns:
        Callable[[BehaviorLauncher], RobocopyService]: A callable factory for the robocopy service.
    """
    return partial(_robocopy_data_transfer_factory, destination=destination, **robocopy_kwargs)


def _robocopy_data_transfer_factory(
    launcher: BehaviorLauncher, destination: os.PathLike, **robocopy_kwargs
) -> RobocopyService:
    """
    Internal factory function for creating a RobocopyService.

    Args:
        launcher (BehaviorLauncher): The launcher instance.
        destination (os.PathLike): The destination path for data transfer.
        **robocopy_kwargs: Additional keyword arguments for the robocopy service.

    Returns:
        RobocopyService: The created robocopy service.
    """
    if launcher.group_by_subject_log:
        dst = Path(destination) / launcher.session_schema.subject / launcher.session_schema.session_name
    else:
        dst = Path(destination) / launcher.session_schema.session_name
    return RobocopyService(source=launcher.session_directory, destination=dst, **robocopy_kwargs)


class ByAnimalFiles(enum.StrEnum):
    """
    Enum for file types associated with animals in the experiment.
    """

    TASK_LOGIC = "task_logic"


_BehaviorPickerAlias = ui.PickerBase[BehaviorLauncher[TRig, TSession, TTaskLogic], TRig, TSession, TTaskLogic]


class DefaultBehaviorPicker(_BehaviorPickerAlias[TRig, TSession, TTaskLogic]):
    """
    A picker class for selecting rig, session, and task logic configurations for behavior experiments.

    This class provides methods to initialize directories, pick configurations, and prompt user inputs
    for various components of the experiment setup.
    """

    RIG_SUFFIX: str = "Rig"
    SUBJECT_SUFFIX: str = "Subjects"
    TASK_LOGIC_SUFFIX: str = "TaskLogic"

    @override
    def __init__(
        self,
        launcher: Optional[BehaviorLauncher[TRig, TSession, TTaskLogic]] = None,
        *,
        ui_helper: Optional[ui.DefaultUIHelper] = None,
        config_library_dir: os.PathLike,
        **kwargs,
    ):
        """
        Initializes the DefaultBehaviorPicker.

        Args:
            launcher (Optional[BehaviorLauncher]): The launcher instance associated with the picker.
            ui_helper (Optional[ui.DefaultUIHelper]): Helper for user interface interactions.
            config_library_dir (os.PathLike): Path to the configuration library directory.
            **kwargs: Additional keyword arguments.
        """
        super().__init__(launcher, ui_helper=ui_helper, **kwargs)
        self._config_library_dir = Path(config_library_dir)

    @property
    def config_library_dir(self) -> Path:
        """
        Returns the path to the configuration library directory.

        Returns:
            Path: The configuration library directory.
        """
        return self._config_library_dir

    @property
    def rig_dir(self) -> Path:
        """
        Returns the path to the rig configuration directory.

        Returns:
            Path: The rig configuration directory.
        """
        return Path(os.path.join(self._config_library_dir, self.RIG_SUFFIX, self.launcher.computer_name))

    @property
    def subject_dir(self) -> Path:
        """
        Returns the path to the subject configuration directory.

        Returns:
            Path: The subject configuration directory.
        """
        return Path(os.path.join(self._config_library_dir, self.SUBJECT_SUFFIX))

    @property
    def task_logic_dir(self) -> Path:
        """
        Returns the path to the task logic configuration directory.

        Returns:
            Path: The task logic configuration directory.
        """
        return Path(os.path.join(self._config_library_dir, self.TASK_LOGIC_SUFFIX))

    @override
    def initialize(self) -> None:
        """
        Initializes the picker
        """
        if self.launcher.settings.create_directories:
            self._create_directories()

    def _create_directories(self) -> None:
        """
        Creates the required directories for configuration files.
        """
        self.launcher.create_directory(self.config_library_dir)
        self.launcher.create_directory(self.task_logic_dir)
        self.launcher.create_directory(self.rig_dir)
        self.launcher.create_directory(self.subject_dir)

    def pick_rig(self) -> TRig:
        """
        Prompts the user to select a rig configuration file.

        Returns:
            TRig: The selected rig configuration.

        Raises:
            ValueError: If no rig configuration files are found or an invalid choice is made.
        """
        available_rigs = glob.glob(os.path.join(self.rig_dir, "*.json"))
        if len(available_rigs) == 0:
            logger.error("No rig config files found.")
            raise ValueError("No rig config files found.")
        elif len(available_rigs) == 1:
            logger.info("Found a single rig config file. Using %s.", {available_rigs[0]})
            return model_from_json_file(available_rigs[0], self.launcher.rig_schema_model)
        else:
            while True:
                try:
                    path = self.ui_helper.prompt_pick_from_list(available_rigs, prompt="Choose a rig:")
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
        """
        Prompts the user to select or create a session configuration.

        Returns:
            TSession: The created or selected session configuration.
        """
        experimenter = self.prompt_experimenter(strict=True)
        if self.launcher.subject is not None:
            logging.info("Subject provided via CLABE: %s", self.launcher.settings.subject)
            subject = self.launcher.subject
        else:
            subject = self.choose_subject(self.subject_dir)
            self.launcher.subject = subject
            if not (self.subject_dir / subject).exists():
                logger.warning("Directory for subject %s does not exist. Creating a new one.", subject)
                os.makedirs(self.subject_dir / subject)

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
        """
        Prompts the user to select or create a task logic configuration.

        Returns:
            TTaskLogic: The created or selected task logic configuration.

        Raises:
            ValueError: If no valid task logic file is found.
        """
        task_logic: Optional[TTaskLogic]
        try:  # If the task logic is already set (e.g. from CLI), skip the prompt
            task_logic = self.launcher.task_logic_schema
            assert task_logic is not None
            return task_logic
        except ValueError:
            task_logic = None

        # Else, we check inside the subject folder for an existing task file
        try:
            f = self.subject_dir / self.launcher.session_schema.subject / (ByAnimalFiles.TASK_LOGIC.value + ".json")
            logger.info("Attempting to load task logic from subject folder: %s", f)
            task_logic = model_from_json_file(f, self.launcher.task_logic_schema_model)
        except (ValueError, FileNotFoundError, pydantic.ValidationError) as e:
            logger.warning("Failed to find a valid task logic file. %s", e)
        else:
            logger.info("Found a valid task logic file in subject folder!")
            _is_manual = not self.ui_helper.prompt_yes_no_question("Would you like to use this task logic?")
            if not _is_manual:
                return task_logic
            else:
                task_logic = None

        # If not found, we prompt the user to choose/enter a task logic file
        while task_logic is None:
            try:
                _path = Path(os.path.join(self.config_library_dir, self.task_logic_dir))
                available_files = glob.glob(os.path.join(_path, "*.json"))
                if len(available_files) == 0:
                    break
                path = self.ui_helper.prompt_pick_from_list(available_files, prompt="Choose a task logic:")
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
        if task_logic is None:
            logger.error("No task logic file found.")
            raise ValueError("No task logic file found.")
        return task_logic

    def choose_subject(self, directory: str | os.PathLike) -> str:
        """
        Prompts the user to select or manually enter a subject name.

        Args:
            directory (str | os.PathLike): Path to the directory containing subject folders.

        Returns:
            str: The selected or entered subject name.
        """
        subject = None
        while subject is None:
            subject = self.ui_helper.input("Enter subject name: ")
            if subject == "":
                subject = self.ui_helper.prompt_pick_from_list(
                    [
                        os.path.basename(folder)
                        for folder in os.listdir(directory)
                        if os.path.isdir(os.path.join(directory, folder))
                    ],
                    prompt="Choose a subject:",
                    allow_0_as_none=True,
                )
            else:
                return subject

        return subject

    def prompt_experimenter(self, strict: bool = True) -> Optional[List[str]]:
        """
        Prompts the user to enter the experimenter's name(s).

        Args:
            strict (bool): Whether to enforce non-empty input.

        Returns:
            Optional[List[str]]: List of experimenter names.
        """
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

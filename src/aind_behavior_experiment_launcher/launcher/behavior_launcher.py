from __future__ import annotations

import glob
import logging
import os
import subprocess
from functools import partial
from pathlib import Path
from typing import Any, Callable, Dict, Generic, List, Optional, Self, Type, TypeVar, Union

import pydantic
from aind_behavior_services.db_utils import SubjectDataBase, SubjectEntry
from aind_behavior_services.utils import model_from_json_file, utcnow
from typing_extensions import override

from aind_behavior_experiment_launcher import logging_helper
from aind_behavior_experiment_launcher.apps.app_service import BonsaiApp
from aind_behavior_experiment_launcher.data_mappers.aind_data_schema import AindDataSchemaSessionDataMapper
from aind_behavior_experiment_launcher.data_mappers.data_mapper_service import DataMapperService
from aind_behavior_experiment_launcher.data_transfer.data_transfer_service import DataTransferService
from aind_behavior_experiment_launcher.data_transfer.robocopy_service import RobocopyService
from aind_behavior_experiment_launcher.data_transfer.watchdog_service import WatchdogDataTransferService
from aind_behavior_experiment_launcher.launcher import BaseLauncher, TRig, TSession, TTaskLogic
from aind_behavior_experiment_launcher.resource_monitor.resource_monitor_service import ResourceMonitor
from aind_behavior_experiment_launcher.services import IService, ServiceFactory, ServicesFactoryManager

TService = TypeVar("TService", bound=IService)

logger = logging.getLogger(__name__)


class BehaviorLauncher(BaseLauncher, Generic[TRig, TSession, TTaskLogic]):
    services_factory_manager: BehaviorServicesFactoryManager

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._subject_db_data: Optional[SubjectEntry] = None

    def _post_init(self, validate: bool = True) -> None:
        super()._post_init(validate=validate)
        if validate:
            if self.services_factory_manager.resource_monitor is not None:
                self.services_factory_manager.resource_monitor.evaluate_constraints()

    @override
    def _prompt_session_input(self, directory: Optional[str] = None) -> TSession:
        _local_config_directory = (
            Path(os.path.join(self.config_library_dir, directory)) if directory is not None else self._subject_dir
        )
        available_batches = self._get_available_batches(_local_config_directory)
        experimenter = self._ui_helper.prompt_experimenter(strict=True)
        subject_list = self._get_subject_list(available_batches)
        subject = self._ui_helper.choose_subject(subject_list)
        self._subject_db_data = subject_list.get_subject(subject)
        notes = self._ui_helper.prompt_get_notes()

        return self.session_schema_model(
            experiment="",  # Will be set later
            root_path=str(self.data_dir.resolve())
            if not self.group_by_subject_log
            else str(self.data_dir.resolve() / subject),
            subject=subject,
            notes=notes,
            experimenter=experimenter if experimenter is not None else [],
            commit_hash=self.repository.head.commit.hexsha,
            allow_dirty_repo=self._debug_mode or self.allow_dirty,
            skip_hardware_validation=self.skip_hardware_validation,
            experiment_version="",  # Will be set later
        )

    def _get_available_batches(self, directory: os.PathLike) -> List[str]:
        available_batches = glob.glob(os.path.join(directory, "*.json"))
        available_batches = [batch for batch in available_batches if os.path.isfile(batch)]
        if len(available_batches) == 0:
            raise FileNotFoundError(f"No batch files found in {directory}")
        return available_batches

    def _get_subject_list(self, available_batches: List[str]) -> SubjectDataBase:
        subject_list = None
        while subject_list is None:
            try:
                if len(available_batches) == 1:
                    batch_file = available_batches[0]
                    print(f"Found a single session config file. Using {batch_file}.")
                else:
                    pick = self._ui_helper.prompt_pick_file_from_list(
                        available_batches, prompt="Choose a batch:", zero_label=None
                    )
                    if not isinstance(pick, str):
                        raise ValueError("Invalid choice.")
                    batch_file = pick
                    if not os.path.isfile(batch_file):
                        raise FileNotFoundError(f"File not found: {batch_file}")
                    print(f"Using {batch_file}.")
                with open(batch_file, "r", encoding="utf-8") as file:
                    subject_list = SubjectDataBase.model_validate_json(file.read())
                if len(subject_list.subjects) == 0:
                    raise ValueError("No subjects found in the batch file.")
            except (ValueError, FileNotFoundError, IOError, pydantic.ValidationError) as e:
                logger.error("Invalid choice. Try again. %s", e)
                if len(available_batches) == 1:
                    logger.error("No valid subject batch files found. Exiting.")
                    self._exit(-1)
            else:
                return subject_list

    @override
    def _prompt_rig_input(self, directory: Optional[str] = None) -> TRig:
        rig_schemas_path = (
            Path(os.path.join(self.config_library_dir, directory, self.computer_name))
            if directory is not None
            else self._rig_dir
        )
        available_rigs = glob.glob(os.path.join(rig_schemas_path, "*.json"))
        if len(available_rigs) == 1:
            print(f"Found a single rig config file. Using {available_rigs[0]}.")
            return model_from_json_file(available_rigs[0], self.rig_schema_model)
        else:
            while True:
                try:
                    path = self._ui_helper.prompt_pick_file_from_list(
                        available_rigs, prompt="Choose a rig:", zero_label=None
                    )
                    if not isinstance(path, str):
                        raise ValueError("Invalid choice.")
                    rig = model_from_json_file(path, self.rig_schema_model)
                    print(f"Using {path}.")
                    return rig
                except pydantic.ValidationError as e:
                    logger.error("Failed to validate pydantic model. Try again. %s", e)
                except ValueError as e:
                    logger.error("Invalid choice. Try again. %s", e)

    @override
    def _prompt_task_logic_input(
        self,
        directory: Optional[str] = None,
    ) -> TTaskLogic:
        _path = (
            Path(os.path.join(self.config_library_dir, directory)) if directory is not None else self._task_logic_dir
        )
        hint_input: Optional[SubjectEntry] = self._subject_db_data
        task_logic: Optional[TTaskLogic] = None
        while task_logic is None:
            try:
                if hint_input is None:
                    available_files = glob.glob(os.path.join(_path, "*.json"))
                    path = self._ui_helper.prompt_pick_file_from_list(
                        available_files, prompt="Choose a task logic:", zero_label=None
                    )
                    if not isinstance(path, str):
                        raise ValueError("Invalid choice.")
                    if not os.path.isfile(path):
                        raise FileNotFoundError(f"File not found: {path}")
                    task_logic = model_from_json_file(path, self.task_logic_schema_model)
                    print(f"Using {path}.")

                else:
                    hinted_path = os.path.join(_path, hint_input.task_logic_target + ".json")
                    if not os.path.isfile(hinted_path):
                        hint_input = None
                        raise FileNotFoundError(f"Hinted file not found: {hinted_path}. Try entering manually.")
                    use_hint = self._ui_helper.prompt_yes_no_question(
                        f"Would you like to go with the task file: {hinted_path}?"
                    )
                    if use_hint:
                        task_logic = model_from_json_file(hinted_path, self.task_logic_schema_model)
                    else:
                        hint_input = None

            except pydantic.ValidationError as e:
                logger.error("Failed to validate pydantic model. Try again. %s", e)
            except (ValueError, FileNotFoundError) as e:
                logger.error("Invalid choice. Try again. %s", e)

        return task_logic

    @override
    def _pre_run_hook(self, *args, **kwargs) -> Self:
        logger.info("Pre-run hook started.")
        self.session_schema.experiment = self.task_logic_schema.name
        self.session_schema.experiment_version = self.task_logic_schema.version

        if self.services_factory_manager.bonsai_app.layout is None:
            self.services_factory_manager.bonsai_app.layout = (
                self.services_factory_manager.bonsai_app.prompt_visualizer_layout_input(self.config_library_dir)
            )
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
                _is_transfer = self._ui_helper.prompt_yes_no_question("Would you like to transfer data?")
                if _is_transfer:
                    self.services_factory_manager.data_transfer.transfer()
                else:
                    logger.info("Data transfer skipped by user request.")
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


_TServiceFactory = TypeVar(
    "_TServiceFactory", bound=ServiceFactory[TService] | Callable[[BaseLauncher], TService] | TService
)


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

    def attach_bonsai_app(self, value: _TServiceFactory[BonsaiApp] | BonsaiApp) -> None:
        self.attach_service_factory("bonsai_app", value)

    @property
    def data_mapper(self) -> Optional[DataMapperService]:
        srv = self.try_get_service("data_mapper")
        return self._validate_service_type(srv, DataMapperService)

    def attach_data_mapper(self, value: _TServiceFactory[DataMapperService]) -> None:
        self.attach_service_factory("data_mapper", value)

    @property
    def resource_monitor(self) -> Optional[ResourceMonitor]:
        srv = self.try_get_service("resource_monitor")
        return self._validate_service_type(srv, ResourceMonitor)

    def attach_resource_monitor(self, value: _TServiceFactory[ResourceMonitor]) -> None:
        self.attach_service_factory("resource_monitor", value)

    @property
    def data_transfer(self) -> Optional[DataTransferService]:
        srv = self.try_get_service("data_transfer")
        return self._validate_service_type(srv, DataTransferService)

    def attach_data_transfer(self, value: _TServiceFactory[DataTransferService]) -> None:
        self.attach_service_factory("data_transfer", value)

    @staticmethod
    def _validate_service_type(value: Any, type_of: Type) -> Optional[TService]:
        if value is None:
            return None
        if not isinstance(value, type_of):
            raise ValueError(f"{type(value).__name__} is not of the correct type. Expected {type_of.__name__}.")
        return value


def aind_data_mapper_factory() -> Callable[[BehaviorLauncher], AindDataSchemaSessionDataMapper]:
    return _aind_data_mapper_factory


def _aind_data_mapper_factory(launcher: BehaviorLauncher) -> AindDataSchemaSessionDataMapper:
    now = utcnow()
    return AindDataSchemaSessionDataMapper(
        session_model=launcher.session_schema,
        rig_model=launcher.rig_schema,
        task_logic_model=launcher.task_logic_schema,
        repository=launcher.repository,
        script_path=launcher.services_factory_manager.bonsai_app.workflow,
        session_directory=launcher.session_directory,
        session_end_time=now,
    )


def watchdog_data_transfer_factory(
    watchdog: WatchdogDataTransferService,
) -> Callable[[BehaviorLauncher], WatchdogDataTransferService]:
    return partial(_watchdog_data_transfer_factory, watchdog=watchdog)


def _watchdog_data_transfer_factory(
    launcher: BehaviorLauncher, watchdog: WatchdogDataTransferService
) -> WatchdogDataTransferService:
    if launcher.services_factory_manager.data_mapper is None:
        raise ValueError("Data mapper service is not set. Cannot create watchdog.")
    if not isinstance(launcher.services_factory_manager.data_mapper, AindDataSchemaSessionDataMapper):
        raise ValueError(
            "Data mapper service is not of the correct type (AindDataSchemaSessionDataMapper). Cannot create watchdog."
        )
    watchdog.aind_data_mapper = launcher.services_factory_manager.data_mapper
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

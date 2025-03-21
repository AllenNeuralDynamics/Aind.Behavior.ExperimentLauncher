import importlib.util

if importlib.util.find_spec("aind_watchdog_service") is None:
    raise ImportError(
        "The 'aind_watchdog_service' package is required to use this module. \
            Install the optional dependencies defined in `project.toml' \
                by running `pip install .[aind-services]`"
    )

import datetime
import json
import logging
import os
import subprocess
from os import PathLike
from pathlib import Path
from typing import Callable, Dict, List, Optional, Union

import aind_watchdog_service.models
import pydantic
import requests
import yaml
from aind_data_schema.core.metadata import CORE_FILES
from aind_data_schema.core.session import Session as AdsSession
from aind_data_schema_models.platforms import Platform
from aind_watchdog_service.models.manifest_config import (
    BucketType,
    ManifestConfig,
    ModalityConfigs,
)
from aind_watchdog_service.models.watch_config import WatchConfig
from pydantic import BaseModel
from requests.exceptions import HTTPError

from aind_behavior_experiment_launcher import ui
from aind_behavior_experiment_launcher.data_mapper.aind_data_schema import AindDataSchemaSessionDataMapper

from ._base import DataTransfer

logger = logging.getLogger(__name__)


_JobConfigs = Union[ModalityConfigs, Callable[["WatchdogDataTransferService"], Union[ModalityConfigs]]]


class WatchdogDataTransferService(DataTransfer):
    """
    A data transfer service that uses the aind-watchdog-service service to monitor and transfer
    data based on manifest configurations.
    """

    def __init__(
        self,
        source: PathLike,
        destination: PathLike,
        aind_session_data_mapper: Optional[AindDataSchemaSessionDataMapper] = None,
        schedule_time: Optional[datetime.time] = datetime.time(hour=20),
        project_name: Optional[str] = None,
        platform: Platform = getattr(Platform, "BEHAVIOR"),
        capsule_id: Optional[str] = None,
        script: Optional[Dict[str, List[str]]] = None,
        s3_bucket: BucketType = BucketType.PRIVATE,
        mount: Optional[str] = None,
        force_cloud_sync: bool = True,
        transfer_endpoint: str = "http://aind-data-transfer-service/api/v1/submit_jobs",
        validate: bool = True,
        session_name: Optional[str] = None,
        upload_job_configs: Optional[List[_JobConfigs]] = None,
        ui_helper: Optional[ui.UiHelper] = None,
    ) -> None:
        """
        Initializes the WatchdogDataTransferService.

        Args:
            source: The source directory or file to monitor.
            destination: The destination directory or file.
            aind_session_data_mapper: Mapper for session data to AIND schema.
            schedule_time: Time to schedule the transfer.
            project_name: Name of the project.
            platform: Platform associated with the data.
            capsule_id: Capsule ID for the session.
            script: Optional scripts to execute during transfer.
            s3_bucket: S3 bucket type for cloud storage.
            mount: Mount point for the destination.
            force_cloud_sync: Whether to force synchronization with the cloud.
            transfer_endpoint: Endpoint for the transfer service.
            validate: Whether to validate the project name.
            session_name: Name of the session.
            upload_job_configs: List of job configurations for the transfer.
            ui_helper: UI helper for user prompts.
        """
        self.source = source
        self.destination = destination
        self.project_name = project_name
        self.schedule_time = schedule_time
        self.platform = platform
        self.capsule_id = capsule_id
        self.script = script
        self.s3_bucket = s3_bucket
        self.mount = mount
        self.force_cloud_sync = force_cloud_sync
        self.transfer_endpoint = transfer_endpoint
        self._aind_session_data_mapper = aind_session_data_mapper
        self._session_name = session_name
        self.upload_job_configs = upload_job_configs or []

        _default_exe = os.environ.get("WATCHDOG_EXE", None)
        _default_config = os.environ.get("WATCHDOG_CONFIG", None)

        if _default_exe is None or _default_config is None:
            raise ValueError("WATCHDOG_EXE and WATCHDOG_CONFIG environment variables must be defined.")

        self.executable_path = Path(_default_exe)
        self.config_path = Path(_default_config)

        self._watch_config: Optional[WatchConfig] = None
        self._manifest_config: Optional[ManifestConfig] = None

        self.validate_project_name = validate
        self._ui_helper = ui_helper or ui.DefaultUIHelper()

    @property
    def aind_session_data_mapper(self) -> AindDataSchemaSessionDataMapper:
        """
        Gets the aind-data-schema session data mapper.

        Returns:
            The session data mapper.

        Raises:
            ValueError: If the data mapper is not set.
        """
        if self._aind_session_data_mapper is None:
            raise ValueError("Data mapper is not set.")
        return self._aind_session_data_mapper

    @aind_session_data_mapper.setter
    def aind_session_data_mapper(self, value: AindDataSchemaSessionDataMapper) -> None:
        """
        Sets the session data mapper.

        Args:
            value: The data mapper to set.

        Raises:
            ValueError: If the provided value is not a valid data mapper.
        """
        if not isinstance(value, AindDataSchemaSessionDataMapper):
            raise ValueError("Data mapper must be an instance of AindDataSchemaSessionDataMapper.")
        self._aind_session_data_mapper = value

    def transfer(self) -> None:
        """
        Executes the data transfer by generating a Watchdog manifest configuration.
        """
        try:
            if not self.is_running():
                logger.warning("Watchdog service is not running. Attempting to start it.")
                try:
                    self.force_restart(kill_if_running=False)
                except subprocess.CalledProcessError as e:
                    logger.error("Failed to start watchdog service. %s", e)
                    raise RuntimeError("Failed to start watchdog service.") from e
                else:
                    if not self.is_running():
                        logger.error("Failed to start watchdog service.")
                        raise RuntimeError("Failed to start watchdog service.")
                    else:
                        logger.info("Watchdog service restarted successfully.")

            logger.info("Creating watchdog manifest config.")

            if not self.aind_session_data_mapper.is_mapped():
                raise ValueError("Data mapper has not been mapped yet.")

            self._manifest_config = self.create_manifest_config_from_ads_session(
                ads_session=self.aind_session_data_mapper.mapped,
                session_name=self._session_name,
            )

            if self._watch_config is None:
                raise ValueError("Watchdog config is not set.")

            _manifest_path = self.dump_manifest_config(
                path=Path(self._watch_config.flag_dir) / self._manifest_config.name
            )
            logger.info("Watchdog manifest config created successfully at %s.", _manifest_path)

        except (pydantic.ValidationError, ValueError, IOError) as e:
            logger.error("Failed to create watchdog manifest config. %s", e)
            raise e

    def validate(self, create_config: bool = True) -> bool:
        """
        Validates the Watchdog service and its configuration.

        Args:
            create_config: Whether to create a default configuration if missing.

        Returns:
            True if the service is valid, False otherwise.

        Raises:
            FileNotFoundError: If required files are missing.
            HTTPError: If the project name validation fails.
        """
        logger.info("Attempting to validate Watchdog service.")
        if not self.executable_path.exists():
            raise FileNotFoundError(f"Executable not found at {self.executable_path}")
        if not self.config_path.exists():
            if not create_config:
                raise FileNotFoundError(f"Config file not found at {self.config_path}")
            else:
                self._watch_config = self.create_watch_config(
                    self.config_path.parent / "Manifests", self.config_path.parent / "Completed"
                )
                self._write_yaml(self._watch_config, self.config_path)
        else:
            self._watch_config = WatchConfig.model_validate(self._read_yaml(self.config_path))

        is_running = True
        if not self.is_running():
            is_running = False
            logger.warning(
                "Watchdog service is not running. \
                                After the session is over, \
                                the launcher will attempt to forcefully restart it"
            )

        if not self.is_valid_project_name():
            is_running = False
            try:
                logger.warning("Watchdog project name is not valid.")
            except HTTPError as e:
                logger.error("Failed to fetch project names from endpoint. %s", e)
                raise e
        return is_running

    @staticmethod
    def create_watch_config(
        watched_directory: os.PathLike,
        manifest_complete_directory: os.PathLike,
        webhook_url: Optional[str] = None,
        create_dir: bool = True,
    ) -> WatchConfig:
        """
        Creates a WatchConfig object for the Watchdog service.

        Args:
            watched_directory: Directory to monitor for changes.
            manifest_complete_directory: Directory for completed manifests.
            webhook_url: Optional webhook URL for notifications.
            create_dir: Whether to create the directories if they don't exist.

        Returns:
            A WatchConfig object.
        """
        if create_dir:
            if not Path(watched_directory).exists():
                Path(watched_directory).mkdir(parents=True, exist_ok=True)
            if not Path(manifest_complete_directory).exists():
                Path(manifest_complete_directory).mkdir(parents=True, exist_ok=True)

        return WatchConfig(
            flag_dir=str(watched_directory),
            manifest_complete=str(manifest_complete_directory),
            webhook_url=webhook_url,
        )

    def is_valid_project_name(self) -> bool:
        """
        Checks if the project name is valid by querying the metadata service.

        Returns:
            True if the project name is valid, False otherwise.
        """
        project_names = self._get_project_names()
        return self.project_name in project_names

    def create_manifest_config_from_ads_session(
        self,
        ads_session: AdsSession,
        ads_schemas: Optional[List[os.PathLike]] = None,
        session_name: Optional[str] = None,
    ) -> ManifestConfig:
        """
        Creates a ManifestConfig object from an aind-data-schema session.

        Args:
            ads_session: The aind-data-schema session data.
            ads_schemas: Optional list of schema files.
            session_name: Name of the session.

        Returns:
            A ManifestConfig object.

        Raises:
            ValueError: If the project name is invalid.
        """
        processor_full_name = ",".join(ads_session.experimenter_full_name) or os.environ.get("USERNAME", "unknown")

        destination = Path(self.destination).resolve()
        source = Path(self.source).resolve()

        if self.validate_project_name:
            project_names = self._get_project_names()
            if self.project_name not in project_names:
                raise ValueError(f"Project name {self.project_name} not found in {project_names}")

        ads_schemas = self._find_ads_schemas(source) if ads_schemas is None else ads_schemas

        _manifest_config = ManifestConfig(
            name=session_name,
            modalities={
                str(modality.abbreviation): [str(path.resolve()) for path in [source / str(modality.abbreviation)]]
                for modality in ads_session.data_streams[0].stream_modalities
            },
            subject_id=int(ads_session.subject_id),
            acquisition_datetime=ads_session.session_start_time,
            schemas=[str(value) for value in ads_schemas],
            destination=str(destination.resolve()),
            mount=self.mount,
            processor_full_name=processor_full_name,
            project_name=self.project_name,
            schedule_time=self.schedule_time,
            platform=getattr(self.platform, "abbreviation"),
            capsule_id=self.capsule_id,
            s3_bucket=self.s3_bucket,
            script=self.script if self.script else {},
            force_cloud_sync=self.force_cloud_sync,
            transfer_endpoint=self.transfer_endpoint,
        )
        _manifest_config = self.add_transfer_service_args(_manifest_config, jobs=self.upload_job_configs)
        return _manifest_config

    def add_transfer_service_args(
        self,
        manifest_config: ManifestConfig = None,
        jobs=Optional[List[_JobConfigs]],
        submit_job_request_kwargs: Optional[dict] = None,
    ) -> ManifestConfig:
        """
        Adds transfer service arguments to the manifest configuration.

        Args:
            manifest_config: The manifest configuration to update.
            jobs: List of job configurations.
            submit_job_request_kwargs: Additional arguments for the job request.

        Returns:
            The updated ManifestConfig object.
        """
        # TODO (bruno-f-cruz)
        # The following code is super hacky and should be refactored once the transfer service
        # has a more composable API. Currently, the idea is to only allow one job per modality

        # we use the aind-watchdog-service library to create the default transfer service args for us
        job_settings = aind_watchdog_service.models.make_standard_transfer_args(manifest_config)
        job_settings = job_settings.model_copy(update=(submit_job_request_kwargs or {}))
        manifest_config.transfer_service_args = job_settings

        if (jobs is None) or (len(jobs) == 0):
            return manifest_config

        def _normalize_callable(job: _JobConfigs) -> ModalityConfigs:
            if callable(job):
                return job(self)
            return job

        modality_configs = [_normalize_callable(job) for job in jobs]

        if len(set([m.modality for m in modality_configs])) < len(modality_configs):
            raise ValueError("Duplicate modality configurations found. Aborting.")

        for modified in modality_configs:
            for overridable in manifest_config.transfer_service_args.upload_jobs[0].modalities:
                if modified.modality == overridable.modality:
                    # We need to let the watchdog api handle this or we are screwed...
                    modified.source = overridable.source
                    manifest_config.transfer_service_args.upload_jobs[0].modalities.remove(overridable)
                    manifest_config.transfer_service_args.upload_jobs[0].modalities.append(modified)
                    break

        return manifest_config

    @staticmethod
    def _find_ads_schemas(source: PathLike) -> List[PathLike]:
        """
        Finds aind-data-schema schema files in the source directory.

        Args:
            source: The source directory to search.

        Returns:
            A list of schema file paths.
        """
        json_files = []
        for core_file in CORE_FILES:
            json_file = Path(source) / f"{core_file}.json"
            if json_file.exists():
                json_files.append(json_file)
        return [path for path in json_files]

    @staticmethod
    def _get_project_names(
        end_point: str = "http://aind-metadata-service/project_names", timeout: int = 5
    ) -> list[str]:
        """
        Fetches the list of valid project names from the metadata service.

        Args:
            end_point: The endpoint URL for the metadata service.
            timeout: Timeout for the request.

        Returns:
            A list of valid project names.

        Raises:
            HTTPError: If the request fails.
        """
        response = requests.get(end_point, timeout=timeout)
        if response.ok:
            return json.loads(response.content)["data"]
        else:
            response.raise_for_status()
            raise HTTPError(f"Failed to fetch project names from endpoint. {response.content.decode('utf-8')}")

    def is_running(self) -> bool:
        """
        Checks if the Watchdog service is currently running.

        Returns:
            True if the service is running, False otherwise.
        """
        output = subprocess.check_output(
            ["tasklist", "/FI", f"IMAGENAME eq {self.executable_path.name}"], shell=True, encoding="utf-8"
        )
        processes = [line.split()[0] for line in output.splitlines()[2:]]
        return len(processes) > 0

    def force_restart(self, kill_if_running: bool = True) -> subprocess.Popen[bytes]:
        """
        Attempts to restart the Watchdog application.

        Args:
            kill_if_running: Whether to terminate the service if it's already running.

        Returns:
            A subprocess.Popen object representing the restarted service.
        """
        if kill_if_running is True:
            while self.is_running():
                subprocess.run(["taskkill", "/IM", self.executable_path.name, "/F"], shell=True, check=True)

        cmd_factory = "{exe} -c {config}".format(exe=self.executable_path, config=self.config_path)

        return subprocess.Popen(cmd_factory, start_new_session=True, shell=True)

    def dump_manifest_config(self, path: Optional[os.PathLike] = None, make_dir: bool = True) -> Path:
        """
        Dumps the manifest configuration to a YAML file.

        Args:
            path: The file path to save the manifest.
            make_dir: Whether to create the directory if it doesn't exist.

        Returns:
            The path to the saved manifest file.

        Raises:
            ValueError: If the manifest or watch configuration is not set.
        """
        manifest_config = self._manifest_config
        watch_config = self._watch_config

        if manifest_config is None or watch_config is None:
            raise ValueError("ManifestConfig or WatchConfig config is not set.")

        path = (Path(path) if path else Path(watch_config.flag_dir) / f"manifest_{manifest_config.name}.yaml").resolve()
        if "manifest" not in path.name:
            logger.warning("Prefix manifest_ not found in file name. Appending it.")
            path = path.with_name(f"manifest_{path.name}.yaml")

        if make_dir and not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)

        manifest_config.destination = str(Path.as_posix(Path(manifest_config.destination)))
        manifest_config.schemas = [str(Path.as_posix(Path(schema))) for schema in manifest_config.schemas]
        for modality in manifest_config.modalities:
            manifest_config.modalities[modality] = [
                str(Path.as_posix(Path(_path))) for _path in manifest_config.modalities[modality]
            ]

        self._write_yaml(manifest_config, path)
        return path

    @staticmethod
    def _yaml_dump(model: BaseModel) -> str:
        """
        Converts a Pydantic model to a YAML string.

        Args:
            model: The Pydantic model to convert.

        Returns:
            A YAML string representation of the model.
        """
        native_json = json.loads(model.model_dump_json())
        return yaml.dump(native_json, default_flow_style=False)

    @classmethod
    def _write_yaml(cls, model: BaseModel, path: PathLike) -> None:
        """
        Writes a Pydantic model to a YAML file.

        Args:
            model: The Pydantic model to write.
            path: The file path to save the YAML.
        """
        with open(path, "w", encoding="utf-8") as f:
            f.write(cls._yaml_dump(model))

    @staticmethod
    def _read_yaml(path: PathLike) -> dict:
        """
        Reads a YAML file and returns its contents as a dictionary.

        Args:
            path: The file path to read.

        Returns:
            A dictionary representation of the YAML file.
        """
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def prompt_input(self) -> bool:
        """
        Prompts the user to confirm whether to generate a manifest.

        Returns:
            True if the user confirms, False otherwise.
        """
        return self._ui_helper.prompt_yes_no_question("Would you like to generate a watchdog manifest (Y/N)?")

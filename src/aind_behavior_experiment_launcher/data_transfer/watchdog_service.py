try:
    import aind_watchdog_service  # noqa: F401
except ImportError as e:
    e.add_note(
        "The 'aind-watchdog-service' package is required to use this module. \
            Install the optional dependencies defined in `project.toml' \
                by running `pip install .[aind-services]`"
    )
    raise

import datetime
import json
import logging
import os
import subprocess
from os import PathLike
from pathlib import Path
from typing import Dict, List, Optional

import pydantic
import requests
import yaml
from aind_data_schema.core.session import Session as AdsSession
from aind_data_schema_models.platforms import Platform
from aind_watchdog_service.models.manifest_config import BucketType, ManifestConfig
from aind_watchdog_service.models.watch_config import WatchConfig
from pydantic import BaseModel
from requests.exceptions import HTTPError

from aind_behavior_experiment_launcher.data_mappers.aind_data_schema import AindDataSchemaSessionDataMapper

from .data_transfer_service import DataTransferService

logger = logging.getLogger(__name__)


class WatchdogDataTransferService(DataTransferService):
    DEFAULT_EXE: Optional[str] = os.getenv("WATCHDOG_EXE", None)
    DEFAULT_CONFIG: Optional[str] = os.getenv("WATCHDOG_CONFIG", None)

    def __init__(
        self,
        source: PathLike,
        destination: PathLike,
        aind_data_mapper: Optional[AindDataSchemaSessionDataMapper] = None,
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
    ) -> None:
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
        self._aind_data_mapper = aind_data_mapper

        if self.DEFAULT_EXE is None or self.DEFAULT_CONFIG is None:
            raise ValueError("WATCHDOG_EXE and WATCHDOG_CONFIG environment variables must be defined.")

        self.executable_path = Path(self.DEFAULT_EXE)
        self.config_path = Path(self.DEFAULT_CONFIG)
        self._config_model: WatchConfig = None
        self.validate_project_name = validate
        if validate:
            self.validate(create_config=True)

    @property
    def aind_data_mapper(self) -> AindDataSchemaSessionDataMapper:
        if self._aind_data_mapper is None:
            raise ValueError("Data mapper is not set.")
        return self._aind_data_mapper

    @aind_data_mapper.setter
    def aind_data_mapper(self, value: AindDataSchemaSessionDataMapper) -> None:
        self._aind_data_mapper = value

    def transfer(self) -> None:
        try:
            if not self.is_running():
                logger.warning("Watchdog service is not running. Attempting to start it.")
                try:
                    self.force_restart(kill_if_running=False)
                except subprocess.CalledProcessError as e:
                    logger.error("Failed to start watchdog service. %s", e)
                else:
                    if not self.is_running():
                        logger.error("Failed to start watchdog service.")
                    else:
                        logger.info("Watchdog service restarted successfully.")

            logger.info("Creating watchdog manifest config.")

            config = self.manifest_config_factory()

            _manifest_path = self.dump_manifest_config(config, path=Path(self._config_model.flag_dir) / config.name)
            logger.info("Watchdog manifest config created successfully at %s.", _manifest_path)

        except (pydantic.ValidationError, ValueError, IOError) as e:
            logger.error("Failed to create watchdog manifest config. %s", e)

    def manifest_config_factory(self) -> ManifestConfig:
        if not self.aind_data_mapper.is_mapped():
            raise ValueError("Data mapper has not been mapped yet.")
        ads_session = self.aind_data_mapper.mapped
        return self.create_manifest_config_from_ads_session(
            ads_session=ads_session,
            session_name=self.aind_data_mapper.session_model.session_name,
        )

    def validate(self, create_config: bool = True) -> bool:
        logger.info("Attempting to validate Watchdog service.")
        if not self.executable_path.exists():
            raise FileNotFoundError(f"Executable not found at {self.executable_path}")
        if not self.config_path.exists():
            if not create_config:
                raise FileNotFoundError(f"Config file not found at {self.config_path}")
            else:
                self._config_model = self.create_watchdog_config(
                    self.config_path.parent / "Manifests", self.config_path.parent / "Completed"
                )
                self._write_yaml(self._config_model, self.config_path)
        else:
            self._config_model = WatchConfig.model_validate(self._read_yaml(self.config_path))

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

        return is_running

    @staticmethod
    def create_watchdog_config(
        watched_directory: os.PathLike,
        manifest_complete_directory: os.PathLike,
        webhook_url: Optional[str] = None,
        create_dir: bool = True,
    ) -> WatchConfig:
        """Create a WatchConfig object"""

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
        project_names = self._get_project_names()
        return self.project_name in project_names

    def create_manifest_config_from_ads_session(
        self,
        ads_session: AdsSession,
        ads_schemas: Optional[List[os.PathLike]] = None,
        session_name: Optional[str] = None,
    ) -> ManifestConfig:
        """Create a ManifestConfig object"""
        processor_full_name = ",".join(ads_session.experimenter_full_name) or os.environ.get("USERNAME", "unknown")

        destination = Path(self.destination).resolve()
        source = Path(self.source).resolve()

        if session_name is None:
            session_name = (ads_session.stimulus_epochs[0]).stimulus_name

        if self.validate_project_name:
            project_names = self._get_project_names()
            if self.project_name not in project_names:
                raise ValueError(f"Project name {self.project_name} not found in {project_names}")

        ads_schemas = [source / "session.json"] if ads_schemas is None else ads_schemas

        return ManifestConfig(
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

    @staticmethod
    def _get_project_names(
        end_point: str = "http://aind-metadata-service/project_names", timeout: int = 5
    ) -> list[str]:
        response = requests.get(end_point, timeout=timeout)
        if response.ok:
            content = json.loads(response.content)
        else:
            response.raise_for_status()
        return content["data"]

    def is_running(self) -> bool:
        output = subprocess.check_output(
            ["tasklist", "/FI", f"IMAGENAME eq {self.executable_path.name}"], shell=True, encoding="utf-8"
        )
        processes = [line.split()[0] for line in output.splitlines()[2:]]
        return len(processes) > 0

    def force_restart(self, kill_if_running: bool = True) -> subprocess.Popen[bytes]:
        if kill_if_running is True:
            while self.is_running():
                subprocess.run(["taskkill", "/IM", self.executable_path.name, "/F"], shell=True, check=True)

        cmd_factory = "{exe} -c {config}".format(exe=self.executable_path, config=self.config_path)

        return subprocess.Popen(cmd_factory, start_new_session=True, shell=True)

    def dump_manifest_config(
        self, manifest_config: ManifestConfig, path: Optional[os.PathLike] = None, make_dir: bool = True
    ) -> Path:
        path = Path(path if path else self._config_model.flag_dir / f"manifest_{manifest_config.name}.yaml").resolve()
        if "manifest" not in path.name:
            logger.warning("Prefix " "manifest_" " not found in file name. Appending it.")
            path = path.with_name(f"manifest_{path.name}")

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
        native_json = json.loads(model.model_dump_json())
        return yaml.dump(native_json, default_flow_style=False)

    @classmethod
    def _write_yaml(cls, model: BaseModel, path: PathLike) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(cls._yaml_dump(model))

    @staticmethod
    def _read_yaml(path: PathLike) -> dict:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

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

from aind_behavior_experiment_launcher.data_mapper.aind_data_schema import AindDataSchemaSessionDataMapper

from ._base import DataTransfer

logger = logging.getLogger(__name__)


class WatchdogDataTransferService(DataTransfer):
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
        self._aind_session_data_mapper = aind_session_data_mapper
        self._session_name = session_name

        _default_exe = os.environ.get("WATCHDOG_EXE", None)
        _default_config = os.environ.get("WATCHDOG_CONFIG", None)

        if _default_exe is None or _default_config is None:
            raise ValueError("WATCHDOG_EXE and WATCHDOG_CONFIG environment variables must be defined.")

        self.executable_path = Path(_default_exe)
        self.config_path = Path(_default_config)

        self._watch_config: Optional[WatchConfig] = None
        self._manifest_config: Optional[ManifestConfig] = None

        self.validate_project_name = validate

    @property
    def aind_session_data_mapper(self) -> AindDataSchemaSessionDataMapper:
        if self._aind_session_data_mapper is None:
            raise ValueError("Data mapper is not set.")
        return self._aind_session_data_mapper

    @aind_session_data_mapper.setter
    def aind_session_data_mapper(self, value: AindDataSchemaSessionDataMapper) -> None:
        if not isinstance(value, AindDataSchemaSessionDataMapper):
            raise ValueError("Data mapper must be an instance of AindDataSchemaSessionDataMapper.")
        self._aind_session_data_mapper = value

    def transfer(self) -> None:
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
            session_name = self._session_name

        if self.validate_project_name:
            project_names = self._get_project_names()
            if self.project_name not in project_names:
                raise ValueError(f"Project name {self.project_name} not found in {project_names}")

        ads_schemas = self._find_ads_schemas(source) if ads_schemas is None else ads_schemas

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
    def _find_ads_schemas(source: PathLike) -> List[PathLike]:
        # TODO as of version aind-data-schema 1.1.1 this list does not seem to exist...
        # from https://github.com/AllenNeuralDynamics/aind-data-schema/blob/7b2a2a4bf8ed554c56dd33d17cd2f7a0addc1e22/src/aind_data_schema/core/metadata.py#L33
        CORE_FILES = [
            "subject",
            "data_description",
            "procedures",
            "session",
            "rig",
            "processing",
            "acquisition",
            "instrument",
            "quality_control",
        ]
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
        response = requests.get(end_point, timeout=timeout)
        if response.ok:
            return json.loads(response.content)["data"]
        else:
            response.raise_for_status()
            raise HTTPError(f"Failed to fetch project names from endpoint. {response.content}")

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

    def dump_manifest_config(self, path: Optional[os.PathLike] = None, make_dir: bool = True) -> Path:
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

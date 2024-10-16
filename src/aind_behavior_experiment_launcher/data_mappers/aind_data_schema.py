from __future__ import annotations

try:
    import aind_data_schema
except ImportError as _e:
    _e.add_note(
        "The 'aind-data-schema' package is required to use this module. \
            Install the optional dependencies defined in `project.toml' \
                by running `pip install .[aind-services]`"
    )
    raise _e

import datetime
import logging
import os
from pathlib import Path
from typing import Dict, Optional, Self, Type, TypeVar, Union

import aind_behavior_services.rig as AbsRig
import aind_data_schema.components.devices
import aind_data_schema.core.session
import git
import pydantic
from aind_behavior_services import (
    AindBehaviorRigModel,
    AindBehaviorSessionModel,
    AindBehaviorTaskLogicModel,
)
from aind_behavior_services.calibration import Calibration
from aind_behavior_services.utils import model_from_json_file, utcnow

from aind_behavior_experiment_launcher.records.subject_info import SubjectInfo

from . import data_mapper_service

T = TypeVar("T")

logger = logging.getLogger(__name__)


class AindDataSchemaSessionDataMapper(data_mapper_service.DataMapperService):
    def __init__(
        self,
        session_model: AindBehaviorSessionModel,
        rig_model: AindBehaviorRigModel,
        task_logic_model: AindBehaviorTaskLogicModel,
        repository: Union[os.PathLike, git.Repo],
        script_path: os.PathLike,
        session_end_time: Optional[datetime.datetime] = None,
        output_parameters: Optional[Dict] = None,
        subject_info: Optional[SubjectInfo] = None,
        session_directory: Optional[os.PathLike] = None,
    ):
        self.session_model = session_model
        self.rig_model = rig_model
        self.task_logic_model = task_logic_model
        self.session_directory = session_directory
        self.repository = repository
        self.script_path = script_path
        self.session_end_time = session_end_time
        self.output_parameters = output_parameters
        self.subject_info = subject_info
        self.mapped: Optional[aind_data_schema.core.session.Session] = None

    def validate(self, *args, **kwargs) -> bool:
        return True

    def is_mapped(self) -> bool:
        return self.mapped is not None

    def map(self) -> Optional[aind_data_schema.core.session.Session]:
        logger.info("Mapping to aind-data-schema Session")
        try:
            ads_session = self._map(
                session_model=self.session_model,
                rig_model=self.rig_model,
                task_logic_model=self.task_logic_model,
                repository=self.repository,
                script_path=self.script_path,
                session_end_time=self.session_end_time,
                output_parameters=self.output_parameters,
                subject_info=self.subject_info,
            )
            self.mapped = ads_session
            if self.session_directory is not None:
                logger.info("Writing session.json to %s", self.session_directory)
                ads_session.write_standard_file(self.session_directory)
            logger.info("Mapping successful.")
        except (pydantic.ValidationError, ValueError, IOError) as e:
            logger.error("Failed to map to aind-data-schema Session. %s", e)
            raise e
        else:
            return ads_session

    @classmethod
    def map_from_session_root(
        cls,
        schema_root: os.PathLike,
        session_model: Type[AindBehaviorSessionModel],
        rig_model: Type[AindBehaviorRigModel],
        task_logic_model: Type[AindBehaviorTaskLogicModel],
        repository: Union[os.PathLike, git.Repo],
        script_path: os.PathLike,
        session_end_time: Optional[datetime.datetime] = None,
        output_parameters: Optional[Dict] = None,
        subject_info: Optional[SubjectInfo] = None,
    ) -> Self:
        return cls(
            session_model=model_from_json_file(Path(schema_root) / "session_input.json", session_model),
            rig_model=model_from_json_file(Path(schema_root) / "rig_input.json", rig_model),
            task_logic_model=model_from_json_file(Path(schema_root) / "tasklogic_input.json", task_logic_model),
            session_directory=schema_root,
            repository=repository,
            script_path=script_path,
            session_end_time=session_end_time if session_end_time else utcnow(),
            output_parameters=output_parameters,
            subject_info=subject_info,
        )

    @classmethod
    def map_from_json_files(
        cls,
        session_json: os.PathLike,
        rig_json: os.PathLike,
        task_logic_json: os.PathLike,
        session_model: Type[AindBehaviorSessionModel],
        rig_model: Type[AindBehaviorRigModel],
        task_logic_model: Type[AindBehaviorTaskLogicModel],
        repository: Union[os.PathLike, git.Repo],
        script_path: os.PathLike,
        session_end_time: Optional[datetime.datetime],
        session_directory: Optional[os.PathLike] = None,
        output_parameters: Optional[Dict] = None,
        subject_info: Optional[SubjectInfo] = None,
        **kwargs,
    ) -> Self:
        return cls(
            session_model=model_from_json_file(session_json, session_model),
            rig_model=model_from_json_file(rig_json, rig_model),
            task_logic_model=model_from_json_file(task_logic_json, task_logic_model),
            session_directory=session_directory,
            repository=repository,
            script_path=script_path,
            session_end_time=session_end_time if session_end_time else utcnow(),
            output_parameters=output_parameters,
            subject_info=subject_info,
            **kwargs,
        )

    @classmethod
    def _map(
        cls,
        session_model: AindBehaviorSessionModel,
        rig_model: AindBehaviorRigModel,
        task_logic_model: AindBehaviorTaskLogicModel,
        repository: Union[os.PathLike, git.Repo],
        script_path: os.PathLike,
        session_end_time: Optional[datetime.datetime] = None,
        output_parameters: Optional[Dict] = None,
        subject_info: Optional[SubjectInfo] = None,
    ) -> aind_data_schema.core.session.Session:
        if isinstance(repository, os.PathLike | str):
            repository = git.Repo(Path(repository))
        repository_remote_url = repository.remote().url
        repository_sha = repository.head.commit.hexsha
        repository_relative_script_path = Path(script_path).resolve().relative_to(repository.working_dir)

        # Populate calibrations:
        calibrations = [
            cls._mapper_calibration(_calibration_model[1])
            for _calibration_model in data_mapper_service.get_fields_of_type(rig_model, Calibration)
        ]
        # Populate cameras
        cameras = data_mapper_service.get_cameras(rig_model, exclude_without_video_writer=True)
        # populate devices
        devices = [
            device[0] for device in data_mapper_service.get_fields_of_type(rig_model, AbsRig.Device) if device[0]
        ]
        # Populate modalities
        modalities: list[aind_data_schema.core.session.Modality] = [
            getattr(aind_data_schema.core.session.Modality, "BEHAVIOR")
        ]
        if len(cameras) > 0:
            modalities.append(getattr(aind_data_schema.core.session.Modality, "BEHAVIOR_VIDEOS"))
        modalities = list(set(modalities))
        # Populate stimulus modalities
        stimulus_modalities: list[aind_data_schema.core.session.StimulusModality] = []

        if data_mapper_service.get_fields_of_type(rig_model, AbsRig.Screen):
            stimulus_modalities.extend(
                [
                    aind_data_schema.core.session.StimulusModality.VISUAL,
                    aind_data_schema.core.session.StimulusModality.VIRTUAL_REALITY,
                ]
            )
        if data_mapper_service.get_fields_of_type(rig_model, AbsRig.HarpOlfactometer):
            stimulus_modalities.append(aind_data_schema.core.session.StimulusModality.OLFACTORY)
        if data_mapper_service.get_fields_of_type(rig_model, AbsRig.HarpTreadmill):
            stimulus_modalities.append(aind_data_schema.core.session.StimulusModality.WHEEL_FRICTION)

        # Mouse platform

        mouse_platform: str
        if data_mapper_service.get_fields_of_type(rig_model, AbsRig.HarpTreadmill):
            mouse_platform = "Treadmill"
            active_mouse_platform = True
        elif data_mapper_service.get_fields_of_type(rig_model, AbsRig.HarpLoadCells):
            mouse_platform = "TubeWithLoadCells"
            active_mouse_platform = True
        else:
            mouse_platform = "None"
            active_mouse_platform = False

        # Reward delivery
        reward_delivery_config = aind_data_schema.core.session.RewardDeliveryConfig(
            reward_solution=aind_data_schema.core.session.RewardSolution.WATER, reward_spouts=[]
        )

        # Construct aind-data-schema session
        aind_data_schema_session = aind_data_schema.core.session.Session(
            animal_weight_post=subject_info.animal_weight_post if subject_info else None,
            animal_weight_prior=subject_info.animal_weight_prior if subject_info else None,
            reward_consumed_total=subject_info.reward_consumed_total if subject_info else None,
            reward_delivery=reward_delivery_config,
            experimenter_full_name=session_model.experimenter,
            session_start_time=session_model.date,
            session_type=session_model.experiment,
            rig_id=rig_model.rig_name,
            subject_id=session_model.subject,
            notes=session_model.notes,
            data_streams=[
                aind_data_schema.core.session.Stream(
                    daq_names=devices,
                    stream_modalities=modalities,
                    stream_start_time=session_model.date,
                    stream_end_time=session_end_time if session_end_time else session_model.date,
                    camera_names=list(cameras.keys()),
                ),
            ],
            calibrations=calibrations,
            mouse_platform_name=mouse_platform,
            active_mouse_platform=active_mouse_platform,
            stimulus_epochs=[
                aind_data_schema.core.session.StimulusEpoch(
                    stimulus_name=session_model.experiment,
                    stimulus_start_time=session_model.date,
                    stimulus_end_time=session_end_time if session_end_time else session_model.date,
                    stimulus_modalities=stimulus_modalities,
                    software=[
                        aind_data_schema.core.session.Software(
                            name="Bonsai",
                            version=f"{repository_remote_url}/blob/{repository_sha}/bonsai/Bonsai.config",
                            url=f"{repository_remote_url}/blob/{repository_sha}/bonsai",
                            parameters={
                                "data_mapper_service.snapshot_bonsai_environment": r'(config_file=Path("./bonsai/bonsai.config")'
                            },
                        ),
                        aind_data_schema.core.session.Software(
                            name="Python",
                            version=f"{repository_remote_url}/blob/{repository_sha}/pyproject.toml",
                            url=f"{repository_remote_url}/blob/{repository_sha}",
                            parameters=data_mapper_service.snapshot_python_environment(),
                        ),
                    ],
                    script=aind_data_schema.core.session.Software(
                        name=Path(script_path).stem,
                        version=session_model.commit_hash if session_model.commit_hash else repository_sha,
                        url=f"{repository_remote_url}/blob/{repository_sha}/{repository_relative_script_path}",
                        parameters=task_logic_model.model_dump(),
                    ),
                    output_parameters=output_parameters if output_parameters else {},
                )  # type: ignore
            ],
        )  # type: ignore
        return aind_data_schema_session

    @staticmethod
    def _mapper_calibration(calibration: Calibration) -> aind_data_schema.components.devices.Calibration:
        return aind_data_schema.components.devices.Calibration(
            device_name=calibration.device_name,
            input=calibration.input.model_dump() if calibration.input else {},
            output=calibration.output.model_dump() if calibration.output else {},
            calibration_date=calibration.date if calibration.date else utcnow(),
            description=calibration.description if calibration.description else "",
            notes=calibration.notes,
        )

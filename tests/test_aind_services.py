import datetime
import unittest
from pathlib import Path
from typing import Dict, List, Literal, Optional

import pydantic
import yaml
from aind_behavior_services.rig import AindBehaviorRigModel, CameraController, CameraTypes, SpinnakerCamera
from aind_behavior_services.session import AindBehaviorSessionModel
from aind_behavior_services.task_logic import AindBehaviorTaskLogicModel, TaskParameters
from aind_behavior_services.utils import utcnow

from aind_behavior_experiment_launcher.data_mappers import aind_data_schema as aind_data_schema_data_mapper
from aind_behavior_experiment_launcher.data_transfer import watchdog_service


class AindServicesTests(unittest.TestCase):
    def test_session_mapper(self):
        mapper = aind_data_schema_data_mapper.AindDataSchemaSessionDataMapper(
            session_model=MockSession(),
            rig_model=MockRig(),
            task_logic_model=MockTaskLogic(),
            session_end_time=utcnow(),
            repository=Path("./"),
            script_path=Path("./src/unit_test.bonsai"),
        )
        self.assertFalse(mapper.is_mapped())
        mapper.map()
        self.assertTrue(mapper.is_mapped())

    def test_watchdog_manifest(self):
        mapper = aind_data_schema_data_mapper.AindDataSchemaSessionDataMapper(
            session_model=MockSession(),
            rig_model=MockRig(),
            task_logic_model=MockTaskLogic(),
            session_end_time=utcnow(),
            repository=Path("./"),
            script_path=Path("./src/unit_test.bonsai"),
        )
        mapper.map()
        mapper.session_directory = Path("mock_path")

        _watchdog = watchdog_service.WatchdogDataTransferService(
            destination="mock_path",
            aind_data_mapper=mapper,
            project_name="Cognitive flexibility in patch foraging",
            schedule_time=datetime.time(hour=20),
            validate=False,
        )

        config = _watchdog.manifest_config_builder()

        self.assertEqual(
            config,
            watchdog_service.ManifestConfig.model_validate_json(config.model_dump_json()),
            "Manifest config round trip failed",
        )

        round_via_yaml = watchdog_service.ManifestConfig.model_validate(yaml.safe_load(_watchdog._yaml_dump(config)))
        self.assertEqual(config, round_via_yaml, "Manifest config round trip failed via yaml")


class MockRig(AindBehaviorRigModel):
    version: Literal["0.0.0"] = "0.0.0"
    rig_name: str = pydantic.Field(default="MockRig", description="Rig name")
    camera_controllers: Optional[CameraController[SpinnakerCamera]] = pydantic.Field(
        default=None, description="Camera controllers"
    )
    camera_controllers_2: CameraController[SpinnakerCamera] = pydantic.Field(
        default=CameraController[SpinnakerCamera](
            frame_rate=120, cameras={"cam0": SpinnakerCamera(serial_number="12")}
        ),
        validate_default=True,
    )
    camera_controllers_3: CameraController[SpinnakerCamera] = pydantic.Field(
        default=CameraController[SpinnakerCamera](
            frame_rate=120,
            cameras={"cam0": SpinnakerCamera(serial_number="12"), "cam1": SpinnakerCamera(serial_number="22")},
        ),
        validate_default=True,
    )
    a: List[CameraTypes] = pydantic.Field(default=[SpinnakerCamera(serial_number="12")])


def MockSession() -> AindBehaviorSessionModel:
    return AindBehaviorSessionModel(
        experiment="MockExperiment",
        root_path="MockRootPath",
        subject="0000",
        experiment_version="0.0.0",
    )


class MockTasLogicParameters(TaskParameters):
    foo: int = 1
    bar: str = "bar"
    baz: List[int] = [1, 2, 3]
    qux: Dict[str, int] = {"a": 1, "b": 2, "c": 3}


class MockTaskLogic(AindBehaviorTaskLogicModel):
    version: Literal["0.0.0"] = "0.0.0"
    task_parameters: MockTasLogicParameters = MockTasLogicParameters()
    name: str = "MockTaskLogic"


if __name__ == "__main__":
    unittest.main()

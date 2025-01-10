from __future__ import annotations

import logging
import os
import re
import xml.etree.ElementTree as ET
from importlib import metadata
from pathlib import Path
from typing import Dict, List, TypeVar, Union

import pydantic
from aind_behavior_services import (
    AindBehaviorRigModel,
)
from aind_behavior_services.rig import CameraController, CameraTypes
from aind_behavior_services.utils import get_fields_of_type

logger = logging.getLogger(__name__)


T = TypeVar("T")


def get_cameras(
    rig_instance: AindBehaviorRigModel, exclude_without_video_writer: bool = True
) -> Dict[str, CameraTypes]:
    cameras: dict[str, CameraTypes] = {}
    camera_controllers = [x[1] for x in get_fields_of_type(rig_instance, CameraController)]

    for controller in camera_controllers:
        if exclude_without_video_writer:
            these_cameras = {k: v for k, v in controller.cameras.items() if v.video_writer is not None}
        else:
            these_cameras = controller.cameras
        cameras.update(these_cameras)
    return cameras


ISearchable = Union[pydantic.BaseModel, Dict, List]


def _sanity_snapshot_keys(snapshot: Dict[str, str]) -> Dict[str, str]:
    # Sanitize the key names https://github.com/AllenNeuralDynamics/Aind.Behavior.ExperimentLauncher/issues/18
    return {re.sub(r"[.$]", "_", k): v for k, v in snapshot.items()}


def snapshot_python_environment() -> Dict[str, str]:
    return _sanity_snapshot_keys({dist.name: dist.version for dist in metadata.distributions()})


def snapshot_bonsai_environment(
    config_file: os.PathLike = Path("./bonsai/bonsai.config"),
) -> Dict[str, str]:
    tree = ET.parse(Path(config_file))
    root = tree.getroot()
    packages = root.findall("Packages/Package")
    return _sanity_snapshot_keys({leaf.attrib["id"]: leaf.attrib["version"] for leaf in packages})

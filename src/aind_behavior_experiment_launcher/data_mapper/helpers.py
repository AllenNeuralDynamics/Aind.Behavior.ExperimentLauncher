from __future__ import annotations

import logging
import os
import re
import xml.etree.ElementTree as ET
from importlib import metadata
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple, Type, TypeVar, Union, get_args

import pydantic
from aind_behavior_services import (
    AindBehaviorRigModel,
)
from aind_behavior_services.rig import CameraController, CameraTypes

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
_ISearchableTypeChecker = tuple(get_args(ISearchable))  # pre-compute for performance


def get_fields_of_type(
    searchable: ISearchable,
    target_type: Type[T],
    *args,
    recursive: bool = True,
    stop_recursion_on_type: bool = True,
    **kwargs,
) -> List[Tuple[Optional[str], T]]:
    _iterable: Iterable
    _is_type: bool
    result: List[Tuple[Optional[str], T]] = []

    if isinstance(searchable, dict):
        _iterable = searchable.items()
    elif isinstance(searchable, list):
        _iterable = list(zip([None for _ in range(len(searchable))], searchable))
    elif isinstance(searchable, pydantic.BaseModel):
        _iterable = {k: getattr(searchable, k) for k in searchable.model_fields.keys()}.items()
    else:
        raise ValueError(f"Unsupported model type: {type(searchable)}")

    for name, field in _iterable:
        _is_type = False
        if isinstance(field, target_type):
            result.append((name, field))
            _is_type = True
        if recursive and isinstance(field, _ISearchableTypeChecker) and not (stop_recursion_on_type and _is_type):
            result.extend(
                get_fields_of_type(
                    field,
                    target_type,
                    recursive=recursive,
                    stop_recursion_on_type=stop_recursion_on_type,
                )
            )
    return result


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

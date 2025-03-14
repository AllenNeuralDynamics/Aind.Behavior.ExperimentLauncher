import os
import shutil
from pathlib import Path

from ._base import Constraint


def available_storage_constraint_factory(drive: os.PathLike = Path(r"C:\\"), min_bytes: float = 2e11) -> Constraint:
    if not os.path.ismount(drive):
        drive = os.path.splitdrive(drive)[0] + "\\"
    if drive is None:
        raise ValueError("Drive is not valid.")
    return Constraint(
        name="available_storage",
        constraint=lambda drive, min_bytes: shutil.disk_usage(drive).free >= min_bytes,
        args=[],
        kwargs={"drive": drive, "min_bytes": min_bytes},
        fail_msg_handler=lambda drive, min_bytes: f"Drive {drive} does not have enough space.",
    )


def remote_dir_exists_constraint_factory(dir_path: os.PathLike) -> Constraint:
    return Constraint(
        name="remote_dir_exists",
        constraint=lambda dir_path: os.path.exists(dir_path),
        args=[],
        kwargs={"dir_path": dir_path},
        fail_msg_handler=lambda dir_path: f"Directory {dir_path} does not exist.",
    )

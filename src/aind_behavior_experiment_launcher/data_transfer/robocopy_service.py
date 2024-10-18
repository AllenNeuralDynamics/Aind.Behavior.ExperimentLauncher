import logging
import shutil
import subprocess
from os import PathLike
from pathlib import Path
from typing import Dict, Literal, Optional, overload

from .data_transfer_service import DataTransferService

logger = logging.getLogger(__name__)

DEFAULT_EXTRA_ARGS = "/E /DCOPY:DAT /R:100 /W:3 /tee"


class RobocopyService(DataTransferService):
    def __init__(
        self,
        destination: Optional[PathLike] = None,
        log: Optional[PathLike] = None,
        extra_args: Optional[str] = None,
    ):
        self.destination = destination
        self.log = log
        self.extra_args = extra_args if extra_args else DEFAULT_EXTRA_ARGS

    def transfer(
        self,
        source: PathLike,
        destination: Optional[PathLike] = None,
        delete_src: bool = False,
        overwrite: bool = False,
        force_dir: bool = True,
        *args, **kwargs
    ) -> None:
        # Loop through each source-destination pair and call robocopy'
        destination = destination if destination else self.destination
        if not destination:
            raise ValueError("Destination should be provided in constructor or transfer() method.")
        src_dist = self._solve_src_dst_mapping(source, destination)
        if src_dist is None:
            raise ValueError("Source and destination should be provided.")

        for src, dst in src_dist.items():
            try:
                command = ["robocopy", f'"{str(Path(src))}"', f'"{str(Path(dst))}"', self.extra_args]
                if self.log:
                    command.append(f'/LOG:"{Path(dst) / self.log}"')
                if delete_src:
                    command.append("/MOV")
                if overwrite:
                    command.append("/IS")
                if force_dir:
                    command.append("/CREATE")
                cmd = " ".join(command)
                result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                result.check_returncode()
                logger.info("Successfully copied from %s to %s:\n%s", src, dst, result.stdout)
            except subprocess.CalledProcessError as e:
                logger.error("Error copying from %s to %s:\n%s", src, dst, e.stdout)

    @staticmethod
    def _solve_src_dst_mapping(
        source: Optional[PathLike | Dict[PathLike, PathLike]], destination: Optional[PathLike]
    ) -> Optional[Dict[PathLike, PathLike]]:
        if source is None:
            return None
        if isinstance(source, dict):
            if destination:
                raise ValueError("Destination should not be provided when source is a dictionary.")
            else:
                return source
        else:
            source = Path(source)
            if not destination:
                raise ValueError("Destination should be provided when source is a single path.")
            return {source: Path(destination)}

    def validate(self, *args, **kwargs):
        if not shutil.which("robocopy"):
            logger.error("Robocopy command is not available on this system.")
            return False
        return True

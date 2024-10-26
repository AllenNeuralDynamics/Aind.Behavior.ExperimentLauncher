import logging
import shutil
import subprocess
from os import PathLike
from pathlib import Path
from typing import Dict, Optional

from .data_transfer_service import DataTransferService

logger = logging.getLogger(__name__)

DEFAULT_EXTRA_ARGS = "/E /DCOPY:DAT /R:100 /W:3 /tee"


class RobocopyService(DataTransferService):
    def __init__(
        self,
        source: PathLike,
        destination: PathLike,
        log: Optional[PathLike] = None,
        extra_args: Optional[str] = None,
        delete_src: bool = False,
        overwrite: bool = False,
        force_dir: bool = True,
    ):
        self.source = source
        self.destination = destination
        self.delete_src = delete_src
        self.overwrite = overwrite
        self.force_dir = force_dir
        self.log = log
        self.extra_args = extra_args if extra_args else DEFAULT_EXTRA_ARGS

    def transfer(
        self,
    ) -> None:
        # Loop through each source-destination pair and call robocopy'
        logger.info("Starting robocopy transfer service.")
        src_dist = self._solve_src_dst_mapping(self.source, self.destination)
        if src_dist is None:
            raise ValueError("Source and destination should be provided.")

        for src, dst in src_dist.items():
            dst = Path(dst)
            src = Path(src)
            try:
                command = ["robocopy", f"{src.as_posix()}", f"{dst.as_posix()}", self.extra_args]
                if self.log:
                    command.append(f'/LOG:"{Path(dst) / self.log}"')
                if self.delete_src:
                    command.append("/MOV")
                if self.overwrite:
                    command.append("/IS")
                if self.force_dir:
                    command.append("/CREATE")
                cmd = " ".join(command)
                logger.info("Running Robocopy command: %s", " ".join(command))
                with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) as process:
                    if process.stdout:
                        for line in process.stdout:
                            logger.info(line.strip())
                _ = process.wait()
                logger.info("Successfully copied from %s to %s:\n", src, dst)
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

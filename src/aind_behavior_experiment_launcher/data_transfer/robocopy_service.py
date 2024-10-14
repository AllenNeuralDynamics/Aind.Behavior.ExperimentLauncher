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
    @overload
    def __init__(
        self,
        source: Dict[PathLike, PathLike],
        destination: Literal[None] = None,
        log: Optional[PathLike] = None,
        extra_args: Optional[str] = None,
    ):
        pass

    @overload
    def __init__(
        self,
        source: PathLike,
        destination: PathLike,
        log: Optional[PathLike] = None,
        extra_args: Optional[str] = None,
    ):
        pass

    def __init__(
        self,
        source: PathLike | Dict[PathLike, PathLike],
        destination: Optional[PathLike] = None,
        log: Optional[PathLike] = None,
        extra_args: Optional[str] = None,
    ):
        self._src_dst_mapping = self._solve_src_dst_mapping(source, destination)
        self.log = log
        self.extra_args = extra_args if extra_args else DEFAULT_EXTRA_ARGS

    def transfer(
        self, delete_src: bool = False, overwrite: bool = False, force_dir: bool = True, *args, **kwargs
    ) -> None:
        # Loop through each source-destination pair and call robocopy
        for src, dst in self._src_dst_mapping.items():
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
        source: PathLike | Dict[PathLike, PathLike], destination: Optional[PathLike]
    ) -> Dict[PathLike, PathLike]:
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

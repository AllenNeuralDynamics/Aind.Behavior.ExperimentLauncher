from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Self

from ._base import App

logger = logging.getLogger(__name__)

_HAS_UV = shutil.which("uv") is not None

if not _HAS_UV:
    logging.error("uv executable not detected.")
    raise RuntimeError(
        "uv is not installed in this computer. Please install uv. see https://docs.astral.sh/uv/getting-started/installation/"
    )


class PythonScriptApp(App):
    def __init__(
        self,
        /,
        script: str,
        additional_arguments: str = "",
        project_directory: os.PathLike = Path("."),
        optional_toml_dependencies: Optional[list[str]] = None,
        append_python_exe: bool = False,
        timeout: Optional[float] = None,
    ) -> None:
        self._script = script
        self._project_directory = project_directory
        self._timeout = timeout
        self._optional_toml_dependencies = optional_toml_dependencies if optional_toml_dependencies else []
        self._append_python_exe = append_python_exe
        self._additional_arguments = additional_arguments

        self._result: Optional[subprocess.CompletedProcess] = None

    @property
    def result(self) -> subprocess.CompletedProcess:
        if self._result is None:
            raise RuntimeError("The app has not been run yet.")
        return self._result

    def run(self) -> subprocess.CompletedProcess:
        logger.info("Starting python script %s...", self._script)

        if not self._has_venv():
            logging.warning("Python environment not found. Creating one...")
            self.create_environment()

        _script = f"{self._script} {self._additional_arguments}"
        _python_exe = "python" if self._append_python_exe else ""
        command = f"uv run {_python_exe} {_script} {self._add_uv_optional_toml_dependencies()}"

        try:
            proc = subprocess.run(
                command,
                shell=False,
                capture_output=True,
                text=True,
                check=True,
                cwd=self._project_directory,
            )
        except subprocess.CalledProcessError as e:
            logger.error("Error creating Python environment. %s", e)
            raise e

        logger.info("Python script completed.")
        return proc

    def output_from_result(self, allow_stderr: Optional[bool] = True) -> Self:
        proc = self.result
        try:
            proc.check_returncode()
        except subprocess.CalledProcessError as e:
            self._log_process_std_output(self._script, proc)
            raise e
        else:
            self._log_process_std_output(self._script, proc)
            if len(proc.stdout) > 0 and allow_stderr is False:
                raise subprocess.CalledProcessError(1, proc.args)
        return self

    def _log_process_std_output(self, process_name: str, proc: subprocess.CompletedProcess) -> None:
        if len(proc.stdout) > 0:
            logger.info("%s full stdout dump: \n%s", process_name, proc.stdout)
        if len(proc.stderr) > 0:
            logger.error("%s full stderr dump: \n%s", process_name, proc.stderr)

    def prompt_input(self, *args, **kwargs) -> Self:
        raise NotImplementedError("Not implemented yet.")

    def _has_venv(self) -> bool:
        return (Path(self._project_directory) / ".venv").exists()

    def create_environment(self, run_kwargs: Optional[dict[str, any]] = None) -> subprocess.CompletedProcess:
        logger.info("Creating Python environment with uv venv at %s...", self._project_directory)
        run_kwargs = run_kwargs or {}
        try:
            proc = subprocess.run(
                f"uv venv {self._add_uv_project_directory()} ",
                shell=False,
                capture_output=True,
                text=True,
                check=True,
                cwd=self._project_directory,
                **run_kwargs,
            )
            proc.check_returncode()
        except subprocess.CalledProcessError as e:
            logger.error("Error creating Python environment. %s", e)
            raise e
        return proc

    def _add_uv_project_directory(self) -> str:
        return f" --directory {self._project_directory}"

    def _add_uv_optional_toml_dependencies(self) -> str:
        return " ".join([f"--extra {dep}" for dep in self._optional_toml_dependencies])

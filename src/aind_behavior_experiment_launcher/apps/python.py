from __future__ import annotations
import subprocess
from aind_behavior_experiment_launcher.apps import App
from typing import Literal, Optional
import logging
from dataclasses import dataclass, field
import abc
from pathlib import Path
import os
import shutil
from typing import Self


logger = logging.getLogger(__name__)

_HAS_UV = shutil.which("uv") is not None

if not _HAS_UV:
    logging.error("uv executable not detected.")
    raise RuntimeError("uv is not installed in this computer. Please install uv. see https://docs.astral.sh/uv/getting-started/installation/")


@dataclass
class UvEnvironmentManager():
    project_directory: os.PathLike = Path(".")
    optional_toml_dependencies: list[str] = field(default_factory=list)

    def _add_uv_project_directory(self) -> str:
        return f" --directory {self.project_directory}"

    def _add_uv_optional_toml_dependencies(self) -> str:
        return " ".join([f"--extra {dep}" for dep in self.optional_toml_dependencies])

    def create_environment(self, run_kwargs: Optional[dict[str, any]] = None) -> subprocess.CompletedProcess:
        logger.info("Creating Python environment with uv venv at %s...", self.project_directory)
        run_kwargs = run_kwargs or {}
        proc = subprocess.run(
            f"uv venv {self._add_uv_project_directory()} ",
            shell=True,
            capture_output=True,
            text=True,
            check=True,
            cwd=self.project_directory,
            **run_kwargs
        )
        return proc

    def run_command(self, command: str, run_kwargs: Optional[dict[str, any]] = None) -> subprocess.CompletedProcess:
        logger.info("Running command %s in uv venv at %s...", command, self.project_directory)
        run_kwargs = run_kwargs or {}
        print(f"uv run {command} {self._add_uv_optional_toml_dependencies()}")
        proc = subprocess.run(
            f"uv run {command} {self._add_uv_optional_toml_dependencies()}",
            shell=True,
            capture_output=True,
            text=True,
            check=True,
            cwd=self.project_directory,
            **run_kwargs
        )
        print(proc)
        return proc


class PythonScriptApp(App):
    def __init__(self, /,
                 script: str,
                 project_directory: os.PathLike = Path("."),
                 optional_toml_dependencies: Optional[list[str]] = None,
                 append_python_exe: bool = False,
                 timeout: Optional[float] = None) -> None:
        self._script = script
        self._project_directory = project_directory
        self._timeout = timeout
        self._optional_toml_dependencies = optional_toml_dependencies if optional_toml_dependencies else []
        self._append_python_exe = append_python_exe

        self._environment_manager = UvEnvironmentManager(project_directory=self._project_directory, optional_toml_dependencies=self._optional_toml_dependencies)
        self._result: Optional[subprocess.CompletedProcess] = None

    @property
    def result(self) -> subprocess.CompletedProcess:
        if self._result is None:
            raise RuntimeError("The app has not been run yet.")
        return self._result

    def create_environment(self) -> subprocess.CompletedProcess:
        proc = self._environment_manager.create_environment(run_kwargs={"timeout": self._timeout})
        try:
            proc.check_returncode()
        except subprocess.CalledProcessError as e:
            logger.error("Error creating Python environment. %s", e)
            raise e
        return proc

    def run(self) -> subprocess.CompletedProcess:
        logger.info("Starting Python process...")
        if self._append_python_exe:
            proc = self._environment_manager.run_command(f"python {self._script}", run_kwargs={"timeout": self._timeout})
        else:
            proc = self._environment_manager.run_command(f"{self._script}", run_kwargs={"timeout": self._timeout})
        logger.info("Python process completed.")
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


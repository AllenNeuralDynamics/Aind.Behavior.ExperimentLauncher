from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional, Self

from typing_extensions import override

from ._base import App

logger = logging.getLogger(__name__)

_HAS_UV = shutil.which("uv") is not None


class PythonScriptApp(App):
    """
    PythonScriptApp is a class that facilitates running Python scripts within a managed environment.
    It ensures the presence of a virtual environment, handles dependencies, and executes the script
    with specified arguments.
    Attributes:
        _script (str): The Python script to be executed.
        _project_directory (os.PathLike): The directory where the project resides.
        _timeout (Optional[float]): Timeout for the script execution.
        _optional_toml_dependencies (list[str]): Additional TOML dependencies to be included.
        _append_python_exe (bool): Whether to append the Python executable to the command.
        _additional_arguments (str): Additional arguments to pass to the script.
        _result (Optional[subprocess.CompletedProcess]): The result of the executed script.
    Methods:
        __init__(script, additional_arguments, project_directory, optional_toml_dependencies, append_python_exe, timeout):
            Initializes the PythonScriptApp with the specified parameters.
        result:
            Property that retrieves the result of the executed script. Raises an error if the script has not been run.
        run():
            Executes the Python script within the managed environment. Creates a virtual environment if one does not exist.
        output_from_result(allow_stderr):
            Processes the output of the executed script. Logs stdout and stderr, and optionally raises an error if stderr is present.
        _log_process_std_output(process_name, proc):
            Logs the stdout and stderr of a completed process.
        _has_venv():
            Checks if a virtual environment exists in the project directory.
        create_environment(run_kwargs):
            Creates a Python virtual environment using the `uv` tool.
        _add_uv_project_directory():
            Constructs the `--directory` argument for the `uv` command.
        _add_uv_optional_toml_dependencies():
            Constructs the `--extra` arguments for the `uv` command based on optional TOML dependencies.
        _validate_uv():
            Validates the presence of the `uv` executable. Raises an error if it is not installed.
    """

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
        """
        Initializes the PythonScriptApp with the specified parameters.

        Args:
            script (str): The Python script to be executed.
            additional_arguments (str): Additional arguments to pass to the script.
            project_directory (os.PathLike): The directory where the project resides.
            optional_toml_dependencies (Optional[list[str]]): Additional TOML dependencies to include.
            append_python_exe (bool): Whether to append the Python executable to the command.
            timeout (Optional[float]): Timeout for the script execution.
        """
        self._validate_uv()
        self._script = script
        self._project_directory = project_directory
        self._timeout = timeout
        self._optional_toml_dependencies = optional_toml_dependencies if optional_toml_dependencies else []
        self._append_python_exe = append_python_exe
        self._additional_arguments = additional_arguments

        self._result: Optional[subprocess.CompletedProcess] = None

    @property
    def result(self) -> subprocess.CompletedProcess:
        """
        Retrieves the result of the executed script.

        Returns:
            subprocess.CompletedProcess: The result of the executed script.

        Raises:
            RuntimeError: If the script has not been run yet.
        """
        if self._result is None:
            raise RuntimeError("The app has not been run yet.")
        return self._result

    @override
    def run(self) -> subprocess.CompletedProcess:
        """
        Executes the Python script within the managed environment.

        Returns:
            subprocess.CompletedProcess: The result of the executed script.

        Raises:
            subprocess.CalledProcessError: If the script execution fails.
        """
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

    @override
    def output_from_result(self, allow_stderr: Optional[bool] = True) -> Self:
        """
        Processes the output of the executed script.

        Args:
            allow_stderr (Optional[bool]): Whether to allow stderr in the output.

        Returns:
            Self: The current instance.

        Raises:
            subprocess.CalledProcessError: If the script execution fails or stderr is present when not allowed.
        """
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
        """
        Logs the stdout and stderr of a completed process.

        Args:
            process_name (str): The name of the process.
            proc (subprocess.CompletedProcess): The completed process.
        """
        if len(proc.stdout) > 0:
            logger.info("%s full stdout dump: \n%s", process_name, proc.stdout)
        if len(proc.stderr) > 0:
            logger.error("%s full stderr dump: \n%s", process_name, proc.stderr)

    def _has_venv(self) -> bool:
        """
        Checks if a virtual environment exists in the project directory.

        Returns:
            bool: True if a virtual environment exists, False otherwise.
        """
        return (Path(self._project_directory) / ".venv").exists()

    def create_environment(self, run_kwargs: Optional[dict[str, Any]] = None) -> subprocess.CompletedProcess:
        """
        Creates a Python virtual environment using the `uv` tool.

        Args:
            run_kwargs (Optional[dict[str, Any]]): Additional arguments for the `subprocess.run` call.

        Returns:
            subprocess.CompletedProcess: The result of the environment creation process.

        Raises:
            subprocess.CalledProcessError: If the environment creation fails.
        """
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
        """
        Constructs the `--directory` argument for the `uv` command.

        Returns:
            str: The `--directory` argument.
        """
        return f" --directory {self._project_directory}"

    def _add_uv_optional_toml_dependencies(self) -> str:
        """
        Constructs the `--extra` arguments for the `uv` command based on optional TOML dependencies.

        Returns:
            str: The `--extra` arguments.
        """
        return " ".join([f"--extra {dep}" for dep in self._optional_toml_dependencies])

    @staticmethod
    def _validate_uv() -> bool:
        """
        Validates the presence of the `uv` executable.

        Returns:
            bool: True if `uv` is installed.

        Raises:
            RuntimeError: If `uv` is not installed.
        """
        if not _HAS_UV:
            logging.error("uv executable not detected.")
            raise RuntimeError(
                "uv is not installed in this computer. Please install uv. see https://docs.astral.sh/uv/getting-started/installation/"
            )
        return True

import logging
import os
import subprocess
from pathlib import Path
from typing import Literal, Optional, Self

from aind_behavior_services.rig import AindBehaviorRigModel
from aind_behavior_services.session import AindBehaviorSessionModel
from aind_behavior_services.task_logic import AindBehaviorTaskLogicModel
from pydantic import Field
from typing_extensions import override

from aind_behavior_experiment_launcher import resource_monitor
from aind_behavior_experiment_launcher.apps import App
from aind_behavior_experiment_launcher.launcher import BaseCliArgs
from aind_behavior_experiment_launcher.launcher.behavior_launcher import (
    BehaviorLauncher,
    BehaviorServicesFactoryManager,
    DefaultBehaviorPicker,
)

logger = logging.getLogger(__name__)

TASK_NAME = "RandomTask"
LIB_CONFIG = rf"local\AindBehavior.db\{TASK_NAME}"


class RigModel(AindBehaviorRigModel):
    rig_name: str = Field("TestRig", description="Rig name")
    version: Literal["0.0.0"] = "0.0.0"


class TaskLogicModel(AindBehaviorTaskLogicModel):
    version: Literal["0.0.0"] = "0.0.0"
    name: Literal[TASK_NAME] = TASK_NAME


class EchoApp(App):
    def __init__(self, value: str) -> None:
        self._value = value
        self._result = None

    @override
    def run(self) -> subprocess.CompletedProcess:
        logger.info("Running EchoApp...")
        command = ["cmd", "/c", "echo", self._value]

        try:
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            logger.error("%s", e)
            raise e
        self._result = proc
        logger.info("EchoApp completed.")
        return proc

    def output_from_result(self, allow_stderr: Optional[bool]) -> Self:
        proc = self.result
        try:
            proc.check_returncode()
        except subprocess.CalledProcessError as e:
            self._log_process_std_output("echo", proc)
            raise e
        else:
            self._log_process_std_output("echo", proc)
            if len(proc.stdout) > 0 and allow_stderr is False:
                raise subprocess.CalledProcessError(1, proc.args)
        return self

    def _log_process_std_output(self, process_name: str, proc: subprocess.CompletedProcess) -> None:
        if len(proc.stdout) > 0:
            logger.info("%s full stdout dump: \n%s", process_name, proc.stdout)
        if len(proc.stderr) > 0:
            logger.error("%s full stderr dump: \n%s", process_name, proc.stderr)

    @property
    def result(self) -> subprocess.CompletedProcess:
        if self._result is None:
            raise RuntimeError("The app has not been run yet.")
        return self._result


DATA_DIR = Path(r"./local/data")
srv = BehaviorServicesFactoryManager()
srv.attach_app(EchoApp("hello world"))
srv.attach_resource_monitor(
    resource_monitor.ResourceMonitor(
        constrains=[
            resource_monitor.available_storage_constraint_factory(DATA_DIR, 2e11),
            resource_monitor.remote_dir_exists_constraint_factory(Path(r"C:/")),
        ]
    )
)


def make_launcher():
    return BehaviorLauncher(
        rig_schema_model=RigModel,
        session_schema_model=AindBehaviorSessionModel,
        task_logic_schema_model=TaskLogicModel,
        picker=DefaultBehaviorPicker(config_library_dir=Path(LIB_CONFIG)),
        services=srv,
        settings=BaseCliArgs(
            data_dir=DATA_DIR,
            temp_dir=Path(r"./local/.temp"),
            allow_dirty=True,
            skip_hardware_validation=True,
            debug_mode=True,
            group_by_subject_log=True,
            validate_init=True,
        ),
    )


def create_fake_subjects():
    subjects = ["00000", "123456"]
    for subject in subjects:
        os.makedirs(f"{LIB_CONFIG}/Subjects/{subject}", exist_ok=True)
        with open(f"{LIB_CONFIG}/Subjects/{subject}/task_logic.json", "w", encoding="utf-8") as f:
            f.write(TaskLogicModel(task_parameters={"subject": subject}).model_dump_json(indent=2))


def create_fake_rig():
    computer_name = os.getenv("COMPUTERNAME")
    os.makedirs(_dir := f"{LIB_CONFIG}/Rig/{computer_name}", exist_ok=True)
    with open(f"{_dir}/rig1.json", "w", encoding="utf-8") as f:
        f.write(RigModel().model_dump_json(indent=2))


def main():
    create_fake_subjects()
    create_fake_rig()
    launcher = make_launcher()
    launcher.main()
    return None


if __name__ == "__main__":
    main()

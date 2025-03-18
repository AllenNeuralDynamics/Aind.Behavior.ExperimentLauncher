import argparse
import os
from pathlib import Path
from typing import Optional, Tuple, Type, TypeVar

from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    CliApp,
    CliImplicitFlag,
    CliSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)


class BaseCliArgs(BaseSettings, cli_parse_args=True, cli_prog_name="clabe", cli_kebab_case=True):
    model_config = SettingsConfigDict(
        env_prefix="CLABE_", yaml_file=["./clabe_default.yml", "./local/clabe_custom.yml"]
    )

    data_dir: os.PathLike = Field(description="The data directory where to save the data")
    repository_dir: Optional[os.PathLike] = Field(default=None, description="The repository root directory")
    create_directories: CliImplicitFlag[bool] = Field(
        default=False, description="Whether to create directory structure necessary for the launcher"
    )
    debug_mode: CliImplicitFlag[bool] = Field(default=False, description="Whether to run in debug mode")
    allow_dirty: CliImplicitFlag[bool] = Field(
        default=False, description="Whether to allow the launcher to run with a dirty repository"
    )
    skip_hardware_validation: CliImplicitFlag[bool] = Field(
        default=False, description="Whether to skip hardware validation"
    )
    subject: Optional[str] = Field(default=None, description="The name of the subject. If None, will be prompted later")
    task_logic_path: Optional[os.PathLike] = Field(
        default=None, description="The path to the task logic schema. If None, will be prompted later"
    )
    rig_path: Optional[os.PathLike] = Field(
        default=None, description="The path to the rig schema. If None, will be prompted later"
    )
    validate_init: CliImplicitFlag[bool] = Field(
        default=True, description="Whether to validate the launcher state during initialization"
    )
    temp_dir: os.PathLike = Field(
        default=Path("local/.temp"), description="The directory used for the launcher temp files"
    )
    group_by_subject_log: CliImplicitFlag[bool] = Field(
        default=True, description="Whether to group data logging by subject"
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            YamlConfigSettingsSource(settings_cls),
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )


_TCliArgs = TypeVar("_TCliArgs", bound=BaseCliArgs)


def run_clabe_cli(cli_args_cls: Type[_TCliArgs], root_parser: Optional[argparse.ArgumentParser] = None) -> _TCliArgs:
    if root_parser is None:
        root_parser = argparse.ArgumentParser()
    cli_settings: CliSettingsSource[_TCliArgs] = CliSettingsSource(
        cli_args_cls, root_parser=root_parser, cli_prog_name="clabe"
    )
    _s = CliApp.run(cli_args_cls, cli_settings_source=cli_settings, cli_cmd_method_name="clabe")
    return _s


class _BaseCliArgsForUnitTests(BaseCliArgs):
    model_config = SettingsConfigDict(cli_parse_args=False)

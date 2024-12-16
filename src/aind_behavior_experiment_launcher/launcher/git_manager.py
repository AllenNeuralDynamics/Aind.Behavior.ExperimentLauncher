import logging
import shutil
from typing import List, Self

from git import Repo

from aind_behavior_experiment_launcher.ui_helper import UIHelper

logger = logging.getLogger(__name__)

_HAS_GIT = shutil.which("git") is not None

if not _HAS_GIT:
    logging.error("git executable not detected.")
    raise RuntimeError("git is not installed in this computer. Please install git. https://git-scm.com/downloads")


class GitRepository(Repo):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def reset_repo(self) -> Self:
        self.git.reset("--hard")
        return self

    def clean_repo(self) -> Self:
        self.git.clean("-fd")
        return self

    def is_dirty_with_submodules(self) -> bool:
        _is_dirty_repo = self.is_dirty(untracked_files=True)
        if _is_dirty_repo:
            return True
        return any([submodule.repo.is_dirty(untracked_files=True) for submodule in self.submodules])

    def untracked_files_with_submodules(self) -> List[str]:
        _untracked_files = self.untracked_files
        for submodule in self.submodules:
            _untracked_files.extend(submodule.repo.untracked_files)
        return _untracked_files

    def force_update_submodules(self) -> Self:
        self.submodule_update()
        return self

    def submodules_sync(self) -> Self:
        self.git.submodule("sync", "--recursive")
        return self

    def full_reset(self) -> Self:
        self.reset_repo().submodules_sync().force_update_submodules().clean_repo()
        _ = [GitRepository(str(sub.abspath)).full_reset() for sub in self.submodules]
        return self

    def try_prompt_full_reset(self, ui_helper: UIHelper, force_reset: bool = False) -> Self:
        if force_reset:
            self.full_reset()
            return self
        if self.is_dirty_with_submodules():
            logger.info("Repository is dirty! %s", self.working_dir)
            logger.info("Untracked files: %s", self.untracked_files_with_submodules())
            if not force_reset:
                is_reset = ui_helper.prompt_yes_no_question(prompt="Do you want to reset the repository?")
            else:
                is_reset = True
            if is_reset:
                logging.info("Full reset of repository and submodules: %s", self.working_dir)
                self.full_reset()
        return self

import logging
import os
from typing import List, Optional

from aind_slims_api import SlimsClient, exceptions, models
from typing_extensions import override

import aind_behavior_experiment_launcher.ui as ui
from aind_behavior_experiment_launcher.ui.picker import _L, _R, _S, _T, DefaultPicker

logger = logging.getLogger(__name__)


class SlimsPicker(DefaultPicker[_L, _R, _S, _T]):
    """
    Picker class that handles the selection of rigs, sessions, and task logic from slims
    """

    def __init__(
        self,
        launcher: Optional[_L] = None,
        *,
        ui_helper: Optional[ui.DefaultUIHelper] = None,
        slims_url: str = None,
        username: str = None,
        password: str = None,
        **kwargs,
    ):
        """
        Initializes the picker with an optional launcher, UI helper, username, and password.

        Args:
            launcher (Optional[_L]): The launcher instance.
            ui_helper (Optional[_UiHelperBase]): The UI helper instance
            slims_url(Optional[str]): slims url. Defaults to dev version of slims if not provided
            username (Optional[str]): slims username. Defaults to SLIMS_USERNAME environment variable if not provided
            password (Optional[str]): slims password. Default sto SLIMS_PASSWORD environment variable if not provided
            **kwargs: Additional keyword arguments.
        """

        super().__init__(launcher, ui_helper=ui_helper, **kwargs)

        self.slims_client = self.connect_to_slims(slims_url, username, password)

        # initialize properties
        self._slims_mouse = None
        self._slims_session = None

    def connect_to_slims(self, url: str = None, username: str = None, password: str = None) -> SlimsClient:
        """
        Connect to Slims with optional username and password or use environment variables

        Args:
            url(Optional[str]): slims url. Defaults to dev version of slims if not provided
            username (Optional[str]): slims username. Defaults to SLIMS_USERNAME environment variable if not provided
            password (Optional[str]): slims password. Defaults to SLIMS_PASSWORD environment variable if not provided

        Returns:
            SlimsClient: slims client instance.

        Raises:
            Exception: If invalid credentials or error reading from slims
        """

        try:
            logger.info("Attempting to connect to Slims")
            slims_client = SlimsClient(
                url=url,
                username=username if username else os.environ["SLIMS_USERNAME"],
                password=password if password else os.environ["SLIMS_PASSWORD"],
            )
            slims_client.fetch_model(models.SlimsMouseContent, barcode="00000000")

        except exceptions.SlimsAPIException as e:
            if "Status 401 – Unauthorized" in str(e):  # catch error if username and password are incorrect
                raise Exception(
                    f"Exception trying to read from Slims: {e}.\n"
                    f" Please check credentials:\n"
                    f"Username: {username if username else os.environ['SLIMS_USERNAME']}\n"
                    f"Password: {password if password else os.environ['SLIMS_PASSWORD']}"
                )
            else:
                raise Exception(f"Exception trying to read from Slims: {e}.\n")

        logger.info("Successfully connected to Slims")

        return slims_client

    @property
    def slims_mouse(self) -> models.mouse:
        """
        Returns slims mouse model being used to load session

        Returns:
            models.Mouse: slims mouse model object
        """

        return self._slims_mouse

    @property
    def slims_session(self) -> models.behavior_session.SlimsBehaviorSession:
        """
        Returns slims session model being used to load task logic

        Returns:
            models.behavior_session.SlimsBehaviorSession: slims session model object
        """

        return self._slims_session

    def pick_rig(self) -> _R:
        """
        Prompts the user to provide a rig name.

        Returns:
            _R: The selected rig configuration.

        Raises:
            SlimsRecordNotFound: If no rig is found in Slims or an invalid choice is made.
        """

        while True:
            try:
                rig_name = self.ui_helper.prompt_text(prompt="Input rig name: ")
                rig = self.slims_client.fetch_model(models.SlimsInstrument, name=rig_name)
                return self.launcher.rig_schema_model(rig_name=rig.name)

            except exceptions.SlimsRecordNotFound as e:
                logger.error("Rig not found in Slims. Try again. %s", e)

    def pick_session(self) -> _S:
        """
        Prompts the user to select or create a session configuration.

        Returns:
            TSession: The created or selected session configuration.

        Raises:
            ValueError: If no session model is found on slims.
        """

        username = self.prompt_username(strict=True)
        if self.launcher.subject is not None:
            logging.info("Subject provided via CLABE: %s", self.launcher.settings.subject)
            subject = self.launcher.subject
        else:
            slims_mice = self.slims_client.fetch_models(models.SlimsMouseContent)[
                -100:
            ]  # grab 100 latest mice from slims
            subject = None
            while subject is None:
                subject = self.ui_helper.input("Enter subject name: ")
                if subject == "":
                    subject = self.ui_helper.prompt_pick_from_list(
                        [mouse.barcode for mouse in slims_mice],
                        prompt="Choose a subject:",
                        allow_0_as_none=True,
                    )
            self.launcher.subject = subject

        self._slims_mouse = self.slims_client.fetch_model(models.SlimsMouseContent, barcode=subject)
        try:
            self._slims_session = self.slims_client.fetch_models(
                models.behavior_session.SlimsBehaviorSession, mouse_pk=self._slims_mouse.pk
            )[-1]
        except IndexError:  # empty list returned from slims
            raise ValueError(f"No session found on slims for mouse {subject}.")

        return self.launcher.session_schema_model(
            experiment="",  # Will be set later
            root_path=str(self.launcher.data_dir.resolve())
            if not self.launcher.group_by_subject_log
            else str(self.launcher.data_dir.resolve() / subject),
            subject=subject,
            notes=self._slims_session.notes,
            experimenter=username if username is not None else [],
            commit_hash=self.launcher.repository.head.commit.hexsha,
            allow_dirty_repo=self.launcher.is_debug_mode or self.launcher.allow_dirty,
            skip_hardware_validation=self.launcher.skip_hardware_validation,
            experiment_version="",  # Will be set later
        )

    def pick_task_logic(self) -> _T:
        """
        Returns task_logic found as an attachment from session loaded from slims.

        Returns:
            TTaskLogic: Task logic found as an attachment from session loaded from slims.

        Raises:
            ValueError: If no valid task logic attachment is found.
        """

        try:  # If the task logic is already set (e.g. from CLI), skip the prompt
            task_logic = self.launcher.task_logic_schema
            assert task_logic is not None
            return task_logic
        except ValueError:
            task_logic = None

        if self._slims_session is not None:
            # check attachments from loaded session
            attachments = self.slims_client.fetch_attachments(self._slims_session)
            try:  # get most recently added task_logic
                response = [
                    self.slims_client.fetch_attachment_content(attach).json()
                    for attach in attachments
                    if attach.name == "task_logic"
                ][0]  # TODO: hardcoded attachment name here. Not sure where/how we should store this value
            except IndexError:  # empty attachment list with loaded session
                raise ValueError(
                    "No task_logic model found on with loaded slims session for mouse"
                    f" {self.launcher.subject}. Please add before continuing."
                )

            return self.launcher.task_logic_schema_model(**response)

        else:
            logger.info("No Slims session loaded.")

    @override
    def initialize(self) -> None:
        """
        Initializes the picker
        """

    def prompt_username(self, strict: bool = True) -> Optional[List[str]]:
        """
        Prompts the user to enter their slims username(s).

        Args:
            strict (bool): Whether to enforce non-empty input.

        Returns:
            Optional[List[str]]: List of usernames names.
        """
        username_lst: Optional[List[str]] = None
        while username_lst is None:
            _user_input = self.ui_helper.prompt_text("Slims  username: ")
            username_lst = _user_input.replace(",", " ").split()
            if strict & (len(username_lst) == 0):
                logger.error("Username is not valid.")
                username_lst = None
            else:  # check if username(s) exist in slims
                invalid = []
                for username in username_lst:
                    try:
                        self.slims_client.fetch_model(models.SlimsUser, username=username)
                    except exceptions.SlimsRecordNotFound:
                        invalid.append(username)

                if invalid:
                    logger.error(f"Slims username(s) {invalid} not found. Please re-enter.")
                    username_lst = None

        return username_lst

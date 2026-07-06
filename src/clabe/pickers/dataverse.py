# Code in this module is largely adapted from https://github.com/AllenNeuralDynamics/dataverse-client
# under the MIT license, with modifications. (thanks patricklatimer for the original code!)

import logging
import os
import re
from datetime import datetime, timedelta, timezone
from html import unescape
from typing import Callable, ClassVar, Optional, Type

import msal
import pydantic
import requests
from aind_behavior_curriculum import TrainerState
from aind_behavior_services.rig import Rig
from pydantic import BaseModel, SecretStr, computed_field, field_validator

from .. import ui
from .._typing import TTask
from ..launcher import Launcher
from ..services import ServiceSettings
from ..utils.aind_validators import validate_rig_computer_name, validate_username
from ..utils.keepass import KeePass, KeePassSettings
from .default_behavior import DefaultBehaviorPicker, DefaultBehaviorPickerSettings

logger = logging.getLogger(__name__)


class _DataverseRestClientSettings(ServiceSettings):
    """
    Settings for the Dataverse rest client.

    Configuration for authenticating and connecting to Microsoft Dataverse,
    including Azure AD settings and organization details.

    Properties:
        username_at_domain: Username with domain for authentication
        api_url: Base URL for the Dataverse API
        env_url: Base URL for the Dataverse environment
        authority: Base URL for the Azure AD authority
        scope: Scope string for the Dataverse API
    """

    __yml_section__: ClassVar[Optional[str]] = "dataverse"

    tenant_id: str
    client_id: str
    org: str
    additional_scopes: list[str] = ["offline_access"]
    username: str
    password: SecretStr
    domain: str = "alleninstitute.org"

    @computed_field
    @property
    def username_at_domain(self) -> str:
        """Username with domain for authentication."""
        if self.username.endswith(f"@{self.domain}"):
            return self.username
        return self.username + "@" + self.domain

    @computed_field
    @property
    def api_url(self) -> str:
        """Base URL for the Dataverse API."""
        return f"https://{self.org}.crm.dynamics.com/api/data/v9.2/"

    @computed_field
    @property
    def env_url(self) -> str:
        """Base URL for the Dataverse environment."""
        return f"https://{self.org}.crm.dynamics.com"

    @computed_field
    @property
    def authority(self) -> str:
        """Base URL for the Azure AD authority."""
        return f"https://login.microsoftonline.com/{self.tenant_id}"

    @computed_field
    @property
    def scope(self) -> str:
        """Scope for the Dataverse API."""
        return f"{self.env_url}/.default " + " ".join(self.additional_scopes)

    @classmethod
    def from_keepass(
        cls, entry_title: str = "svc_sipe", keepass: Optional[KeePass] = None, **kwargs
    ) -> "_DataverseRestClientSettings":
        """
        Create a DataverseSettings instance getting the password from a KeePass entry.

        Args:
            entry_title: Title of the KeePass entry. Defaults to "svc_sipe"
            keepass: An optional KeePass manager instance. If not provided, a new instance will be created with default settings. Defaults to None
            **kwargs: Additional keyword arguments to pass to the DataverseSettings constructor

        Returns:
            _DataverseRestClientSettings: The created DataverseSettings instance
        """
        if keepass is None:
            # KeePassSettings will attempt to load settings using the YAML config if available
            # If not, just let the validation fail and raise an error here.
            keepass = KeePass(settings=KeePassSettings())

        keepass_entry = keepass.get_entry(entry_title)
        if keepass_entry is None or keepass_entry.password is None or keepass_entry.username is None:
            raise ValueError(f"No entry found with title '{entry_title}' or entry has no password")
        return _DataverseRestClientSettings(password=keepass_entry.password, username=keepass_entry.username, **kwargs)


_REQUEST_TIMEOUT = 5


class _DataverseRestClient:
    """Client for basic CRUD operations on Dataverse entities."""

    def __init__(self, config: _DataverseRestClientSettings):
        """
        Initialize the DataverseRestClient with configuration.

        Args:
            config: Config object with credentials and URLs
        """
        self.config = config
        self._msal_app = msal.PublicClientApplication(
            client_id=self.config.client_id,
            authority=self.config.authority,
            client_credential=None,
        )

    @property
    def headers(self) -> dict:
        """Get the headers for Dataverse API requests."""
        return {
            "Authorization": f"Bearer {self._get_access_token()}",
            "OData-MaxVersion": "4.0",
            "OData-Version": "4.0",
            "Accept": "application/json",
            "If-None-Match": None,
            "Content-Type": "application/json",
        }

    def _get_access_token(self) -> str:
        """
        Get a valid access token.

        Returns:
            str: Valid access token

        Raises:
            ValueError: If token acquisition fails
        """
        accounts = self._msal_app.get_accounts(username=self.config.username_at_domain)

        if accounts:
            result = self._msal_app.acquire_token_silent(scopes=[self.config.scope], account=accounts[0])
            if result and "access_token" in result:
                return result["access_token"]

        result = self._msal_app.acquire_token_by_username_password(
            username=self.config.username_at_domain,
            password=self.config.password.get_secret_value(),
            scopes=[self.config.scope],
        )

        if "access_token" in result:
            return result["access_token"]
        else:
            raise ValueError(f"Error acquiring token: {result.get('error')} : {result.get('error_description')}")

    @staticmethod
    def _format_queries(
        filter: Optional[str] = None,
        order_by: Optional[str | list[str]] = None,
        top: Optional[int] = None,
        count: Optional[bool] = None,
        select: Optional[str | list[str]] = None,
        apply: Optional[str] = None,
    ) -> str:
        """
        Format query parameters for a Dataverse API request.

        Args:
            filter: OData filter query. Defaults to None
            order_by: OData order by clause. Defaults to None
            top: OData top value. Defaults to None
            count: Include "@odata.count" in the response, counting matches. Defaults to None
            select: OData select clause. Defaults to None
            apply: OData $apply query (aggregation/grouping), e.g. "filter(...)/groupby((column))"
                or "groupby((navProperty/attribute))" for distinct values through a lookup.
                Defaults to None

        Returns:
            str: Formatted query string
        """
        queries = []
        if apply:
            queries.append(f"$apply={apply}")
        if filter:
            queries.append(f"$filter={filter}")
        if order_by:
            if isinstance(order_by, str):
                order_by = [order_by]
            queries.append(f"$orderby={','.join(order_by)}")
        if top is not None:
            queries.append(f"$top={top}")
        if count is not None:
            queries.append(f"$count={str(count).lower()}")
        if select:
            if isinstance(select, str):
                select = [select]
            queries.append(f"$select={','.join(select)}")
        return "?" + "&".join(queries) if len(queries) else ""

    def _construct_url(
        self,
        table: str,
        entry_id: Optional[str | dict] = None,
        filter: Optional[str] = None,
        order_by: Optional[str | list[str]] = None,
        top: Optional[int] = None,
        count: Optional[bool] = None,
        select: Optional[str | list[str]] = None,
        apply: Optional[str] = None,
    ) -> str:
        """
        Construct the URL for a Dataverse table entry.

        Args:
            table: Table name
            entry_id: Entry ID or alternate key. Defaults to None
            filter: OData filter query, e.g. "column eq 'value'". Defaults to None
            order_by: Column or list of columns to order by. Defaults to None
            top: Return the top n results. Defaults to None
            count: Include "@odata.count" in the response, counting matches. Defaults to None
            select: Columns to include in the response. Defaults to None
            apply: OData $apply query (aggregation/grouping). Defaults to None

        Returns:
            str: Constructed URL for the entry
        """
        if entry_id is None:
            identifier = ""
        elif isinstance(entry_id, str):
            identifier = f"({entry_id})"
        elif isinstance(entry_id, dict):  # Can query by alternate key
            key = list(entry_id.keys())[0]
            value = list(entry_id.values())[0]
            if isinstance(value, str):
                # strings in url query must be formatted with single quotes
                value = f"'{value}'"
            identifier = f"({key}={value})"
        else:
            raise ValueError("entry_id must be a string or dictionary")

        queries = self._format_queries(
            filter=filter,
            order_by=order_by,
            top=top,
            count=count,
            select=select,
            apply=apply,
        )

        url = self.config.api_url + table + identifier + queries

        return url

    def get_entry(self, table: str, id: str | dict) -> dict:
        """
        Get a Dataverse entry by ID or alternate key.

        Args:
            table: Table name
            id: Entry ID or alternate key

        Returns:
            dict: Entry data as a dictionary

        Raises:
            ValueError: If the entry cannot be fetched
        """
        url = self._construct_url(table, id)
        response = requests.get(url, headers=self.headers, timeout=_REQUEST_TIMEOUT)
        logger.debug(
            f'Dataverse GET: "{url}", status code: {response.status_code}, '
            f"duration: {response.elapsed.total_seconds()} seconds"
        )
        response.raise_for_status()
        return response.json()

    def add_entry(self, table: str, data: dict) -> Optional[dict]:
        """
        Add a new entry to a Dataverse table.

        Args:
            table: Table name
            data: Entry data to add

        Returns:
            Optional[dict]: Response data from Dataverse

        Raises:
            ValueError: If the entry cannot be added
        """
        url = self._construct_url(table)
        response = requests.post(url, headers=self.headers, json=data, timeout=_REQUEST_TIMEOUT)
        logger.debug(
            f'Dataverse POST: "{url}", status code: {response.status_code}, '
            f"duration: {response.elapsed.total_seconds()} seconds"
        )
        response.raise_for_status()
        if response.status_code == 204:
            return None
        else:
            return response.json()

    def update_entry(
        self,
        table: str,
        id: str | dict,
        update_data: dict,
    ) -> dict:
        """
        Update an existing entry in a Dataverse table.

        Args:
            table: Table name
            id: Entry ID or alternate key
            update_data: Data to update

        Returns:
            dict: Updated entry data from Dataverse

        Raises:
            ValueError: If the entry cannot be updated
        """
        url = self._construct_url(table, id)
        headers = self.headers | {"Prefer": "return=representation"}
        response = requests.patch(url, headers=headers, json=update_data, timeout=_REQUEST_TIMEOUT)
        logger.debug(
            f'Dataverse PATCH: "{url}", status code: {response.status_code}, '
            f"duration: {response.elapsed.total_seconds()} seconds"
        )
        response.raise_for_status()
        return response.json()

    def query(
        self,
        table: str,
        filter: Optional[str] = None,
        order_by: Optional[str] = None,
        top: Optional[int] = None,
        select: Optional[list[str]] = None,
        apply: Optional[str] = None,
    ) -> list[dict]:
        """
        Query a Dataverse table for multiple entries based on filters.

        For details, see https://www.odata.org/getting-started/basic-tutorial/#queryData
        and https://docs.oasis-open.org/odata/odata/v4.0/errata03/os/complete/part1-protocol/odata-v4.0-errata03-os-part1-protocol-complete.html#_The_$filter_System

        Args:
            table: Table name
            filter: OData filter query, e.g. "column eq 'value'". Defaults to None
            order_by: Column or list of columns to order by. Defaults to None
            top: Return the top n results. Defaults to None
            select: Columns to include in the response. Defaults to None
            apply: OData $apply query, e.g. "filter(...)/groupby((navProperty/attribute))" to get
                distinct values through a lookup, optionally pre-filtered. Defaults to None

        Returns:
            list[dict]: Query results from Dataverse
        """
        url = self._construct_url(
            table,
            filter=filter,
            order_by=order_by,
            top=top,
            select=select,
            apply=apply,
        )
        # Note: Could also provide `count`, but it's not useful for this method as this
        # returns a list of values, and wouldn't include the "@odata.count" property anyway
        response = requests.get(
            url, headers=self.headers | {"Prefer": "return=representation"}, timeout=_REQUEST_TIMEOUT
        )
        logger.debug(
            f'Dataverse GET: "{url}", status code: {response.status_code}, '
            f"duration: {response.elapsed.total_seconds()} seconds"
        )
        response.raise_for_status()
        return response.json().get("value", [])


# Helpers for specific API. Prefer using these over direct calls to the client whenever possible


_MICE_TABLE = "aibs_dim_mices"
_SUGGESTIONS_TABLE = "aibs_fact_mouse_proposed_behavior_sessionses"
_ACQUISITION_TYPE_FIELD = "aibs_task_name"
_SUGGESTION_CREATED_ON_FIELD = "createdon"
_MOUSE_LOOKUP_NAV_PROPERTY = "aibs_mouse_id"
_MOUSE_ID_ATTRIBUTE = "aibs_mouse_id"
_LATEST_CREATED_ALIAS = "latest_created"

DEFAULT_MAX_SUBJECTS = 100


def _get_subjects_by_acquisition_type(
    client: _DataverseRestClient,
    acquisition_type: Optional[str],
    created_after: Optional[datetime] = None,
    max_subjects: Optional[int] = DEFAULT_MAX_SUBJECTS,
) -> list[str]:
    """
    Get all distinct subject IDs from Dataverse that have a recorded suggestion matching
    `acquisition_type` (or any acquisition type, if None), optionally restricted to suggestions
    created on/after `created_after`, capped to the `max_subjects` most recently active animals.

    Distinctness is computed server-side via Dataverse's OData $apply/groupby aggregation
    extension, grouping through the mouse lookup's navigation property straight to the mouse's
    readable ID column. This returns one row per matching mouse instead of one per suggestion,
    and needs no separate lookup per mouse. Grouping directly on the raw lookup value (e.g.
    "_aibs_mouse_id_value") is not valid Dataverse syntax; it must traverse the navigation
    property, per https://learn.microsoft.com/en-us/power-apps/developer/data-platform/webapi/query/aggregate-data

    Each group's most recent suggestion date is computed server-side in the same call via
    aggregate(createdon with max as ...) - Dataverse doesn't support $orderby on an aggregated
    value, so the actual sort-by-recency and max_subjects cap happen in Python, but only over
    this already distinct, small (one row per matching animal) result set - not over raw
    suggestion rows.
    """
    filter_clauses = []
    if acquisition_type is not None:
        filter_clauses.append(f"{_ACQUISITION_TYPE_FIELD} eq '{acquisition_type}'")
    if created_after is not None:
        filter_clauses.append(f"{_SUGGESTION_CREATED_ON_FIELD} ge {created_after.strftime('%Y-%m-%dT%H:%M:%SZ')}")
    groupby_key = f"({_MOUSE_LOOKUP_NAV_PROPERTY}/{_MOUSE_ID_ATTRIBUTE})"
    aggregate = f"aggregate({_SUGGESTION_CREATED_ON_FIELD} with max as {_LATEST_CREATED_ALIAS})"
    groupby = f"groupby({groupby_key},{aggregate})"
    apply = f"filter({' and '.join(filter_clauses)})/{groupby}" if filter_clauses else groupby

    rows = client.query(_SUGGESTIONS_TABLE, apply=apply)

    latest_created_by_subject: dict[str, str] = {}
    for row in rows:
        latest_created = row.get(_LATEST_CREATED_ALIAS) or ""
        subject_id = next(
            (value for key, value in row.items() if key != _LATEST_CREATED_ALIAS and "@" not in key and value),
            None,
        )
        if subject_id and latest_created > latest_created_by_subject.get(subject_id, ""):
            latest_created_by_subject[subject_id] = latest_created

    subjects_by_recency = sorted(latest_created_by_subject.items(), key=lambda item: item[1], reverse=True)
    if max_subjects is not None:
        subjects_by_recency = subjects_by_recency[:max_subjects]

    return sorted(subject_id for subject_id, _ in subjects_by_recency)


def _get_last_suggestions(client: _DataverseRestClient, subject_name: str, task_name: str, history: int = 10):
    """
    Get the last N suggestions from a subject for a specific task.
    """
    subject = client.get_entry(_MICE_TABLE, {"aibs_mouse_id": subject_name})
    subject_guid = subject["aibs_dim_miceid"]

    filter_str = f"aibs_task_name eq '{task_name}' and _aibs_mouse_id_value eq '{subject_guid}'"

    sessions = client.query(_SUGGESTIONS_TABLE, filter=filter_str, order_by="createdon desc", top=history, select=["*"])
    return [DataverseSuggestion.from_request_output(subject_name, s) for s in sessions]


class DataverseSuggestion(BaseModel):
    """
    Internal representation of a suggestion entry in Dataverse.
    """

    trainer_state: Optional[TrainerState] = None
    subject_id: str
    task_name: Optional[str]
    stage_name: Optional[str]
    modified_on: Optional[datetime] = None
    created_on: Optional[datetime] = None

    @field_validator("trainer_state", mode="before")
    @classmethod
    def validate_trainer_state(cls, value):
        """
        Validate and convert the trainer_state field from a JSON string to a TrainerState object.
        """
        if value is None:
            return value
        if isinstance(value, str):
            return TrainerState.model_validate_json(value)
        return value

    @classmethod
    def from_request_output(cls, subject: str, request_output: dict) -> "DataverseSuggestion":
        """
        Create a _Suggestion instance from a dictionary of data.
        """
        trainer_state = request_output.get("aibs_trainer_state", None)
        trainer_state = TrainerState.model_validate_json(cls._strip_html(trainer_state)) if trainer_state else None
        return cls(
            subject_id=subject,
            trainer_state=trainer_state,
            task_name=request_output.get("aibs_task_name", None),
            stage_name=request_output.get("aibs_stage_name", None),
            modified_on=request_output.get("modifiedon", None),
            created_on=request_output.get("createdon", None),
        )

    @staticmethod
    def _strip_html(value: str) -> str:
        """
        Remove HTML tags and decode HTML entities from a string.
        """
        if not value:
            return ""
        no_tags = re.sub(r"<[^>]+>", "", value)
        # decode HTML entities (&nbsp;, &amp;, etc.)
        return unescape(no_tags).strip()

    @classmethod
    def from_trainer_state(cls, subject: str, trainer_state: TrainerState) -> "DataverseSuggestion":
        """
        Create a _Suggestion instance from a TrainerState object.
        """
        if trainer_state is None:
            raise ValueError("trainer_state cannot be None")
        if trainer_state.stage is None:
            raise ValueError("trainer_state.stage cannot be None")
        return cls(
            subject_id=subject,
            trainer_state=trainer_state,
            task_name=trainer_state.stage.task.name,
            stage_name=trainer_state.stage.name,
        )


def _append_suggestion(client: _DataverseRestClient, subject_id: str, trainer_state: TrainerState) -> None:
    """
    Append a new suggestion to the Dataverse table for a subject.
    """
    _suggestion = DataverseSuggestion.from_trainer_state(subject_id, trainer_state)
    subject = client.get_entry(_MICE_TABLE, {"aibs_mouse_id": _suggestion.subject_id})
    subject_guid = subject["aibs_dim_miceid"]

    client.add_entry(
        _SUGGESTIONS_TABLE,
        {
            "aibs_task_name": _suggestion.task_name,
            "aibs_mouse_id@odata.bind": f"/aibs_dim_mices({subject_guid})",
            "aibs_stage_name": _suggestion.stage_name,
            "aibs_trainer_state": _suggestion.trainer_state.model_dump_json() if _suggestion.trainer_state else None,
        },
    )


class DataversePicker(DefaultBehaviorPicker):
    """
    Picker that integrates with Dataverse to fetch and push trainer state suggestions.
    """

    def __init__(
        self,
        *,
        dataverse_client: Optional[_DataverseRestClient] = None,
        settings: DefaultBehaviorPickerSettings,
        launcher: Launcher,
        frontend: Optional[ui.Frontend] = None,
        experimenter_validator: Optional[Callable[[str], bool]] = validate_username,
        rig_validator: Optional[Callable[[Rig], Rig]] = validate_rig_computer_name,
        acquisition_type: Optional[str] = None,
        lookback_time: Optional[timedelta] = timedelta(days=60),
        max_subjects: Optional[int] = DEFAULT_MAX_SUBJECTS,
    ):
        """
        Initializes the DataversePicker.

        Args:
            acquisition_type: The acquisition type (e.g. "AindVrForaging") used to filter which
                subjects choose_subject offers. If None, subjects are not filtered by acquisition
                type, only by lookback_time
            lookback_time: Only offer subjects with a suggestion created within this window before now. Pass None to disable the time bound. Defaults to 60 days
            max_subjects: Only offer the this many most-recently-active subjects. Pass None to disable the cap. Defaults to 100
            dataverse_client: Optional Dataverse REST client for making API calls. If not provided, a new client will be created using settings from KeePass.
            settings: Settings containing configuration including config_library_dir
            frontend: Frontend mediating user interaction
            experimenter_validator: Function to validate the experimenter's username. If None, no validation is performed
            rig_validator: Function to validate the rig configuration. If None, no validation is performed
        """
        super().__init__(
            settings=settings,
            launcher=launcher,
            frontend=frontend,
            experimenter_validator=experimenter_validator,
            rig_validator=rig_validator,
        )
        self._acquisition_type = acquisition_type
        self._lookback_time = lookback_time
        self._max_subjects = max_subjects
        self._dataverse_client = (
            dataverse_client
            if dataverse_client is not None
            else _DataverseRestClient(_DataverseRestClientSettings.from_keepass())
        )
        self._dataverse_suggestion: Optional[DataverseSuggestion] = None

    def choose_subject(self, directory: str | os.PathLike) -> str:
        """
        Prompts the user to select or manually enter a subject name, offering autocomplete
        suggestions from Dataverse for all animals matching this picker's acquisition type
        (restricted to `lookback_time` and `max_subjects`, if set).

        If the Dataverse query fails, no autocomplete options are offered and the user must
        enter the subject name manually.

        Args:
            directory: Path to the directory containing subject folders. Unused, kept for
                interface compatibility with DefaultBehaviorPicker.choose_subject

        Returns:
            str: The selected or entered subject name.
        """
        created_after = datetime.now(timezone.utc) - self._lookback_time if self._lookback_time else None
        try:
            options = _get_subjects_by_acquisition_type(
                self._dataverse_client,
                self._acquisition_type,
                created_after=created_after,
                max_subjects=self._max_subjects,
            )
        except (requests.exceptions.RequestException, ValueError) as e:
            logger.error(
                "Failed to fetch subjects from Dataverse for acquisition type %s: %s", self._acquisition_type, e
            )
            self.frontend.notify(
                "Failed to fetch subjects from Dataverse. Enter the subject manually.", ui.MessageLevel.WARNING
            )
            options = []

        subject: Optional[str] = None
        while not subject:
            subject = self.frontend.prompt_autocomplete(
                ui.AutoCompleteRequest(
                    label="Subject (type to filter, or enter a new one)",
                    options=options,
                    field="subject",
                )
            )
        return subject

    def pick_trainer_state(self, task_model: Type[TTask]) -> tuple[TrainerState, TTask]:
        """
        Prompts the user to select or create a trainer state configuration.

        Attempts to load trainer state in the following order:
        1. If task already exists in launcher, will return an empty TrainerState
        2. From subject-specific folder

        It will launcher.set_task if the deserialized TrainerState is valid.

        Returns:
            TrainerState: The deserialized TrainerState object.

        Raises:
            ValueError: If no valid task file is found.
        """
        if self._session is None:
            raise ValueError("No session set. Run pick_session first.")
        task_name = task_model.model_fields["name"].default
        if not task_name:
            raise ValueError("Task model does not have a default name.")
        try:
            logger.debug("Attempting to load trainer state dataverse")
            last_suggestions = _get_last_suggestions(self._dataverse_client, self._session.subject, task_name, 1)
        except requests.exceptions.HTTPError as e:
            logger.error("Failed to fetch suggestions from Dataverse: %s", e)
            raise
        except pydantic.ValidationError as e:
            logger.error("Failed to validate suggestion from Dataverse: %s", e)
            raise
        if len(last_suggestions) == 0:
            raise ValueError(
                f"No valid suggestions found in Dataverse for subject {self._session.subject} with task {task_name}."
            )

        _dataverse_suggestion = last_suggestions[0]

        assert _dataverse_suggestion is not None
        if _dataverse_suggestion.trainer_state is None:
            raise ValueError("No trainer state found in the latest suggestion.")
        if _dataverse_suggestion.trainer_state.stage is None:
            raise ValueError("No stage found in the latest suggestion's trainer state.")
        self._dataverse_suggestion = _dataverse_suggestion
        self._trainer_state = _dataverse_suggestion.trainer_state

        assert self._trainer_state is not None
        if not self._trainer_state.is_on_curriculum:
            logging.warning("Deserialized TrainerState is NOT on curriculum.")
        return (
            self.trainer_state,
            task_model.model_validate_json(self.trainer_state.stage.task.model_dump_json()),
        )

    def push_new_suggestion(self, trainer_state: TrainerState) -> None:
        """
        Pushes a new suggestion to Dataverse for the current subject in the launcher.
        Args:
            launcher: The Launcher instance containing the current session and subject information.
            trainer_state: The TrainerState object to be pushed as a new suggestion.
        """
        if self._session is None:
            raise ValueError("No session or subject set in launcher.")

        logger.info("Pushing new suggestion to Dataverse for subject %s", self._session.subject)
        _append_suggestion(self._dataverse_client, self._session.subject, trainer_state)

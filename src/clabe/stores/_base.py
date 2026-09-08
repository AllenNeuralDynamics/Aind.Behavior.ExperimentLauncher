import abc
import functools
import logging
import re
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Generic, NamedTuple, Protocol, TypeVar, runtime_checkable

import pydantic
from aind_behavior_curriculum import TrainerState
from aind_behavior_services import Session

from .. import ui
from .._typing import TRig, TSession, TTask
from ..cache_manager import CacheManager
from ..utils.aind_validators import validate_rig_computer_name

logger = logging.getLogger(__name__)

T = TypeVar("T")

#: A set of key/value narrowings selecting which records a call addresses,
#: e.g. ``{"subject": "789012", "computer_name": "RIG-01"}``.
Scope = Mapping[str, str]

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def _snake_case(name: str) -> str:
    """Converts a CamelCase class name to snake_case."""
    return _CAMEL_BOUNDARY.sub("_", name).lower()


def _recent_first(cache_name: str, options: Sequence[str]) -> list[str]:
    """Floats the most recently chosen options to the top of a pick list, newest first."""
    recent = CacheManager.get_instance().try_get_cache(cache_name) or []
    ranked = [o for o in recent if o in options]
    return ranked + [o for o in options if o not in ranked]


def _validate_trainer_state(trainer_state: TrainerState) -> TrainerState:
    """Rejects a stageless trainer state, and warns when it has fallen off the curriculum."""
    if trainer_state.stage is None:
        raise ValueError("Trainer state has no stage.")
    if not trainer_state.is_on_curriculum:
        ui.notify("Deserialized TrainerState is NOT on curriculum.", ui.MessageLevel.WARNING)
    return trainer_state


class Kind(Generic[T]):
    """
    A record name bound to the pydantic model that parses it.

    The name routes the record to a backend and determines its storage layout;
    the model types the return value of every store call made with this kind.

    Canonical kinds must be built through :meth:`from_rig`, :meth:`from_task`,
    :meth:`from_session` or :meth:`from_trainer_state`, which fix the framework
    name. The bare constructor derives the name from the model class instead,
    so ``Kind(AindVrForagingRig)`` is named ``"aind_vr_foraging_rig"``, *not*
    ``"rig"`` -- it is for custom records only.
    """

    def __init__(self, model: type[T], name: str | None = None, *, validate: Callable[[T], T] | None = None) -> None:
        """
        Args:
            model: The pydantic model records of this kind deserialize to.
            name: The record name. Defaults to the snake-cased model class name.
            validate: Applied to every record read through a store, e.g. to
                reconcile a rig against the machine it was loaded on.
        """
        self.model = model
        self.name = name if name is not None else _snake_case(model.__name__)
        self.validate = validate

    @staticmethod
    def from_rig(
        model: type[TRig], *, validate: Callable[[TRig], TRig] | None = validate_rig_computer_name
    ) -> "Kind[TRig]":
        """Builds the canonical ``"rig"`` kind for a rig model."""
        return Kind(model, "rig", validate=validate)

    @staticmethod
    def from_task(model: type[TTask]) -> "Kind[TTask]":
        """Builds the canonical ``"task"`` kind for a task model."""
        return Kind(model, "task")

    @staticmethod
    def from_session(model: type[TSession] = Session) -> "Kind[TSession]":
        """Builds the canonical ``"session"`` kind for a session model."""
        return Kind(model, "session")

    @staticmethod
    def from_trainer_state() -> "Kind[TrainerState]":
        """Builds the canonical ``"trainer_state"`` kind."""
        return Kind(TrainerState, "trainer_state", validate=_validate_trainer_state)

    @functools.cached_property
    def adapter(self) -> pydantic.TypeAdapter[T]:
        """Serializes and parses records of this kind. Also covers models that are not ``BaseModel``."""
        return pydantic.TypeAdapter(self.model)

    def __repr__(self) -> str:
        return f"Kind({self.name!r}, {self.model.__name__})"


#: Either a declared kind or a bare model, which is wrapped in ``Kind(model)``.
KindLike = Kind[T] | type[T]


def as_kind(kind: KindLike[T]) -> Kind[T]:
    """Normalizes a kind-or-model argument into a :class:`Kind`."""
    return kind if isinstance(kind, Kind) else Kind(kind)


@runtime_checkable
class Store(Protocol):
    """
    Reads, resolves and writes records of a given :class:`Kind`.

    Which kinds a store actually serves is a deployment fact, not a type-level
    one: an unsupported kind raises when the call is made.
    """

    def resolve(self, kind: KindLike[T], *, scope: Scope | None = None) -> T:
        """Selects a single record, prompting the user when the choice is ambiguous."""
        ...

    def list(self, kind: KindLike[T], *, scope: Scope | None = None) -> Sequence[T]:
        """Returns every record of this kind in scope, without prompting."""
        ...

    def write(self, kind: KindLike[T], value: T, *, scope: Scope | None = None) -> None:
        """Persists a record. Whether that overwrites, versions or appends is the store's contract."""
        ...

    def scoped(self, **scope: str) -> "Store":
        """Returns a view of this store narrowed by the given scope."""
        ...


class Candidate(NamedTuple, Generic[T]):
    """A record together with the label a store shows when asking the user to pick it."""

    label: str
    value: T


class StoreBase(abc.ABC):
    """
    Base for stores, supplying scope narrowing and the default resolution policy.

    Subclasses implement :meth:`_candidates` and :meth:`write`, and may override
    :meth:`resolve` when their backend affords a better presentation than a flat
    pick list.
    """

    def __init__(self, *, scope: Scope | None = None) -> None:
        self._scope: dict[str, str] = dict(scope or {})

    @property
    def scope(self) -> Scope:
        """The scope every call on this store is narrowed by."""
        return dict(self._scope)

    def scoped(self, **scope: str) -> "StoreBase":
        """Returns a view sharing this store's data, narrowed by the given scope."""
        clone = object.__new__(type(self))
        clone.__dict__.update(self.__dict__)
        clone._scope = {**self._scope, **scope}
        return clone

    def _merge_scope(self, scope: Scope | None) -> dict[str, str]:
        """Layers a call's scope over the store's own."""
        return {**self._scope, **(scope or {})}

    @abc.abstractmethod
    def _candidates(self, kind: Kind[T], scope: Scope) -> Sequence[Candidate[T]]:
        """Returns every record of this kind in scope, each labelled for display."""

    @abc.abstractmethod
    def write(self, kind: KindLike[T], value: T, *, scope: Scope | None = None) -> None:
        """Persists a record. See :meth:`Store.write`."""

    def list(self, kind: KindLike[T], *, scope: Scope | None = None) -> Sequence[T]:
        """Returns every record of this kind in scope, validated but unprompted."""
        _kind = as_kind(kind)
        return [self._validated(_kind, c.value) for c in self._candidates(_kind, self._merge_scope(scope))]

    def resolve(self, kind: KindLike[T], *, scope: Scope | None = None) -> T:
        """
        Selects a single record: raises on none, auto-selects a lone candidate, prompts otherwise.

        Raises:
            LookupError: If no record of this kind exists in scope, or the user declined to pick one.
            ui.NoFrontendError: If a choice must be made and no frontend is registered.
        """
        _kind = as_kind(kind)
        candidates = self._candidates(_kind, self._merge_scope(scope))
        if not candidates:
            raise LookupError(f"No {_kind.name!r} records found in {self}.")
        if len(candidates) == 1:
            ui.notify(f"Found a single {_kind.name}. Using {candidates[0].label}.")
            return self._validated(_kind, candidates[0].value)
        by_label = {c.label: c.value for c in candidates}
        picked = ui.prompt_pick(
            ui.PickRequest(
                label=f"Choose a {_kind.name} for {_kind.model.__name__}:",
                options=_recent_first(_kind.name, sorted(by_label)),
                allow_none=False,
                field=_kind.name,
            )
        )
        if picked is None:
            raise LookupError(f"No {_kind.name} was selected.")
        CacheManager.get_instance().add_to_cache(_kind.name, picked)
        return self._validated(_kind, by_label[picked])

    @staticmethod
    def _validated(kind: Kind[T], value: T) -> T:
        """Applies the kind's validator, if it has one."""
        return kind.validate(value) if kind.validate is not None else value


class CompositeStore(StoreBase):
    """
    Routes each kind to a backend by record name, falling back to a default store.

    This is what composition buys over subclassing: a deployment keeping rigs and
    tasks on a network share but trainer state in Dataverse is a routing table,
    not a class.

    Example:
        ```python
        from clabe.stores.dataverse import DataverseStore

        store = CompositeStore(
            default=LocalFileStore(root=VR_LIB),
            routes={"trainer_state": DataverseStore()},
        )
        ```
    """

    def __init__(self, *, default: Store | None = None, routes: Mapping[str, Store] | None = None) -> None:
        """
        Args:
            default: Serves any kind not named in ``routes``. If ``None``,
                unrouted kinds raise.
            routes: Maps a :attr:`Kind.name` to the store serving it.
        """
        super().__init__()
        self._default = default
        self._routes = dict(routes or {})

    def _route(self, kind: Kind[Any]) -> Store:
        """
        Returns the backend serving this kind.

        Raises:
            LookupError: If the kind is unrouted and there is no default.
        """
        store = self._routes.get(kind.name, self._default)
        if store is None:
            raise LookupError(f"No store is registered for kind {kind.name!r}.")
        return store

    def _candidates(self, kind: Kind[T], scope: Scope) -> Sequence[Candidate[T]]:
        """Never called: every read is delegated to a routed backend."""
        raise NotImplementedError("CompositeStore delegates to its routed backends.")

    def resolve(self, kind: KindLike[T], *, scope: Scope | None = None) -> T:
        """Delegates to the routed backend, so its own presentation is used."""
        _kind = as_kind(kind)
        return self._route(_kind).resolve(_kind, scope=scope)

    def list(self, kind: KindLike[T], *, scope: Scope | None = None) -> Sequence[T]:
        """Delegates to the routed backend."""
        _kind = as_kind(kind)
        return self._route(_kind).list(_kind, scope=scope)

    def write(self, kind: KindLike[T], value: T, *, scope: Scope | None = None) -> None:
        """Delegates to the routed backend."""
        _kind = as_kind(kind)
        self._route(_kind).write(_kind, value, scope=scope)

    def scoped(self, **scope: str) -> "CompositeStore":
        """Returns a composite whose every backend is narrowed by the given scope."""
        return CompositeStore(
            default=self._default.scoped(**scope) if self._default is not None else None,
            routes={name: store.scoped(**scope) for name, store in self._routes.items()},
        )

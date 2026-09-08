from collections.abc import Sequence
from typing import Any, TypeVar

from ._base import Candidate, Kind, KindLike, Scope, StoreBase, as_kind

T = TypeVar("T")


class MemoryStore(StoreBase):
    """
    A store holding records in memory, for tests and for assembling records in-process.

    Writes replace any record previously written with the same kind and scope,
    matching :class:`~clabe.stores.LocalFileStore`. A record is visible to a
    read whose scope agrees with every narrowing the record was written under,
    so a record written unscoped is library-wide.
    """

    def __init__(self, *, scope: Scope | None = None) -> None:
        super().__init__(scope=scope)
        self._records: list[tuple[str, dict[str, str], Any]] = []

    def __str__(self) -> str:
        return f"{type(self).__name__}({len(self._records)} records)"

    def _candidates(self, kind: Kind[T], scope: Scope) -> Sequence[Candidate[T]]:
        return [
            Candidate(f"{kind.name}[{i}]", value)
            for i, (name, written, value) in enumerate(self._records)
            if name == kind.name and all(scope.get(k) == v for k, v in written.items())
        ]

    def write(self, kind: KindLike[T], value: T, *, scope: Scope | None = None) -> None:
        name = as_kind(kind).name
        merged = self._merge_scope(scope)
        self._records = [r for r in self._records if (r[0], r[1]) != (name, merged)]
        self._records.append((name, merged, value))

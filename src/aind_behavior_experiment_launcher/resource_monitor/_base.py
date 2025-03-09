from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from aind_behavior_experiment_launcher.services import IService

logger = logging.getLogger(__name__)


class ResourceMonitor(IService):
    def __init__(
        self,
        *args,
        constrains: Optional[List[Constraint]] = None,
        **kwargs,
    ) -> None:
        self.constraints = constrains or []

    def validate(self, *args, **kwargs) -> bool:
        return self.evaluate_constraints()

    def add_constraint(self, constraint: Constraint) -> None:
        self.constraints.append(constraint)

    def remove_constraint(self, constraint: Constraint) -> None:
        self.constraints.remove(constraint)

    def evaluate_constraints(self) -> bool:
        for constraint in self.constraints:
            if not constraint():
                logger.error(constraint.on_fail())
                return False
        return True


@dataclass(frozen=True)
class Constraint:
    name: str
    constraint: Callable[..., bool]
    args: List = field(default_factory=list)
    kwargs: dict = field(default_factory=dict)
    fail_msg_handler: Optional[Callable[..., str]] = field(default=None)

    def __call__(self) -> bool | Exception:
        return self.constraint(*self.args, **self.kwargs)

    def on_fail(self) -> str:
        if self.fail_msg_handler:
            return self.fail_msg_handler(*self.args, **self.kwargs)
        else:
            return f"Constraint {self.name} failed."

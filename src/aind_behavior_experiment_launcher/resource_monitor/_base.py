from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from aind_behavior_experiment_launcher.services import IService

logger = logging.getLogger(__name__)


class ResourceMonitor(IService):
    """
    A service that monitors and validates resource constraints.

    Attributes:
        constraints (List[Constraint]): A list of constraints to monitor.
    """

    def __init__(
        self,
        *args,
        constrains: Optional[List[Constraint]] = None,
        **kwargs,
    ) -> None:
        """
        Initializes the ResourceMonitor.

        Args:
            constrains (Optional[List[Constraint]]): A list of constraints to initialize with. Defaults to None.
        """
        self.constraints = constrains or []

    def validate(self, *args, **kwargs) -> bool:
        """
        Validates all constraints.

        Returns:
            bool: True if all constraints are satisfied, False otherwise.
        """
        return self.evaluate_constraints()

    def add_constraint(self, constraint: Constraint) -> None:
        """
        Adds a new constraint to the monitor.

        Args:
            constraint (Constraint): The constraint to add.
        """
        self.constraints.append(constraint)

    def remove_constraint(self, constraint: Constraint) -> None:
        """
        Removes a constraint from the monitor.

        Args:
            constraint (Constraint): The constraint to remove.
        """
        self.constraints.remove(constraint)

    def evaluate_constraints(self) -> bool:
        """
        Evaluates all constraints.

        Returns:
            bool: True if all constraints are satisfied, False otherwise.
        """
        for constraint in self.constraints:
            if not constraint():
                logger.error(constraint.on_fail())
                return False
        return True


@dataclass(frozen=True)
class Constraint:
    """
    Represents a resource constraint.

    Attributes:
        name (str): The name of the constraint.
        constraint (Callable[..., bool]): The function to evaluate the constraint.
        args (List): Positional arguments for the constraint function.
        kwargs (dict): Keyword arguments for the constraint function.
        fail_msg_handler (Optional[Callable[..., str]]): A function to generate a failure message.
    """

    name: str
    constraint: Callable[..., bool]
    args: List = field(default_factory=list)
    kwargs: dict = field(default_factory=dict)
    fail_msg_handler: Optional[Callable[..., str]] = field(default=None)

    def __call__(self) -> bool | Exception:
        """
        Evaluates the constraint.

        Returns:
            bool | Exception: True if the constraint is satisfied, otherwise raises an exception.
        """
        return self.constraint(*self.args, **self.kwargs)

    def on_fail(self) -> str:
        """
        Generates a failure message if the constraint is not satisfied.

        Returns:
            str: The failure message.
        """
        if self.fail_msg_handler:
            return self.fail_msg_handler(*self.args, **self.kwargs)
        else:
            return f"Constraint {self.name} failed."

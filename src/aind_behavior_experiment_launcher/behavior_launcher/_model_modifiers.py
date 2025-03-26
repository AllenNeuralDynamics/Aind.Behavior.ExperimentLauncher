from typing import Any, Generic, Optional, Protocol, TypeVar

from aind_behavior_services.rig import AindBehaviorRigModel
from aind_behavior_services.session import AindBehaviorSessionModel
from aind_behavior_services.task_logic import AindBehaviorTaskLogicModel

_R = TypeVar("_R", bound=AindBehaviorRigModel, contravariant=True)
_S = TypeVar("_S", bound=AindBehaviorSessionModel, contravariant=True)
_T = TypeVar("_T", bound=AindBehaviorTaskLogicModel, contravariant=True)


class ByAnimalModifier(Protocol, Generic[_R, _S, _T]):
    def __call__(
        self, rig_schema: Optional[_R], session_schema: Optional[_S], task_logic_schema: Optional[_T], **kwargs: Any
    ) -> None: ...

import logging
from typing import Any, Optional, Self

from aind_slims_api.core import SlimsClient
from aind_slims_api.models import mouse, waterlog_result
from pydantic import ValidationError

from aind_behavior_experiment_launcher.ui_helper import prompt_field_from_input

logger = logging.getLogger(__name__)


class WaterLogResult(waterlog_result.SlimsWaterlogResult):
    def prompt_field(self, field_name: str, default: Optional[Any] = None, validate=False) -> Self:
        value = prompt_field_from_input(self, field_name, default)
        setattr(self, field_name, value)
        is_validated = self.model_rebuild()
        if is_validated is None:
            return self
        else:
            if not validate | is_validated:
                return self
            else:
                raise ValidationError(f"Invalid value for {field_name}: {value}")

    def calculated_suggested_water(self, target_weight: float, minimum_daily_water: float = 1.0):
        if self.weight_g is None:
            raise ValueError("Weight is not set")
        weight_difference = max(0, target_weight - self.weight_g)
        return max(weight_difference, minimum_daily_water - self.water_earned_ml, 0)


class Mouse(mouse.SlimsMouseContent):
    def prompt_field(self, field_name: str, default: Optional[Any] = None, validate=False) -> Self:
        value = prompt_field_from_input(self, field_name, default)
        setattr(self, field_name, value)
        is_validated = self.model_rebuild()
        if is_validated is None:
            return self
        else:
            if not validate | is_validated:
                return self
            else:
                raise ValidationError(f"Invalid value for {field_name}: {value}")

    @classmethod
    def fetch(self, client: SlimsClient, barcode: str) -> Self:
        return client.fetch_model(Mouse, barcode=barcode)

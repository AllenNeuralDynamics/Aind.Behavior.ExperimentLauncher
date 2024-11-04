import datetime
import unittest

from aind_behavior_experiment_launcher.records.subject import WaterLogResult


class TestWaterLogResult(unittest.TestCase):
    def setUp(self):
        self.water_log_result = WaterLogResult(
            weight_g=20.0,
            water_earned_ml=1.0,
            water_supplement_delivered_ml=1,
            water_supplement_recommended_ml=1,
            total_water_ml=10.0,
            operator="test_operator",
            date=datetime.datetime(2021, 1, 1),
            sw_source="test_sw_source",
        )

    def test_calculated_suggested_water(self):
        result = self.water_log_result.calculated_suggested_water(target_weight=25.0)
        self.assertEqual(result, 5.0)

    def test_calculated_suggested_water_minimum(self):
        result = self.water_log_result.calculated_suggested_water(target_weight=18.0, minimum_daily_water=2.0)
        self.assertEqual(result, 1.0)

    def test_calculated_suggested_water_no_weight(self):
        self.water_log_result.weight_g = None
        with self.assertRaises(ValueError):
            self.water_log_result.calculated_suggested_water(target_weight=25.0)


if __name__ == "__main__":
    unittest.main()

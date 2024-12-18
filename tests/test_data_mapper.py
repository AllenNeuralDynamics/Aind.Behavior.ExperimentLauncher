import unittest

# from . import TESTS_ASSETS, REPO_ROOT
from pathlib import Path
from typing import Dict, List, Optional
from unittest.mock import patch

from pydantic import BaseModel

from aind_behavior_experiment_launcher.data_mapper.helpers import (
    _sanity_snapshot_keys,
    get_fields_of_type,
    snapshot_bonsai_environment,
    snapshot_python_environment,
)

from . import TESTS_ASSETS


class MockModel(BaseModel):
    field1: int
    field2: str
    field3: List[int]
    field4: Dict[str, int]
    field5: Optional[int] = None
    sub_model: Optional["MockModel"] = None


class TestGetFieldsOfType(unittest.TestCase):
    def test_get_fields_of_type_dict(self):
        data = {"field1": 1, "field2": "test", "field3": [1, 2, 3], "field4": {"key1": 1, "key2": 2}, "field5": None}
        result = get_fields_of_type(data, int, recursive=False)
        expected = [("field1", 1)]
        self.assertEqual(result, expected)

        result = get_fields_of_type(data, int, recursive=True)
        expected = [("field1", 1), (None, 1), (None, 2), (None, 3), ("key1", 1), ("key2", 2)]
        self.assertEqual(result, expected)

    def test_get_fields_of_type_list(self):
        data = [1, "test", [1, 2, 3], {"key1": 1, "key2": 2}, None]
        result = get_fields_of_type(data, int, recursive=False)
        expected = [(None, 1)]
        self.assertEqual(result, expected)

        result = get_fields_of_type(data, int, recursive=True)
        expected = [(None, 1), (None, 1), (None, 2), (None, 3), ("key1", 1), ("key2", 2)]
        self.assertEqual(result, expected)

    def test_get_fields_of_type_pydantic_model(self):
        model = MockModel(field1=1, field2="test", field3=[1, 2, 3], field4={"key1": 1, "key2": 2})
        result = get_fields_of_type(model, int, recursive=False)
        expected = [("field1", 1)]
        self.assertEqual(result, expected)

        result = get_fields_of_type(model, int, recursive=True)
        expected = [("field1", 1), (None, 1), (None, 2), (None, 3), ("key1", 1), ("key2", 2)]
        self.assertEqual(result, expected)

    def test_get_fields_of_type_stop_recursion(self):
        sub_model = MockModel(field1=1, field2="test", field3=[1, 3, 36], field4={"key1": 2, "key2": 3})
        model = MockModel(field1=1, field2="test", field3=[1, 2, 3], field4={"key1": 1, "key2": 2}, sub_model=sub_model)
        data = {
            "field1": 1,
            "field2": "test",
            "field3": [1, 2, {"nested_field": 3}],
            "field4": {"key1": 1, "key2": 2},
            "field5": None,
            "field6": model,
        }
        result = get_fields_of_type(data, MockModel, recursive=True, stop_recursion_on_type=True)
        expected = [("field6", model)]
        self.assertEqual(result, expected)

        result = get_fields_of_type(data, MockModel, recursive=True, stop_recursion_on_type=False)
        expected = [("field6", model), ("sub_model", sub_model)]
        self.assertEqual(result, expected)


class TestHelpers(unittest.TestCase):
    @patch("importlib.metadata.distributions")
    def test_snapshot_python_environment(self, mock_distributions):
        mock_distributions.return_value = [
            type("Distribution", (object,), {"name": "package1.sub$s", "version": "1.0.0"}),
            type("Distribution", (object,), {"name": "package2", "version": "2.0.0"}),
        ]
        expected_result = {"package1_sub_s": "1.0.0", "package2": "2.0.0"}
        result = snapshot_python_environment()
        self.assertEqual(result, expected_result)

    def test_snapshot_bonsai_environment_from_mock(self):
        out = snapshot_bonsai_environment(config_file=Path(TESTS_ASSETS) / "bonsai.config")
        self.assertEqual(
            out,
            {"Bonsai": "2.8.5", "Bonsai_Core": "2.8.5", "Bonsai_Design": "2.8.5", "Bonsai_Design_Visualizers": "2.8.0"},
        )

    def test_sanity_snapshot_keys_no_special_chars(self):
        snapshot = {"key1": "value1", "key2": "value2"}
        expected = {"key1": "value1", "key2": "value2"}
        result = _sanity_snapshot_keys(snapshot)
        self.assertEqual(result, expected)

    def test_sanity_snapshot_keys_with_dots(self):
        snapshot = {"key.1": "value1", "key.2": "value2"}
        expected = {"key_1": "value1", "key_2": "value2"}
        result = _sanity_snapshot_keys(snapshot)
        self.assertEqual(result, expected)

    def test_sanity_snapshot_keys_with_dollars(self):
        snapshot = {"key$1": "value1", "key$2": "value2"}
        expected = {"key_1": "value1", "key_2": "value2"}
        result = _sanity_snapshot_keys(snapshot)
        self.assertEqual(result, expected)

    def test_sanity_snapshot_keys_with_dots_and_dollars(self):
        snapshot = {"key.1$": "value1", "key.2$": "value2"}
        expected = {"key_1_": "value1", "key_2_": "value2"}
        result = _sanity_snapshot_keys(snapshot)
        self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()

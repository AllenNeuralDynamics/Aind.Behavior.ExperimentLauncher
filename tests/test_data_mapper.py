import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import patch

from aind_data_schema.base import AindGeneric
from pydantic import BaseModel

from aind_behavior_experiment_launcher.data_mapper.aind_data_schema import create_encoding_model
from aind_behavior_experiment_launcher.data_mapper.helpers import (
    _sanity_snapshot_keys,
    snapshot_bonsai_environment,
    snapshot_python_environment,
)
from tests import TESTS_ASSETS


class MockModel(BaseModel):
    field1: int
    field2: str
    field3: List[int]
    field4: Dict[str, int]
    field5: Optional[int] = None
    sub_model: Optional["MockModel"] = None


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


class TestAindDataMapper(unittest.TestCase):
    class MyMockModel(BaseModel):
        a_dict: Dict[str, Any]
        a_generic: AindGeneric

    def test_encoding_with_illegal_characters(self):
        _input = {"key": "value", "$key.key": "value"}
        _expected = {"key": "value", "\\u0024key\\u002ekey": "value"}
        encoding_model = create_encoding_model(self.MyMockModel)
        test = encoding_model(a_dict=_input, a_generic=_input)
        self.assertEqual(test.a_dict, _expected)
        self.assertEqual(test.a_generic.model_dump(), _expected)


if __name__ == "__main__":
    unittest.main()

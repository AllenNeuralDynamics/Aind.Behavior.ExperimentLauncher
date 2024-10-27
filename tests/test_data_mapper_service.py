import unittest
from typing import Dict, List, Optional

from pydantic import BaseModel

from aind_behavior_experiment_launcher.data_mappers.data_mapper_service import get_fields_of_type


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


if __name__ == "__main__":
    unittest.main()

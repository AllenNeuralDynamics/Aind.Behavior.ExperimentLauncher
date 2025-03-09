import unittest
from unittest.mock import MagicMock, patch
from aind_behavior_experiment_launcher.ui_helper import DefaultUIHelper

class TestDefaultUiHelper(unittest.TestCase):
    def setUp(self):
        self.ui_helper = DefaultUIHelper(print_func=MagicMock())

    @patch("builtins.input", side_effect=["Some notes"])
    def test_prompt_get_text(self, mock_input):
        result = self.ui_helper.prompt_text("")
        self.assertIsInstance(result, str)

    @patch("builtins.input", side_effect=["Y"])
    def test_prompt_yes_no_question(self, mock_input):
        result = self.ui_helper.prompt_yes_no_question("Continue?")
        self.assertIsInstance(result, bool)
        
    @patch("builtins.input", side_effect=["1"])
    def test_prompt_pick_from_list(self, mock_input):
        result = self.ui_helper.prompt_pick_from_list(["item1", "item2"], "Choose an item")
        self.assertIsInstance(result, str)
        self.assertEqual(result, "item1")
    
    @patch("builtins.input", side_effect=["0"])
    def test_prompt_pick_from_list_none(self, mock_input):
        result = self.ui_helper.prompt_pick_from_list(["item1", "item2"], "Choose an item")
        self.assertIsNone(result)

if __name__ == "__main__":
    unittest.main()

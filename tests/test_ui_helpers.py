import unittest
from unittest.mock import MagicMock, patch

from aind_behavior_services.db_utils import SubjectDataBase

from aind_behavior_experiment_launcher.ui_helper import UIHelper


class TestUIHelper(unittest.TestCase):
    def setUp(self):
        self.ui_helper = UIHelper(print_func=MagicMock())

    @patch("builtins.input", side_effect=["1"])
    def test_prompt_pick_file_from_list(self, mock_input):
        files = ["file1.txt", "file2.txt"]
        result = self.ui_helper.prompt_pick_file_from_list(files)
        self.assertEqual(result, "file1.txt")

    @patch("builtins.input", side_effect=["0", "manual_entry"])
    def test_prompt_pick_file_from_list_manual_entry(self, mock_input):
        files = ["file1.txt", "file2.txt"]
        result = self.ui_helper.prompt_pick_file_from_list(files, zero_label="Manual Entry", zero_as_input=True)
        self.assertEqual(result, "manual_entry")

    @patch("builtins.input", side_effect=["Y"])
    def test_prompt_yes_no_question_yes(self, mock_input):
        result = self.ui_helper.prompt_yes_no_question("Continue?")
        self.assertTrue(result)

    @patch("builtins.input", side_effect=["N"])
    def test_prompt_yes_no_question_no(self, mock_input):
        result = self.ui_helper.prompt_yes_no_question("Continue?")
        self.assertFalse(result)

    @patch("builtins.input", side_effect=["1"])
    def test_choose_subject(self, mock_input):
        subject_list = SubjectDataBase(subjects={"subject1": None, "subject2": None})
        result = self.ui_helper.choose_subject(subject_list)
        self.assertEqual(result, "subject1")

    @patch("builtins.input", side_effect=["John Doe"])
    def test_prompt_experimenter(self, mock_input):
        result = self.ui_helper.prompt_experimenter()
        self.assertEqual(result, ["John", "Doe"])

    @patch("builtins.input", side_effect=["Some notes"])
    def test_prompt_get_notes(self, mock_input):
        result = self.ui_helper.prompt_get_notes()
        self.assertEqual(result, "Some notes")


if __name__ == "__main__":
    unittest.main()

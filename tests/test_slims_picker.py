import unittest
from unittest.mock import MagicMock, create_autospec, patch

from aind_slims_api.exceptions import SlimsRecordNotFound
from aind_slims_api.models import SlimsAttachment, SlimsInstrument, SlimsBehaviorSession, SlimsMouseContent
from pydantic import ValidationError
from aind_behavior_experiment_launcher.behavior_launcher._launcher import ByAnimalFiles
from aind_behavior_experiment_launcher.behavior_launcher import (
    BehaviorLauncher,
    BehaviorServicesFactoryManager,
    SlimsPicker,
)
from aind_behavior_services import (
    AindBehaviorRigModel,
)
from aind_behavior_experiment_launcher.launcher.cli import BaseCliArgs
from . import suppress_stdout

MOCK_MOUSE = SlimsMouseContent(point_of_contact="test", water_restricted=False, barcode="test", baseline_weight_g=0)
MOCK_TASK_LOGIC_ATTACHMENT = SlimsAttachment(pk=0, name=ByAnimalFiles.TASK_LOGIC.value)


def slims_ValidationError() -> ValidationError:
    """
    Convenience function to easily return a pydantic ValidationError
    """
    try:
        AindBehaviorRigModel()
    except Exception as e:
        return e


class TestSlimsPicker(unittest.TestCase):
    @patch.multiple(
        "aind_behavior_experiment_launcher.behavior_launcher.slims_picker.SlimsClient",
        __init__=MagicMock(return_value=None),
        fetch_model=MagicMock(return_value=None),
    )
    def setUp(self):
        self.services_factory_manager = create_autospec(BehaviorServicesFactoryManager)
        self.launcher = BehaviorLauncher(
            rig_schema_model=MagicMock(),
            task_logic_schema_model=MagicMock(),
            session_schema_model=MagicMock(),
            services=self.services_factory_manager,
            settings=BaseCliArgs(
                data_dir="/path/to/data",
                temp_dir="/path/to/temp",
                repository_dir=None,
                allow_dirty=False,
                skip_hardware_validation=False,
                debug_mode=False,
                group_by_subject_log=False,
                validate_init=False,
            ),
            attached_logger=None,
            picker=SlimsPicker(
                ui_helper=MagicMock(),
            ),
        )
        self.picker = self.launcher.picker

    @patch.multiple(
        "aind_behavior_experiment_launcher.behavior_launcher.slims_picker.SlimsClient",
        fetch_model=MagicMock(side_effect=[SlimsRecordNotFound(), SlimsInstrument(name="test")]),
        fetch_attachments=MagicMock(return_value=[SlimsAttachment(pk=0, name="namesake")] * 2),
        fetch_attachment_content=MagicMock(),
    )
    def test_pick_rig_input(self):
        # test no rig found on slims
        rig = self.picker.pick_rig()
        # fetch_model was called twice (once for failure, once for success)
        self.assertEqual(self.picker.slims_client.fetch_model.call_count, 2)
        self.assertIsNotNone(rig)
        self.assertIsNotNone(self.picker.slims_rig)  # check that rig has been saved as property

        # test invalid json
        self.picker.slims_client.fetch_model.side_effect = SlimsInstrument(name="test")
        self.launcher.rig_schema_model.side_effect = [slims_ValidationError(), MagicMock()]
        self.picker.pick_rig()
        # model validated twice more (once for failure, once for success)
        self.assertEqual(self.picker.launcher.rig_schema_model.call_count, 3)

        # test all invalid jsons
        self.picker.slims_client.fetch_model.side_effect = SlimsInstrument(name="test")
        self.launcher.rig_schema_model.side_effect = [slims_ValidationError(), slims_ValidationError()]
        with self.assertRaises(ValueError) as context:
            self.picker.pick_rig()
            self.assertTrue("No rig configuration found attached to rig model" in str(context.exception))

        # test no attachments
        self.picker.slims_client.fetch_attachments.return_value = []
        with self.assertRaises(ValueError) as context:
            self.picker.pick_rig()
            self.assertTrue("No valid rig configuration found attached to rig model" in str(context.exception))

    @patch.multiple(
        "aind_behavior_experiment_launcher.behavior_launcher.slims_picker.SlimsClient",
        fetch_model=MagicMock(side_effect=[SlimsRecordNotFound(), MOCK_MOUSE]),
        fetch_models=MagicMock(side_effect=[[SlimsBehaviorSession()], []]),
    )
    def test_pick_session(self):
        # test mouse not found
        self.picker.ui_helper.prompt_text.return_value = "Chris P. Bacon"
        session = self.picker.pick_session()
        # fetch_model was called twice (once for failure, once for success)
        self.assertEqual(self.picker.slims_client.fetch_model.call_count, 2)
        self.assertIsNotNone(session)
        self.assertIsNotNone(self.picker.slims_session)  # check that session has been saved as property
        self.assertIsNotNone(self.picker.slims_mouse)  # check that mouse has been saved as property

        # test no sessions on slims
        with self.assertRaises(ValueError) as context:
            self.picker.pick_session()
            self.assertTrue("No session found on slims for mouse" in str(context.exception))

    @patch.multiple(
        "aind_behavior_experiment_launcher.behavior_launcher.slims_picker.SlimsClient",
        fetch_attachments=MagicMock(
            side_effect=[[MOCK_TASK_LOGIC_ATTACHMENT], [], [SlimsAttachment(pk=0, name="test")]]
        ),
        fetch_attachment_content=MagicMock(),
    )
    def test_pick_task_logic(self):
        # test success
        self.picker._slims_session = SlimsBehaviorSession()
        task_logic = self.picker.pick_task_logic()
        self.assertIsNotNone(task_logic)

        # test no attachments
        with self.assertRaises(ValueError) as context:
            self.picker.pick_task_logic()
            self.assertTrue("No task_logic model found on with loaded slims session for " in str(context.exception))

        # test incorrectly named attachment
        with self.assertRaises(ValueError) as context:
            self.picker.pick_task_logic()
            self.assertTrue("No task_logic model found on with loaded slims session for " in str(context.exception))

        # test no session picked
        self.picker._slims_session = None
        task_logic = self.picker.pick_task_logic()
        self.assertIsNone(task_logic)


if __name__ == "__main__":
    unittest.main()

# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import copy as COPY

from odoo.tests.common import new_test_user
from odoo.addons.spreadsheet_edition.tests.spreadsheet_test_case import SpreadsheetTestCase


def add_thread_command(thread_id):
    return {
        "type": "ADD_COMMENT_THREAD",
        "sheetId": "sh1",
        "col": 0,
        "row": 1,
        "threadId": thread_id,
    }


class SpreadsheetMixinHistoryTest(SpreadsheetTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Shadow the current environment/cursor with the newly created user.
        cls.env = cls.env(user=new_test_user(cls.env, login="raoul", groups="base.group_user,test_spreadsheet.group_spreadsheet_test"))

    def test_copy_revisions(self):
        spreadsheet = self.env["spreadsheet.test"].create({})
        spreadsheet._dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        copy = spreadsheet.copy()
        self.assertEqual(
            copy.sudo().spreadsheet_revision_ids.commands,  # by default the current user is not allowed to see revisions
            spreadsheet.sudo().spreadsheet_revision_ids.commands,
        )

    def test_copy_parent_revisions(self):
        spreadsheet = self.env["spreadsheet.test"].create({})
        spreadsheet._dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        spreadsheet._dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        spreadsheet._dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        copy = spreadsheet.copy()
        revisions = copy.sudo().spreadsheet_revision_ids
        self.assertEqual(len(revisions), 3)
        self.assertEqual(
            revisions[2].parent_revision_id,
            revisions[1],
        )
        self.assertEqual(
            revisions[1].parent_revision_id,
            revisions[0],
        )
        self.assertFalse(revisions[0].parent_revision_id)

    def test_dont_copy_revisions_if_provided(self):
        spreadsheet = self.env["spreadsheet.test"].create({})
        spreadsheet._dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        copy = spreadsheet.copy({"spreadsheet_revision_ids": []})
        self.assertFalse(copy.sudo().spreadsheet_revision_ids)

    def test_dont_copy_revisions_if_data_changes(self):
        spreadsheet = self.env["spreadsheet.test"].create({})
        spreadsheet._dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        copy = spreadsheet.copy({"spreadsheet_data": "{}"})
        self.assertFalse(copy.sudo().spreadsheet_revision_ids)

    def test_copy_filters_out_comments(self):
        base_data = {
            "sheets": [{
                "comments": [
                    {"A1": {"threadId": 1, "isResolved": False}}
                ]
            }],
            "revisionId": "revision-id"
        }
        spreadsheet = self.env["spreadsheet.test"].create({"spreadsheet_data": json.dumps(base_data)})

        spreadsheet._dispatch_command(add_thread_command(2))
        snapshot_data = COPY.deepcopy(base_data)
        snapshot_data["revisionId"] = "snapshot-revision-id"
        snapshot_data["sheets"][0]["comments"][0]["A2"] = {"threadId": 1, "isResolved": False}

        self.snapshot(spreadsheet, spreadsheet.current_revision_uuid, "snapshot-revision-id", snapshot_data)
        spreadsheet._dispatch_command(add_thread_command(3))

        copy = spreadsheet.copy().with_context(active_test=False)  # get all the archived revisions

        copied_data = json.loads(copy.spreadsheet_data)
        copied_snapshot = json.loads(copy._get_spreadsheet_serialized_snapshot())  # snapshot
        copied_revision_before = json.loads(copy.sudo().spreadsheet_revision_ids[0].commands)  # revision before snapshot
        copied_revision_after = json.loads(copy.sudo().spreadsheet_revision_ids[2].commands)  # revision after snapshot

        self.assertEqual(copied_data["sheets"][0]["comments"], {})
        self.assertEqual(copied_snapshot["sheets"][0]["comments"], {})
        self.assertEqual(copied_revision_before["commands"], [])
        self.assertEqual(copied_revision_after["commands"], [])

    def test_fork_history_filters_out_comments(self):
        base_data = {
            "sheets": [{
                "comments": [
                    {"A1": {"threadId": 1, "isResolved": False}}
                ]
            }],
            "revisionId": "revision-id"
        }
        spreadsheet = self.env["spreadsheet.test"].create({"spreadsheet_data": json.dumps(base_data)})

        spreadsheet._dispatch_command(add_thread_command(2))
        snapshot_data = COPY.deepcopy(base_data)
        snapshot_data["revisionId"] = "snapshot-revision-id"
        snapshot_data["sheets"][0]["comments"][0]["A2"] = {"threadId": 1, "isResolved": False}

        self.snapshot(spreadsheet, spreadsheet.sudo().current_revision_uuid, "snapshot-revision-id", snapshot_data)
        spreadsheet._dispatch_command(add_thread_command(3))

        action = spreadsheet.fork_history(spreadsheet.sudo().spreadsheet_revision_ids[-1].id, snapshot_data)
        fork_id = action["params"]["spreadsheet_id"]
        fork = self.env["spreadsheet.test"].browse(fork_id).with_context(
            active_test=False)  # get all the archived revisions

        copied_data = json.loads(fork.spreadsheet_data)
        copied_snapshot = json.loads(fork._get_spreadsheet_serialized_snapshot())  # snapshot
        copied_revision_before = json.loads(fork.sudo().spreadsheet_revision_ids[0].commands)  # revision before snapshot
        copied_revision_after = json.loads(fork.sudo().spreadsheet_revision_ids[2].commands)  # revision after snapshot

        self.assertEqual(copied_data["sheets"][0]["comments"], {})
        self.assertEqual(copied_snapshot["sheets"][0]["comments"], {})
        self.assertEqual(copied_revision_before["commands"], [])
        self.assertEqual(copied_revision_after["commands"], [])

    def test_reset_spreadsheet_data(self):
        spreadsheet = self.env["spreadsheet.test"].create({})
        # one revision before the snapshot (it's archived by the snapshot)
        spreadsheet._dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        self.snapshot(
            spreadsheet,
            spreadsheet.current_revision_uuid, "snapshot-revision-id",
            {"sheets": [], "revisionId": "snapshot-revision-id"},
        )
        # one revision after the snapshot
        spreadsheet._dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        spreadsheet.spreadsheet_data = r"{}"
        self.assertFalse(spreadsheet.spreadsheet_snapshot)
        self.assertFalse(
            spreadsheet.with_context(active_test=True).sudo().spreadsheet_revision_ids,
        )

    def test_fork_history(self):
        spreadsheet = self.env["spreadsheet.test"].create({})
        spreadsheet._dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        rev1 = spreadsheet.sudo().spreadsheet_revision_ids[0]
        action = spreadsheet.fork_history(rev1.id, {"test": "snapshot"})
        self.assertTrue(isinstance(action, dict))

        copy_id = action["params"]["spreadsheet_id"]
        spreadsheet_copy = self.env["spreadsheet.test"].browse(copy_id)
        self.assertTrue(spreadsheet_copy.exists())
        fork_revision = spreadsheet_copy.with_context(active_test=False).sudo().spreadsheet_revision_ids
        self.assertEqual(len(fork_revision), 1)
        self.assertEqual(fork_revision.commands, rev1.commands)
        self.assertEqual(fork_revision.active, False)

    def test_fork_history_before_snapshot(self):
        spreadsheet = self.env["spreadsheet.test"].create({})
        spreadsheet._dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        self.snapshot(
            spreadsheet,
            spreadsheet.current_revision_uuid,
            "snapshot-revision-id",
             {"sheets": [], "revisionId": "snapshot-revision-id"}
        )
        spreadsheet._dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        rev1 = spreadsheet.with_context(active_test=False).sudo().spreadsheet_revision_ids[0]
        fork_snapshot = {"test": "snapshot"}
        action = spreadsheet.fork_history(rev1.id, fork_snapshot)
        fork_id = action["params"]["spreadsheet_id"]
        spreadsheet_fork = self.env["spreadsheet.test"].browse(fork_id)
        self.assertEqual(json.loads(spreadsheet_fork._get_spreadsheet_serialized_snapshot()), fork_snapshot)
        self.assertEqual(
            spreadsheet_fork.with_context(active_test=False).sudo().spreadsheet_revision_ids.active,
            False
        )

    def test_restore_version(self):
        spreadsheet = self.env["spreadsheet.test"].create({})
        spreadsheet._dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        spreadsheet._dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        revisions = spreadsheet.sudo().spreadsheet_revision_ids
        rev1 = revisions[0]
        rev2 = revisions[1]

        spreadsheet.restore_spreadsheet_version(
            rev1.id,
            {"test": "snapshot", "revisionId": rev1.revision_uuid}
        )
        self.assertFalse(rev1.active)
        self.assertFalse(rev2.exists())

        self.assertEqual(
            json.loads(spreadsheet._get_spreadsheet_serialized_snapshot()),
            {"test": "snapshot", "revisionId": spreadsheet.current_revision_uuid}
        )

    def test_restore_version_before_snapshot(self):
        spreadsheet = self.env["spreadsheet.test"].create({})

        spreadsheet._dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        self.snapshot(
            spreadsheet,
            spreadsheet.current_revision_uuid,
            "snapshot-revision-id",
            {"sheets": [], "revisionId": "snapshot-revision-id"},
        )
        spreadsheet._dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))

        revisions = spreadsheet.sudo().with_context(active_test=False).spreadsheet_revision_ids
        rev1 = revisions[0]
        snapshot_rev = revisions[1]
        rev3 = revisions[2]

        spreadsheet.restore_spreadsheet_version(
            rev1.id,
            {"test": "snapshot", "revisionId": rev1.revision_uuid}
        )
        self.assertFalse(rev1.active)
        self.assertFalse((snapshot_rev | rev3).exists())

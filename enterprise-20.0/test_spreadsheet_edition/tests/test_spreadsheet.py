# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime
from freezegun import freeze_time
import psycopg2
import json
from odoo.tools import mute_logger

from odoo.exceptions import AccessError
from odoo.tests.common import new_test_user
from odoo.addons.spreadsheet_edition.tests.spreadsheet_test_case import SpreadsheetTestCase


class SpreadsheetMixinTest(SpreadsheetTestCase):

    def test_cannot_dispatch_with_invalid_parent_revision(self):
        spreadsheet = self.env["spreadsheet.test"].create({})

        revision_payload = self.new_revision_data(spreadsheet)
        is_accepted = spreadsheet._dispatch_spreadsheet_message(revision_payload)
        self.assertTrue(is_accepted, "the first revision should be accepted")

        revision_payload = self.new_revision_data(spreadsheet, serverRevisionId="something")
        is_accepted = spreadsheet._dispatch_spreadsheet_message(revision_payload)
        self.assertFalse(is_accepted)

    def test_cannot_delete_revision_in_a_chain(self):
        spreadsheet = self.env["spreadsheet.test"].create({})
        spreadsheet._dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        spreadsheet._dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        spreadsheet._dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        revision = spreadsheet.spreadsheet_revision_ids[1]
        with self.assertRaises(psycopg2.errors.UniqueViolation), mute_logger("odoo.sql_db"):
            revision.unlink()

    def test_user_can_undo_own_revision(self):
        user = new_test_user(self.env, login="owner", groups="base.group_user,test_spreadsheet.group_spreadsheet_test")
        spreadsheet = self.env["spreadsheet.test"].create({})
        revision = self.new_revision_data(spreadsheet)
        spreadsheet.with_user(user)._dispatch_spreadsheet_message(revision)
        undo = {
            "type": "REVISION_UNDONE",
            "undoneRevisionId": revision["nextRevisionId"],
            "nextRevisionId": "undo-revision-id",
            "serverRevisionId": spreadsheet.current_revision_uuid,
        }
        is_accepted = spreadsheet.with_user(user)._dispatch_spreadsheet_message(undo)
        self.assertTrue(is_accepted)

    def test_user_cannot_undo_other_user_revision(self):
        user = new_test_user(self.env, login="other_user", groups="base.group_user,test_spreadsheet.group_spreadsheet_test")
        spreadsheet = self.env["spreadsheet.test"].create({})
        revision = self.new_revision_data(spreadsheet)
        spreadsheet._dispatch_spreadsheet_message(revision)
        undo = {
            "type": "REVISION_UNDONE",
            "undoneRevisionId": revision["nextRevisionId"],
            "nextRevisionId": "undo-revision-id",
            "serverRevisionId": spreadsheet.current_revision_uuid,
        }
        with self.assertRaises(AccessError):
            spreadsheet.with_user(user)._dispatch_spreadsheet_message(undo)

    def test_user_cannot_redo_other_user_revision(self):
        user = new_test_user(self.env, login="other_user", groups="base.group_user,test_spreadsheet.group_spreadsheet_test")
        spreadsheet = self.env["spreadsheet.test"].create({})
        revision = self.new_revision_data(spreadsheet)
        spreadsheet._dispatch_spreadsheet_message(revision)
        redo = {
            "type": "REVISION_REDONE",
            "redoneRevisionId": revision["nextRevisionId"],
            "nextRevisionId": "redo-revision-id",
            "serverRevisionId": spreadsheet.current_revision_uuid,
        }
        with self.assertRaises(AccessError):
            spreadsheet.with_user(user)._dispatch_spreadsheet_message(redo)

    def test_rename_revision(self):
        spreadsheet = self.env["spreadsheet.test"].create({})
        spreadsheet._dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        revision = spreadsheet.spreadsheet_revision_ids[0]
        self.assertEqual(revision.name, False)

        spreadsheet.rename_revision(revision.id, "new revision name")
        self.assertEqual(revision.name, "new revision name")

    def test_get_spreadsheet_history(self):
        with freeze_time("2020-02-02"):
            spreadsheet = self.env["spreadsheet.test"].create({})
            spreadsheet._dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
            self.snapshot(
                spreadsheet,
                spreadsheet.current_revision_uuid, "snapshot-revision-id", {"sheets": [], "revisionId": "snapshot-revision-id"},
            )
            spreadsheet._dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        user = spreadsheet.create_uid
        data = spreadsheet.get_spreadsheet_history()
        revisions = data["revisions"]
        self.assertEqual(len(revisions), 3)
        for revision in revisions:
            self.assertEqual(revision["timestamp"], datetime(2020, 2, 2, 0, 0, 0))
            self.assertEqual(revision["user"], (user.id, user.name))

        self.env.company.fiscalyear_last_day = 7
        self.env.company.fiscalyear_last_month = "6"

        # from snapshot
        with freeze_time("2023-07-30"):
            data = spreadsheet.get_spreadsheet_history(from_snapshot=True)
            revisions = data["revisions"]
            self.assertEqual(len(revisions), 1)
            self.assertEqual(revisions[0]["timestamp"], datetime(2020, 2, 2, 0, 0, 0))
            self.assertEqual(revisions[0]["user"], (user.id, user.name))
            self.assertEqual(data["metadata"]["current_fiscal_year_start"], "2023-06-08")
            self.assertEqual(data["metadata"]["current_fiscal_year_end"], "2024-06-07")

    def test_can_replay_complete_history(self):
        spreadsheet = self.env["spreadsheet.test"].create({})
        self.assertTrue(spreadsheet._can_replay_complete_history())

        spreadsheet._dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        snapshot_data = {"sheets": [], "revisionId": "snapshot-revision-id"}
        self.snapshot(
            spreadsheet,
            spreadsheet.current_revision_uuid,
            "snapshot-revision-id",
            snapshot_data,
        )
        # one revision after the snapshot, still active
        spreadsheet._dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))

        # the snapshot diverged from `spreadsheet_data`, but the archived
        # revisions bridging them are still there
        self.assertTrue(spreadsheet._can_replay_complete_history())
        data = spreadsheet.get_spreadsheet_history()
        self.assertEqual(data["data"], json.loads(spreadsheet.spreadsheet_data))
        self.assertEqual(len(data["revisions"]), 3)

        # drop the archived revisions: `spreadsheet_data` can no longer be
        # replayed up to the snapshot
        spreadsheet.with_context(active_test=False).spreadsheet_revision_ids.filtered(
            lambda revision: not revision.active
        ).unlink()

        self.assertFalse(spreadsheet._can_replay_complete_history())
        data = spreadsheet.get_spreadsheet_history()
        self.assertEqual(data["data"], snapshot_data)
        self.assertEqual(len(data["revisions"]), 1)

    def test_currency_passed_to_spreadsheet_history(self):
        spreadsheet = self.env["spreadsheet.test"].create({})
        company_eur = self.env["res.company"].create({"currency_id": self.env.ref("base.EUR").id, "name": "EUR"})
        company_gbp = self.env["res.company"].create({"currency_id": self.env.ref("base.GBP").id, "name": "GBP"})

        data = spreadsheet.with_company(company_eur).get_spreadsheet_history()
        self.assertEqual(data["metadata"]["default_currency"]["code"], "EUR")
        self.assertEqual(data["metadata"]["default_currency"]["symbol"], "€")

        data = spreadsheet.with_company(company_gbp).get_spreadsheet_history()
        self.assertEqual(data["metadata"]["default_currency"]["code"], "GBP")
        self.assertEqual(data["metadata"]["default_currency"]["symbol"], "£")

    def test_get_spreadsheet_base_user_access_right_history(self):
        user = new_test_user(self.env, login="test", groups="base.group_user,test_spreadsheet.group_spreadsheet_test")
        spreadsheet = self.env["spreadsheet.test"].create({})
        spreadsheet._dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        spreadsheet.invalidate_recordset()
        data = spreadsheet.with_user(user).get_spreadsheet_history()
        self.assertEqual(len(data["revisions"]), 1)

    def test_empty_spreadsheet_server_revision_id(self):
        spreadsheet = self.env["spreadsheet.test"].create({})
        self.assertEqual(spreadsheet.current_revision_uuid, "START_REVISION")
        self.assertEqual(
            spreadsheet.current_revision_uuid,
            "START_REVISION"
        )

    def test_no_data_server_revision_id(self):
        spreadsheet = self.env["spreadsheet.test"].create({})
        spreadsheet.spreadsheet_snapshot = False
        spreadsheet.spreadsheet_data = False
        self.assertEqual(spreadsheet.current_revision_uuid, "START_REVISION")

    def test_last_revision_is_server_revision_id(self):
        spreadsheet = self.env["spreadsheet.test"].create({})

        revision_data = self.new_revision_data(spreadsheet)
        next_revision_id = revision_data["nextRevisionId"]
        spreadsheet._dispatch_spreadsheet_message(revision_data)
        self.assertEqual(spreadsheet.current_revision_uuid, next_revision_id)

        # dispatch new revision on top
        revision_data = self.new_revision_data(spreadsheet)
        next_revision_id = revision_data["nextRevisionId"]
        spreadsheet._dispatch_spreadsheet_message(revision_data)
        self.assertEqual(spreadsheet.current_revision_uuid, next_revision_id)

    def test_snapshotted_server_revision_id(self):
        spreadsheet = self.env["spreadsheet.test"].create({})
        snapshot_revision_id = "snapshot-id"
        self.snapshot(
            spreadsheet,
            spreadsheet.current_revision_uuid,
            snapshot_revision_id,
            {"revisionId": snapshot_revision_id},
        )
        self.assertEqual(spreadsheet.current_revision_uuid, snapshot_revision_id)
        self.assertEqual(
            spreadsheet.current_revision_uuid,
            snapshot_revision_id
        )

        # dispatch revision after snapshot
        revision_data = self.new_revision_data(spreadsheet)
        next_revision_id = revision_data["nextRevisionId"]
        spreadsheet._dispatch_spreadsheet_message(revision_data)
        self.assertEqual(spreadsheet.current_revision_uuid, next_revision_id)

    def test_get_spreadsheets(self):
        spreadsheet = self.env["spreadsheet.test"].create({})
        self.assertEqual(
            self.env["spreadsheet.test"].get_spreadsheets(),
            {
                "records": [{
                    "id": spreadsheet.id,
                    "display_name": spreadsheet.display_name,
                    "display_thumbnail": False
                }],
                "total": 1,
            }
        )

    def test_get_spreadsheets_limit(self):
        self.env["spreadsheet.test"].create({})
        self.env["spreadsheet.test"].create({})
        result = self.env["spreadsheet.test"].get_spreadsheets([], limit=1)
        self.assertEqual(len(result["records"]), 1)
        self.assertEqual(result["total"], 2)

    def test_get_spreadsheets_domain(self):
        first = self.env["spreadsheet.test"].create({})
        self.env["spreadsheet.test"].create({})
        result = self.env["spreadsheet.test"].get_spreadsheets([("id", "=", first.id)], limit=1)
        self.assertEqual(len(result["records"]), 1)
        self.assertEqual(result["records"][0]["id"], first.id)
        self.assertEqual(result["total"], 1)

    def test_get_selector_spreadsheet_models(self):
        result = self.env["spreadsheet.mixin"].get_selector_spreadsheet_models()
        self.assertTrue(any(r["model"] == "spreadsheet.test" for r in result))

    def test_action_open_new_spreadsheet(self):
        action = self.env["spreadsheet.test"].action_open_new_spreadsheet()
        spreadsheet = self.env["spreadsheet.test"].browse(action["params"]["spreadsheet_id"])
        self.assertTrue(spreadsheet.exists())

    def test_keep_original_spreadsheet_author_with_multiple_users(self):
        test_user_1 = new_test_user(self.env, login="test_user_1", groups="base.group_user,test_spreadsheet.group_spreadsheet_test")
        test_user_2 = new_test_user(self.env, login="test_user_2", groups="base.group_user,test_spreadsheet.group_spreadsheet_test")
        test_user_3 = new_test_user(self.env, login="test_user_3", groups="base.group_user,test_spreadsheet.group_spreadsheet_test")
        spreadsheet = self.env["spreadsheet.test"].with_user(test_user_1).create({})
        spreadsheet._dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        spreadsheet.with_user(test_user_2)._dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        spreadsheet.with_user(test_user_3)._dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        copy = spreadsheet.with_user(self.env.ref("base.user_admin")).copy()
        revisions = copy.spreadsheet_revision_ids
        self.assertEqual(revisions[0].author_id, test_user_1)
        self.assertEqual(revisions[1].author_id, test_user_2)
        self.assertEqual(revisions[2].author_id, test_user_3)
        spreadsheet.with_user(self.env.ref("base.user_admin"))._dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        self.assertEqual(spreadsheet.sudo().spreadsheet_revision_ids[-1].author_id, self.env.ref("base.user_admin"))

    def test_keep_original_spreadsheet_revision_timestamps(self):
        with freeze_time("2025-01-01 12:00:00"):
            spreadsheet = self.env["spreadsheet.test"].create({})
            spreadsheet._dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
            spreadsheet._dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
            spreadsheet._dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        with freeze_time("2025-01-01 23:00:00"):
            copy = spreadsheet.copy()
            revisions = copy.spreadsheet_revision_ids
            self.assertEqual(revisions[0].revision_date, datetime(2025, 1, 1, 12, 0, 0))
            self.assertEqual(revisions[1].revision_date, datetime(2025, 1, 1, 12, 0, 0))
            self.assertEqual(revisions[2].revision_date, datetime(2025, 1, 1, 12, 0, 0))
            copy._dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
            self.assertEqual(
                copy.spreadsheet_revision_ids[-1].revision_date,
                datetime(2025, 1, 1, 23, 0, 0),
            )

    def test_get_search_arch(self):

        # default search view
        arch = '<search><field name="name"/></search>'
        self.env["ir.ui.view"].create({
            "name": "Search View",
            "model": "res.partner",
            "type": "search",
            "arch": arch,
        })
        action = self.env["ir.actions.act_window"].create({
            "name": "Action2",
            "res_model": "res.partner",
        })
        xml_id = "spreadsheet_test_partner_search_view"
        module = "test_spreadsheet_edition"
        self.env["ir.model.data"].create({
            "name": xml_id,
            "model": "ir.actions.act_window",
            "module": module,
            "res_id": action.id,
        })
        xml_id = f"{module}.{xml_id}"
        result = self.env["spreadsheet.mixin"].get_search_view_archs([xml_id])
        self.assertEqual(result, {"res.partner": [arch]})

        # with a custom search view
        custom_arch = '<search><field name="name" string="custom search view"/></search>'
        custom_search_view = self.env["ir.ui.view"].create({
            "name": "Custom Search View",
            "model": "res.partner",
            "type": "search",
            "arch": custom_arch,
        })
        action.search_view_id = custom_search_view
        result = self.env["spreadsheet.mixin"].get_search_view_archs([xml_id])
        self.assertEqual(result, {"res.partner": [custom_arch]})

    def test_image_attachment_deleted(self):
        spreadsheet = self.env["spreadsheet.test"].create({})
        image = self.env["ir.attachment"].create({
            "name": "image.png",
            "raw": b"test",
        })
        spreadsheet.spreadsheet_image_ids = image
        self.assertTrue(image.exists())
        spreadsheet.unlink()
        self.assertFalse(image.exists())

    def test_shared_image_attachment_deleted(self):
        spreadsheet = self.env["spreadsheet.test"].create({})
        image = self.env["ir.attachment"].create({
            "name": "image.png",
            "raw": b"test",
        })
        spreadsheet.spreadsheet_image_ids = image
        spreadsheet2 = spreadsheet.copy()
        self.assertIn(image, spreadsheet2.spreadsheet_image_ids)
        self.assertTrue(image.exists())
        spreadsheet.unlink()
        self.assertTrue(image.exists())  # still used by spreadsheet2
        spreadsheet2.unlink()
        self.assertFalse(image.exists())

    def test_image_attachment_copy_access_rights(self):
        spreadsheet = self.env["spreadsheet.test"].create({})
        image = self.env["ir.attachment"].create({
            "name": "image.png",
            "raw": b"test",
        })
        spreadsheet.spreadsheet_image_ids = image
        raoul = new_test_user(self.env, "Bob", groups="base.group_user,test_spreadsheet.group_spreadsheet_test")
        self.assertFalse(image.with_user(raoul).has_access("read"))
        copy = spreadsheet.with_user(raoul).copy()
        self.assertEqual(copy.sudo().spreadsheet_image_ids, image)

    def test_image_attachment_deleted_access_rights(self):
        spreadsheet = self.env["spreadsheet.test"].create({})
        image = self.env["ir.attachment"].create({
            "name": "image.png",
            "raw": b"test",
        })
        spreadsheet.spreadsheet_image_ids = image
        raoul = new_test_user(self.env, "Bob", groups="base.group_user,test_spreadsheet.group_spreadsheet_test")
        self.assertFalse(image.with_user(raoul).has_access("read"))
        spreadsheet.with_user(raoul).unlink()  # deleted by another user
        self.assertFalse(image.exists())

    def test_cell_thread_naming(self):
        spreadsheet1 = self.env["spreadsheet.test"].create({})
        spreadsheet2 = self.env["spreadsheet.test"].create({})
        threads = self.env["spreadsheet.cell.thread"].create([
                {"dummy_id": spreadsheet1.id},
                {"dummy_id": spreadsheet2.id},
        ])
        thread1, thread2 = threads
        self.assertEqual(
            threads.mapped("display_name"),  # compute in batch
            [thread1.display_name, thread2.display_name]
        )

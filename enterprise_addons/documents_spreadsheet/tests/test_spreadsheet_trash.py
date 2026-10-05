from .common import SpreadsheetTestCommon
from odoo.exceptions import UserError
from odoo.tests.common import tagged


@tagged('post_install', '-at_install')
class TestSpreadsheetTrashBehavior(SpreadsheetTestCommon):
    def test_dispatch_fails_when_spreadsheet_in_trash(self):
        spreadsheet = self.create_spreadsheet()
        revision = self.new_revision_data(spreadsheet)
        access_token = spreadsheet.sudo().access_token

        accepted = spreadsheet._dispatch_spreadsheet_message(revision, access_token)
        self.assertTrue(accepted, "Dispatch should work before moving to trash")

        spreadsheet.action_archive()
        with self.assertRaises(UserError, msg="You cannot modify this spreadsheet because it is in the trash."):
            spreadsheet._dispatch_spreadsheet_message(revision, access_token)

    def test_version_restore_fails_when_in_trash(self):
        spreadsheet = self.create_spreadsheet()
        spreadsheet._dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        revisions = spreadsheet.spreadsheet_revision_ids

        spreadsheet.action_archive()
        with self.assertRaises(UserError, msg="You cannot restore this version because the spreadsheet is in the trash."):
            spreadsheet.restore_spreadsheet_version(
                revisions[0].id,
                {"test": "snapshot", "revisionId": revisions[0].revision_uuid}
            )

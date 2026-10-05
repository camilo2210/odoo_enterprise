# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged, new_test_user
from ..common import SpreadsheetTestTourCommon


@tagged('post_install', '-at_install')
class TestSpreadsheetSharePublic(SpreadsheetTestTourCommon):

    def test_share_edit_public(self):
        portal_user = new_test_user(self.env, "spreadsheetPortalUser", groups="base.group_portal")
        logins = [
            None,  # public user
            portal_user.login,
        ]
        for login in logins:
            with self.subTest(login=login):
                spreadsheet = self.env['documents.document'].create({
                    'handler': 'spreadsheet',
                    'folder_id': self.folder.id,
                    'raw': b'{}',
                    'name': 'Test spreadsheet',
                    'access_via_link': 'edit',
                })
                self.start_tour(
                    spreadsheet.access_url,
                    'spreadsheet_share_edit_public',
                    login=login,
                )
                self.assertEqual(len(spreadsheet.spreadsheet_revision_ids), 1)

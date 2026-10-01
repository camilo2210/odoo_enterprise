# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged
from odoo.tests.common import HttpCase


@tagged('post_install', '-at_install')
class TestSpreadsheetSharePublic(HttpCase):

    def test_command_whitelist(self):
        self.start_tour(
            '/odoo',
            'test_spreadsheet_edition.spreadsheet_command_whitelist',
            login='admin',
        )

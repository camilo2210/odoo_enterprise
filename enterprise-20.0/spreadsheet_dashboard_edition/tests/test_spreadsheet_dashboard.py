import json

from odoo.exceptions import ValidationError
from odoo.tests import tagged, new_test_user
from odoo.tools import BinaryBytes

from odoo.addons.spreadsheet_dashboard.tests.common import DashboardTestCommon
from odoo.addons.spreadsheet_edition.tests.spreadsheet_test_case import SpreadsheetTestCase


@tagged('at_install', '-post_install')  # LEGACY at_install
class TestSpreadsheetDashboard(DashboardTestCommon, SpreadsheetTestCase):

    def test_is_from_data(self):
        dashboard = self.create_dashboard()
        xml_id = "spreadsheet_dashboard.external_id"
        self.env['ir.model.data'].create({
            'name': xml_id,
            'model': 'spreadsheet.dashboard',
            'res_id': dashboard.id,
        })
        self.assertFalse(dashboard.is_from_data)
        dashboard.sample_dashboard_file_path = 'spreadsheet_dashboard/sample_dashboard.json'
        self.assertTrue(dashboard.is_from_data)

    def test_dont_have_external_id(self):
        dashboard = self.create_dashboard()
        self.assertFalse(dashboard.is_from_data)

    def test_from_data_internal_user(self):
        dashboard = self.create_dashboard()
        user = new_test_user(self.env, login='raoul', groups='base.group_user')
        self.assertFalse(dashboard.with_user(user).is_from_data)

    def test_dashboard_list_columns_cannot_define_string(self):
        dashboard = self.create_dashboard()
        dashboard.sample_dashboard_file_path = 'spreadsheet_dashboard/sample_dashboard.json'
        data = {
            "lists": {
                "1": {
                    "id": "1",
                    "model": "res.partner",
                    "columns": [{"name": "name", "string": "Name"}],
                    "domain": [],
                    "context": {},
                    "orderBy": [],
                    "name": "Partners",
                },
            },
        }
        with self.assertRaises(ValidationError) as error:
            dashboard.spreadsheet_binary_data = BinaryBytes(json.dumps(data).encode())
        self.assertEqual(
            str(error.exception),
            "List columns in dashboard 'a dashboard' must not define 'string' explicitly. "
            "They should fall back to the translated field label.",
        )

    def test_dashboard_list_columns_can_define_string_with_translation_headers(self):
        dashboard = self.create_dashboard()
        dashboard.sample_dashboard_file_path = 'spreadsheet_dashboard/sample_dashboard.json'
        data = {
            "lists": {
                "1": {
                    "id": "1",
                    "model": "res.partner",
                    "translateHeaders": True,
                    "columns": [{"name": "name", "string": "Name"}],
                    "domain": [],
                    "context": {},
                    "orderBy": [],
                    "name": "Partners",
                },
            },
        }
        dashboard.spreadsheet_binary_data = BinaryBytes(json.dumps(data).encode())

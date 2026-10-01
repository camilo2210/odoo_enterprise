from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestSpreadsheetDashboardSheetSelection(HttpCase):
    def _assert_loaded_sheets(self, show_rates, encode_uom_xmlid, expected_sheet_ids):
        company = self.env.company
        company.timesheet_show_rates = show_rates
        company.timesheet_encode_uom_id = self.env.ref(encode_uom_xmlid)

        dashboard = self.env.ref('spreadsheet_dashboard_sale_timesheet.spreadsheet_dashboard_timesheet')
        delete_sheet_ids = {
            command['sheetId']
            for command in dashboard._get_dashboard_commands()
            if command.get('type') == 'DELETE_SHEET'
        }
        all_sheet_ids = {
            'sheet1-no-target',
            'sheet2-no-target-days',
            'sheet3-targets',
            'sheet4-targets-days',
        }
        loaded_sheet_ids = all_sheet_ids - delete_sheet_ids

        self.assertEqual(loaded_sheet_ids, expected_sheet_ids)

    def test_01_loaded_sheet_no_rates_hours(self):
        self._assert_loaded_sheets(False, 'uom.product_uom_hour', {'sheet1-no-target', 'sheet2-no-target-days', 'sheet3-targets', 'sheet4-targets-days'})

    def test_02_loaded_sheet_no_rates_days(self):
        self._assert_loaded_sheets(False, 'uom.product_uom_day', {'sheet2-no-target-days', 'sheet3-targets', 'sheet4-targets-days'})

    def test_03_loaded_sheet_rates_hours(self):
        self._assert_loaded_sheets(True, 'uom.product_uom_hour', {'sheet3-targets', 'sheet4-targets-days'})

    def test_04_loaded_sheet_rates_days(self):
        self._assert_loaded_sheets(True, 'uom.product_uom_day', {'sheet4-targets-days'})

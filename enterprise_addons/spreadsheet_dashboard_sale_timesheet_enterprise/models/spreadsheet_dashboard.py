from odoo import models


class SpreadsheetDashboard(models.Model):
    _inherit = 'spreadsheet.dashboard'

    def _get_dashboard_commands(self):
        commands = super()._get_dashboard_commands()
        dashboard_id = self.env.ref('spreadsheet_dashboard_sale_timesheet.spreadsheet_dashboard_timesheet').id
        if self.id == dashboard_id:
            is_encode_uom_days = self.env.company.timesheet_encode_uom_id == self.env.ref('uom.product_uom_day', raise_if_not_found=False)
            sheets = [
                {'sheetId': 'sheet1-no-target', 'sheetName': 'Dashboard'},
                {'sheetId': 'sheet2-no-target-days', 'sheetName': 'Dashboard Days'},
                {'sheetId': 'sheet3-targets', 'sheetName': 'Dashboard Targets'},
                {'sheetId': 'sheet4-targets-days', 'sheetName': 'Dashboard Targets Days'},
            ]
            if not self.env.company.timesheet_show_rates and is_encode_uom_days:
                commands.append({'type': 'DELETE_SHEET', **sheets[0]})
            elif self.env.company.timesheet_show_rates and not is_encode_uom_days:
                commands.append({'type': 'DELETE_SHEET', **sheets[0]})
                commands.append({'type': 'DELETE_SHEET', **sheets[1]})
            elif self.env.company.timesheet_show_rates and is_encode_uom_days:
                commands.append({'type': 'DELETE_SHEET', **sheets[0]})
                commands.append({'type': 'DELETE_SHEET', **sheets[1]})
                commands.append({'type': 'DELETE_SHEET', **sheets[2]})
        return commands

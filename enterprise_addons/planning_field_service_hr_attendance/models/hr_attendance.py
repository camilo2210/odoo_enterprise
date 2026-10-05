from odoo import fields, models


class HrAttendance(models.Model):
    _inherit = "hr.attendance"

    def _cron_auto_check_out(self):
        super()._cron_auto_check_out()
        auto_checked_out_employees = self.search([('out_mode', '=', 'auto_check_out'), ('check_in', '>=', fields.Datetime.today())]).employee_id
        auto_checked_out_employees.resource_id._erase_resource_live_location()

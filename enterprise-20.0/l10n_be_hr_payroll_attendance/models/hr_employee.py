# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from dateutil.relativedelta import relativedelta
from odoo import models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def _l10n_be_get_short_work_entries(self):
        employee_short_attendances = self.env['hr.attendance']._read_group(
            [
                ('employee_id', 'in', self.ids),
                ('date', '>', date.today() + relativedelta(days=-31)),
                ('worked_hours', '<', 2)
            ],
            groupby=['employee_id', 'date:day'],
            aggregates=['worked_hours:sum'],
        )
        employee_ids = {employee.id for employee, day, hours in employee_short_attendances if hours < 2}
        return self.env['hr.employee'].browse(employee_ids)

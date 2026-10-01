# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class HrPayrollStructureType(models.Model):
    _inherit = 'hr.payroll.structure.type'
    _description = 'Salary Structure Type'

    wage_type = fields.Selection(
        selection_add=[("daily", "Daily Wage")],
        ondelete={"daily": 'set monthly'},
    )

    def _get_selection_schedule_pay(self):
        if self.env.company.country_code == 'PH':
            return [
                ('annually', self.env._('year')),
                ('monthly', self.env._('month')),
                ('semi-monthly', self.env._('half-month')),
                ('bi-weekly', self.env._('2 weeks')),
                ('weekly', self.env._('week')),
                ('daily', self.env._('day')),
            ]
        return super()._get_selection_schedule_pay()

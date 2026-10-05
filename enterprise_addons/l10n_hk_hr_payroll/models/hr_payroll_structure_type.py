# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class HrPayrollStructureType(models.Model):
    _inherit = 'hr.payroll.structure.type'
    _description = 'Salary Structure Type'

    def _get_selection_schedule_pay(self):
        if self.env.company.country_code == 'HK':
            return [
                ('monthly', self.env._('month')),
                ('semi-monthly', self.env._('half-month')),
                ('bi-weekly', self.env._('2 weeks')),
                ('weekly', self.env._('week')),
                ('daily', self.env._('day')),
            ]
        return super()._get_selection_schedule_pay()

# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class HrPayrollStructureType(models.Model):
    _inherit = 'hr.payroll.structure.type'
    _description = 'Salary Structure Type'

    def _get_selection_schedule_pay(self):
        if self.env.company.country_code == 'MX':
            return [
                ('daily', self.env._('day')),
                ('weekly', self.env._('week')),
                ('10_days', self.env._('10 days')),
                ('14_days', self.env._('14 days')),
                ('bi-weekly', self.env._('2 weeks')),
                ('monthly', self.env._('month')),
                ('bi-monthly', self.env._('2 months')),
            ]
        return super()._get_selection_schedule_pay()

# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrPayrollStructureType(models.Model):
    _inherit = "hr.payroll.structure.type"

    l10n_au_default_input_type_ids = fields.Many2many(
        "hr.salary.rule",
        string="Default Allowances",
        help="Default allowances for this structure type")

    def _get_selection_schedule_pay(self):
        if self.env.company.country_code == 'AU':
            return [
                ('quarterly', self.env._('quarter')),
                ('monthly', self.env._('month')),
                ('bi-weekly', self.env._('fortnight')),
                ('weekly', self.env._('week')),
                ('daily', self.env._('day')),
            ]
        return super()._get_selection_schedule_pay()

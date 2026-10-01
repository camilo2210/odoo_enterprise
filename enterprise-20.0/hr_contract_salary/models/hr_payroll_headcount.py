# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrPayrollHeadcountLine(models.Model):
    _inherit = 'hr.payroll.headcount.line'

    employer_cost = fields.Monetary(compute='_compute_employer_cost', string='Employer Cost')

    @api.depends('version_id.final_yearly_costs')
    def _compute_employer_cost(self):
        for line in self:
            line.employer_cost = line.version_id.final_yearly_costs / 12.0

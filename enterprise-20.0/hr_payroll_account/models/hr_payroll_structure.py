#-*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrPayrollStructure(models.Model):
    _inherit = 'hr.payroll.structure'

    journal_id = fields.Many2one(
        comodel_name='account.journal',
        string='Salary Journal',
        compute='_compute_journal_id', store=True, readonly=False,
        company_dependent=True,
    )

    def _compute_journal_id(self):
        default_structure = self.env.ref('hr_payroll.default_structure', False)
        for structure in self:
            if not structure.journal_id and (journal := (
                (default_structure and default_structure.journal_id)
                or self.env['account.chart.template'].ref('hr_payroll_account_journal', False)
            )):
                structure.journal_id = journal

    @api.model_create_multi
    def create(self, vals_list):
        structures = super().create(vals_list)
        for company in self.env['res.company'].sudo().search([]):
            structures.sudo().with_company(company)._compute_journal_id()
        return structures

    @api.constrains('journal_id')
    def _check_journal_id(self):
        for record_sudo in self.sudo():
            if record_sudo.journal_id.currency_id and record_sudo.journal_id.currency_id != record_sudo.journal_id.company_id.currency_id:
                raise ValidationError(
                    _('Incorrect journal: The journal must be in the same currency as the company')
                )

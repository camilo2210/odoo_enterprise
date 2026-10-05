# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.fields import Domain
from datetime import date, datetime
from dateutil.relativedelta import relativedelta


class TestL10nBeMultiplePayruns(models.TransientModel):
    _name = 'test.l10n.be.multiple.payruns'
    _description = 'Belgium: Multiple Payruns'

    @api.model
    def default_get(self, fields):
        if self.env.company.country_id.code != "BE":
            raise UserError(_('This feature seems to be as exclusive as Belgian chocolates. You must be logged in to a Belgian company to use it.'))
        return super().default_get(fields)

    employee_type_ids = fields.Many2many('hr.employee.type', string='Employee Types')
    structure_domain = fields.Char(compute='_compute_structure_domain')
    country_id = fields.Many2one(
        'res.country',
        string='Country',
        related='company_id.country_id',
        readonly=True,
    )
    company_id = fields.Many2one('res.company', string='Company', required=True, index=True, default=lambda self: self.env.company)
    structure_id = fields.Many2one('hr.payroll.structure', string='Pay Structure', readonly=False, required=True, index=True)
    date_start = fields.Date(string='From', required=True, default=lambda self: fields.Date.to_string(date.today().replace(day=1)))
    date_end = fields.Date(string='To', required=True, default=lambda self: fields.Date.to_string((datetime.now() + relativedelta(months=+1, day=1, days=-1)).date()))

    @api.depends('employee_type_ids', 'country_id')
    def _compute_structure_domain(self):
        for record in self:
            domain = Domain('country_id', 'in', [False, record.country_id.id])
            if record.employee_type_ids:
                employee_type_domain = Domain('employee_type_ids', 'in', [False] + record.employee_type_ids.ids)
                domain = Domain.AND([domain, employee_type_domain])
            record.structure_domain = domain

    def action_prepare_monthly_batches(self):
        current_start = self.date_start
        end_limit = self.date_end
        while current_start <= end_limit:
            next_month = current_start + relativedelta(months=1)
            end_of_month = next_month.replace(day=1) - relativedelta(days=1)
            current_end = min(end_of_month, end_limit)
            valid_versions = self.env['hr.payslip.run']._get_valid_versions(
                current_start,
                current_end,
                self.structure_id.id,
                self.company_id.id,
                self.employee_type_ids.ids,
            )
            created_payruns = self.env['hr.payslip.run'].create({
                'name': f"Payrun ({current_start} to {current_end})",
                'date_start': current_start,
                'date_end': current_end,
                'structure_id': self.structure_id.id,
                'company_id': self.company_id.id,
                'version_ids': [(6, 0, valid_versions.ids)],
            })
            created_payruns._generate_payslips()
            created_payruns.action_validate()
            current_start = current_end + relativedelta(days=1)

        return {
            'type': 'ir.actions.client',
            'tag': 'soft_reload',
        }

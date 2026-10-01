# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo import api, fields, models
from odoo.exceptions import UserError


class L10nBeEcoVouchersWizard(models.TransientModel):
    _name = 'l10n.be.eco.vouchers.wizard'
    _description = 'Eco-Vouchers Wizard'

    @api.model
    def default_get(self, fields):
        if self.env.company.country_id.code != "BE":
            raise UserError(self.env._('This feature seems to be as exclusive as Belgian chocolates. You must be logged in to a Belgian company to use it.'))
        return super().default_get(fields)

    def _get_default_company_id(self):
        if self.env.company.parent_id:
            raise UserError(self.env._("Reports can only be generated from a top-level company"))
        return self.env.company

    reference_year = fields.Selection(
        selection='_get_years', string='Reference Year', required=True,
        default=lambda self: str(fields.Date.context_today(self).year))

    line_ids = fields.One2many(
        'l10n.be.eco.vouchers.line.wizard', 'wizard_id',
        compute='_compute_line_ids', store=True, readonly=False)
    company_id = fields.Many2one(
        'res.company',
        default=_get_default_company_id,
        required=True,
    )
    branch_ids = fields.One2many('res.company', compute='_compute_branch_ids', compute_sudo=True)
    currency_id = fields.Many2one(related='company_id.currency_id')

    def _get_years(self):
        today = fields.Date.context_today(self)
        # show current year and 5 previous years
        return [(str(i), i) for i in range(today.year, today.year - 6, -1)]

    @api.depends('company_id')
    def _compute_branch_ids(self):
        report_companies = self.mapped('company_id')
        branches_by_root = self.env['res.company'].search([
            ('id', 'child_of', report_companies.ids),
        ]).grouped('root_id')

        for report in self:
            report.branch_ids = branches_by_root.get(report.company_id, report.company_id)

    @api.depends('reference_year', 'company_id')
    def _compute_line_ids(self):
        for wizard in self:
            year = int(wizard.reference_year)
            date_from = date(year, 1, 1)
            date_to = date(year, 12, 31)

            payslip_lines_domain = [
                ('code', '=', 'ECOVOUCHERS'),
                ('struct_id.code', '=', 'BEMONTHLY'),
                ('total', '!=', 0),
            ]

            if payrun_id := self.env.context.get('batch_id'):
                # If we trigger this from a batch, we only select payslips from the batch
                payrun = self.env['hr.payslip.run'].browse(payrun_id)
                payslip_lines_domain += [
                    ('slip_id', 'in', payrun.slip_ids.ids),
                ]
            else:
                payslip_lines_domain += [
                    ('date_from', '>=', date_from),
                    ('date_to', '<=', date_to),
                    ('company_id', 'in', wizard.branch_ids.ids),
                    ('slip_id.state', 'in', ['validated', 'paid']),
                ]

            payslip_lines = self.env['hr.payslip.line'].search(payslip_lines_domain)

            result = [(5, 0, 0)]
            for line in payslip_lines:
                result.append((0, 0, {
                    'employee_id': line.employee_id.id,
                    'amount': line.total,
                    'wizard_id': wizard.id,
                }))
            wizard.line_ids = result

    def action_export_xls(self):
        self.ensure_one()
        return {
            'name': 'Export Eco-Vouchers',
            'type': 'ir.actions.act_url',
            'url': '/export/ecovouchers/%s' % (self.id),
        }


class L10nBeEcoVouchersLineWizard(models.TransientModel):
    _name = 'l10n.be.eco.vouchers.line.wizard'
    _description = 'Eco-Vouchers Wizard'

    wizard_id = fields.Many2one('l10n.be.eco.vouchers.wizard')
    employee_id = fields.Many2one('hr.employee', required=True)
    niss = fields.Char(string="NISS", related='employee_id.niss')
    amount = fields.Monetary()
    currency_id = fields.Many2one(related='wizard_id.currency_id')

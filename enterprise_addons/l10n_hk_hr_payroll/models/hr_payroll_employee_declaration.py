# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models
from odoo.exceptions import UserError
from markupsafe import Markup


class HrPayrollEmployeeDeclaration(models.Model):
    _inherit = 'hr.payroll.employee.declaration'

    l10n_hk_hr_payroll_type_of_form = fields.Selection(
        selection=[
            ('O', "Original"),
            ('A', "Additional"),
            ('R', "Replacement"),
            ('S', "Supplementary"),
        ],
        string="Type Of Form",
        compute="_compute_l10n_hk_hr_payroll_type_of_form",
        store=True,
        readonly=False,
    )

    @api.depends('res_model', 'res_id')
    def _compute_l10n_hk_hr_payroll_type_of_form(self):
        """ To avoid frictions, we will pre-set the type of form when it makes sense to do so. """
        for declaration in self:
            sheet = self.env[declaration.res_model].browse(declaration.res_id)
            if issubclass(self.env.registry[declaration.res_model], self.env.registry['l10n_hk.ird']):
                if sheet.type_of_form == 'ARS':
                    declaration.l10n_hk_hr_payroll_type_of_form = 'A'
                else:  # Default for Original submission of IR56B/M and for all E/F/G declaration
                    declaration.l10n_hk_hr_payroll_type_of_form = 'O'
            else:
                declaration.l10n_hk_hr_payroll_type_of_form = False

    def action_open_ir56g_details(self):
        self.ensure_one()
        if self.res_model != "l10n_hk.ir56g":
            raise UserError(self.env._('Wrong Model'))
        sheet = self.env[self.res_model].browse(self.res_id)
        ir56g_line = sheet.appendice_line_ids.filtered(lambda l: l.employee_id == self.employee_id)
        if not ir56g_line:
            return {
                'type': 'ir.actions.act_window',
                'name': self.env._('IR56G Details'),
                'res_model': 'l10n_hk.ir56g.line',
                'view_mode': 'form',
                'view_id': self.env.ref('l10n_hk_hr_payroll.view_l10n_hk_ir56g_line_form').id,
                'target': 'new',
                'context': {
                    'default_employee_id': self.employee_id.id,
                    'default_sheet_id': sheet.id,
                },
            }
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('IR56G Details'),
            'res_model': 'l10n_hk.ir56g.line',
            'view_mode': 'form',
            'view_id': self.env.ref('l10n_hk_hr_payroll.view_l10n_hk_ir56g_line_form').id,
            'res_id': ir56g_line.id,
            'target': 'new',
        }

    def _generate_pdf(self):
        super()._generate_pdf()
        declarations_by_sheet = self.grouped(lambda d: (d.res_model, d.res_id))
        for (res_model, res_id), declarations in declarations_by_sheet.items():
            if issubclass(self.env.registry[res_model], self.env.registry['l10n_hk.ird']):
                continue  # Only apply this logic to Hong Kong reports inheriting from the IRD parent report.
            sheet = self.env[res_model].browse(res_id)
            if sheet.pdf_error:
                sheet.message_post(
                    body=self.env._(
                        "Failure when generating the PDF files."
                        "%(br)s%(errors)s",
                        br=Markup("<br/>"),
                        errors=sheet.pdf_error,
                    ),
                )

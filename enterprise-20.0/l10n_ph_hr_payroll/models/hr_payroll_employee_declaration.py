# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class HrPayrollEmployeeDeclaration(models.Model):
    _inherit = 'hr.payroll.employee.declaration'

    l10n_ph_sss_remarks = fields.Selection(
        selection=[
            ('N', 'N - Regular'),
            ('1', '1 - Newly Hired'),
            ('2', '2 - Terminated'),
            ('3', '3 - No Earnings'),
        ],
        string="Remarks",
        compute='_compute_l10n_ph_sss_remarks',
        store=True,
        readonly=False,
        help="Status reported to the SSS for this employee. It is set from the contract dates and the payslips of "
             "the period, but can be adjusted manually before generating the file.",
    )

    @api.depends('res_model', 'res_id', 'employee_id', 'version_id')
    def _compute_l10n_ph_sss_remarks(self):
        """ Default each SSS line's remark from the employee's contract dates and earnings; clear it on other reports. """
        self.l10n_ph_sss_remarks = False
        sss_declarations = self.filtered(lambda declaration: declaration.res_model == 'l10n_ph_hr_payroll.sss_contribution')
        for res_id, declarations in sss_declarations.grouped('res_id').items():
            sheet = self.env['l10n_ph_hr_payroll.sss_contribution'].browse(res_id).exists()
            if not sheet:
                continue
            amounts = sheet._l10n_ph_sss_get_amounts(declarations.employee_id)
            for declaration in declarations:
                declaration.l10n_ph_sss_remarks = sheet._l10n_ph_sss_get_remark(
                    declaration.employee_id,
                    amounts[declaration.employee_id]['earnings'],
                )

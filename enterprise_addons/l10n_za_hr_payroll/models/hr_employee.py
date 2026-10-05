# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    l10n_za_employee_medical_scheme_contribution = fields.Monetary(
        related="version_id.l10n_za_employee_medical_scheme_contribution",
        inherited=True,
        readonly=False,
        groups="hr_payroll.group_hr_payroll_user")
    l10n_za_employee_dependant_count = fields.Integer(
        related="version_id.l10n_za_employee_dependant_count",
        inherited=True,
        readonly=False,
        groups="hr_payroll.group_hr_payroll_user")
    l10n_za_dependant_medical_scheme_contribution = fields.Monetary(
        related="version_id.l10n_za_dependant_medical_scheme_contribution",
        inherited=True,
        readonly=False,
        groups="hr_payroll.group_hr_payroll_user")

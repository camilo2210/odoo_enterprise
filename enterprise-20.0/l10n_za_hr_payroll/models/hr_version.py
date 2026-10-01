# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrVersion(models.Model):
    _inherit = 'hr.version'

    l10n_za_employee_medical_scheme_contribution = fields.Monetary(
        string="Employee Medical Scheme Contribution",
        tracking=1,
        groups="hr_payroll.group_hr_payroll_user")
    l10n_za_employee_dependant_count = fields.Integer(
        string="Number of Dependants",
        tracking=1,
        groups="hr_payroll.group_hr_payroll_user")
    l10n_za_dependant_medical_scheme_contribution = fields.Monetary(
        string="Dependant Medical Scheme Contribution",
        tracking=1,
        groups="hr_payroll.group_hr_payroll_user")

    @api.model
    def _get_whitelist_fields_from_template(self):
        whitelisted_fields = super()._get_whitelist_fields_from_template()
        if self.env.company.country_id.code == 'ZA':
            whitelisted_fields += [
                "l10n_za_employee_medical_scheme_contribution",
                "l10n_za_employee_dependant_count",
                "l10n_za_dependant_medical_scheme_contribution",
            ]
        return whitelisted_fields

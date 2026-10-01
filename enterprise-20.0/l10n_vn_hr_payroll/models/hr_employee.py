# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    l10n_vn_pit_method = fields.Selection(readonly=False, related="version_id.l10n_vn_pit_method", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_vn_dependants = fields.Integer(readonly=False, related="version_id.l10n_vn_dependants", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_vn_minimum_wage_region = fields.Selection(readonly=False, related="version_id.l10n_vn_minimum_wage_region", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_vn_union_member = fields.Boolean(readonly=False, related="version_id.l10n_vn_union_member", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_vn_insurance_exempt = fields.Boolean(readonly=False, related="version_id.l10n_vn_insurance_exempt", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_vn_net_salary = fields.Boolean(readonly=False, related="version_id.l10n_vn_net_salary", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_vn_tax_code = fields.Char(readonly=False, related="version_id.l10n_vn_tax_code", inherited=True, groups="hr.group_hr_user")

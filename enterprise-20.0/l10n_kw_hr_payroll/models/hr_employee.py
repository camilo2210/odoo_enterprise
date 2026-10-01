# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    l10n_kw_annual_leave_eligibility = fields.Float(
        related='version_id.l10n_kw_annual_leave_eligibility',
        inherited=True,
        readonly=False,
        groups="hr_payroll.group_hr_payroll_user"
    )

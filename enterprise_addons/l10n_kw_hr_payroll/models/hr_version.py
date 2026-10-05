# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class HrVersion(models.Model):
    _inherit = 'hr.version'

    l10n_kw_annual_leave_eligibility = fields.Float(
        string="KW Leave Eligibility",
        default=30.0,
        digits=(16, 1),
        tracking=1,
        groups="hr_payroll.group_hr_payroll_user",
        help="The number of annual leave days an employee is entitled to for one year of service"
    )

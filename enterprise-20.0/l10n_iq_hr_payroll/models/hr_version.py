# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrVersion(models.Model):
    _inherit = 'hr.version'

    l10n_iq_annual_leave_provision_eligibility = fields.Float(default=21,
        string='IQ Annual Leave Eligibility', groups="hr_payroll.group_hr_payroll_user", tracking=1,
        help="Number of Annual leave days per year that the employee is eligible to, it is used to compute the monthly provision for the annual leave days")

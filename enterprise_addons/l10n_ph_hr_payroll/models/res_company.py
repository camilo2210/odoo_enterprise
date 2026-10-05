# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_ph_hr_payroll_sss_number = fields.Char(
        string='SS Number',
        help="The 10-digit Social Security System (SSS) employer number of the company.",
    )
    l10n_ph_hr_payroll_sss_branch_code = fields.Char(
        string='SS Branch Code',
        default='000',
        help="The SSS branch number of the company. It is zero padded to three digits in the SSS contribution file.",
    )

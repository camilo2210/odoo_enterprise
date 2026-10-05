# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class HrDepartureReason(models.Model):
    _inherit = "hr.departure.reason"

    l10n_ph_hr_payroll_terminal_pay_type = fields.Selection(
        selection=[
            ("retirement", "Retirement Pay"),
            ("severance_full", "Severance Pay (Full)"),
            ("severance_half", "Severance Pay (Half)"),
        ],
        help="Statutory terminal pay applied for this departure reason. Leave blank if no terminal benefits apply.",
    )
    l10n_ph_hr_payroll_bir_separation_code = fields.Selection(
        selection=[
            ('T', 'Termination (Employer-Initiated)'),
            ('R', 'Resignation (Voluntary)'),
            ('D', 'Death'),
            ('TR', 'Retirement'),
        ],
        help="Separation Reason as per the BIR categorization, for employee tax declarations.",
    )

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_mx_isr_calculation_method = fields.Selection(
        selection=[
            ("standard", "Period Table"),
            ("monthly_with_period_factor", "Monthly Table with Period Factor"),
        ],
        string="ISR Calculation Method",
        required=True,
        default="standard",
        help="Period Table: the ISR is computed on the taxable income with the tax table matching the pay period.\n"
             "Monthly Table with Period Factor: the taxable income is converted to its monthly equivalent, and the resulting tax is converted back to the pay period.")
    l10n_mx_isr_days_per_month = fields.Float(
        string="ISR Days per Month",
        default=30.4,
        help="Number of days in a month used to compute the period factor (365 / 12 by default).")

    @api.constrains('l10n_mx_isr_days_per_month')
    def _check_l10n_mx_isr_days_per_month(self):
        for company in self:
            if company.l10n_mx_isr_days_per_month <= 0:
                raise ValidationError(_("The ISR days per month must be strictly positive."))

from odoo import fields, models


class HrWorkLocation(models.Model):
    _inherit = "hr.work.location"

    # The value here is dependant of the province, some province even having different min wages.
    # Storing this on the office location make it easy to maintain and keep accurate.
    l10n_ph_hr_payroll_min_daily_wage = fields.Monetary(
        string="Statutory Minimum Wage (Daily)",
        help="The legal daily minimum wage for this specific location. Used for BIR 2316 MWE reporting and calculating the 25% tax-exempt ceiling for OT meal allowances.",
    )

# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ResourceCalendar(models.Model):
    _inherit = "resource.calendar"

    l10n_ph_hr_payroll_is_392_5 = fields.Boolean(
        string="Works Everyday (392.5 Factor)",
        help="Check this if employees on this calendar are required to work every day of the year, including Sundays/rest days, special non-working days, and regular holidays."
             "This legally applies the 392.5 days/year EEMR multiplier."
    )

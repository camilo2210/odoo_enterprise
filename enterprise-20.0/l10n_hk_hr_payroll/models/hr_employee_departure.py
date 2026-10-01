# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrEmployeeDeparture(models.Model):
    _inherit = 'hr.employee.departure'

    l10n_hk_leaving_hk = fields.Boolean(
        string="Leaving HK",
        help="Check this if the user will leave Hong Kong for more than a month, and should be reported in the IR56G.",
    )

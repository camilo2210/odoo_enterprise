# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrVersion(models.Model):
    _inherit = 'hr.version'

    l10n_lt_working_capacity = fields.Selection([
        ('0_25', '0–25%'),
        ('30_55', '30–55%'),
    ], string='Working Capacity',
        help="Disability working capacity level. Determines the tax-exempt amount for permanent residents with disabilities.")

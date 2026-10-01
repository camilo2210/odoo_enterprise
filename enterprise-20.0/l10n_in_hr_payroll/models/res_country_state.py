# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResCountryState(models.Model):
    _inherit = 'res.country.state'

    l10n_in_tds_numeric_code = fields.Integer("TDS Numeric State Code")

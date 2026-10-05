# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResCountry(models.Model):
    _inherit = 'res.country'

    l10n_be_nis_code = fields.Char('NIS Code', size=3)

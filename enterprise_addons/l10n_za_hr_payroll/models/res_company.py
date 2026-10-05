# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_za_eligible_for_sdl = fields.Boolean(string="Eligible for SDL", default=True)

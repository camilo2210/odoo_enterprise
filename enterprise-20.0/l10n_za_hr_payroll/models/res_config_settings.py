# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_za_eligible_for_sdl = fields.Boolean(
        related='company_id.l10n_za_eligible_for_sdl',
        readonly=False,
        string="Eligible for SDL")

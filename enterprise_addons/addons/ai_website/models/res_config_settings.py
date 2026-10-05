# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ai_allow_scripts = fields.Boolean(
        related='website_id.ai_allow_scripts',
        readonly=False,
    )

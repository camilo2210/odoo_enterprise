# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_urbanpiper_store_id = fields.Many2one(
        related='pos_config_id.urbanpiper_store_id',
        readonly=False,
        help="The Urbanpiper Store, which is used for online food delivery."
    )

    def action_open_urbanpiper_signup_form(self):
        """Open the UrbanPiper signup form in a new browser tab."""
        return {
            'type': 'ir.actions.act_url',
            'url': 'https://www.odoo.com/survey/start/f13956e4-0104-48a0-967e-e5b6ffedd45d',
            'target': 'new',
        }

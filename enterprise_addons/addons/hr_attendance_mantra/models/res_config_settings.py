# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    mantra_webhook_token = fields.Char(
        related="company_id.mantra_webhook_token",
        readonly=False,
    )
    mantra_webhook_url = fields.Char(
        related="company_id.mantra_webhook_url",
        readonly=True,
    )

    def action_regenerate_mantra_webhook_token(self):
        self.ensure_one()
        self.company_id.action_regenerate_mantra_webhook_token()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': self.env._('Success'),
                'message': self.env._('Mantra webhook token generated successfully.'),
                'type': 'success',
                'sticky': False,
            }
        }

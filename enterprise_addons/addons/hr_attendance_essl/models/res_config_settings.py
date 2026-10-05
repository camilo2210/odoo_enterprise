# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    essl_webhook_token = fields.Char(
        related="company_id.essl_webhook_token",
        readonly=False,
    )
    essl_webhook_url = fields.Char(
        related="company_id.essl_webhook_url",
        readonly=True,
    )

    def action_regenerate_essl_webhook_token(self):
        self.ensure_one()
        self.company_id.action_regenerate_essl_webhook_token()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': self.env._('Success'),
                'message': self.env._('ESSL webhook token generated successfully.'),
                'type': 'success',
                'sticky': False,
            }
        }

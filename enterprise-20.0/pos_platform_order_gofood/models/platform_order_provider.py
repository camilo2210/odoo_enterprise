# Part of Odoo. See LICENSE file for full copyright and licensing details.
import hashlib
import hmac

from odoo import _, fields, models


class PlatformOrderProvider(models.Model):
    _inherit = 'platform.order.provider'

    code = fields.Selection(
        selection_add=[('gofood', "GoFood")], ondelete={'gofood': 'set default'},
    )
    gofood_appid = fields.Char(
        string="GoFood App ID",
        help="The App ID for the GoFood account.",
        required_if_provider='gofood',
    )
    gofood_secret = fields.Char(
        string="GoFood Secret",
        help="The Secret key for accessing the GoFood services.",
        required_if_provider='gofood',
    )
    gofood_partner_id = fields.Char(
        string="GoFood Partner ID",
        help="The POS ID associated with GoFood.",
        required_if_provider='gofood',
    )
    gofood_relay_secret = fields.Char(
        string="GoFood Relay Secret",
        help="A security token used to verify that incoming webhooks (system notifications) are genuinely from GoFood.",
        required_if_provider='gofood',
    )

    def _gofood_calculate_signature(self, data):
        if not self.gofood_relay_secret:
            raise ValueError(_("GoFood Relay Secret is not set for this provider."))
        relay_secret = self.gofood_relay_secret.encode()
        return hmac.new(relay_secret, data, hashlib.sha256).hexdigest()

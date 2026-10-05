import logging as logger

from odoo import models
from odoo.addons.mail.tools.jwt import generate_vapid_keys

_logger = logger.getLogger(__name__)


class IrConfigParameter(models.Model):
    _inherit = 'ir.config_parameter'

    def _get_vapid_keys(self):
        """ Retrieves the server's public/private VAPID key pair. If the server
            does not already have one, the method automatically creates a new pair
            and discards the outdated push subscriptions. """
        vapid_public_key = self.get_str('social_push_notifications.vapid_public_key')
        vapid_private_key = self.get_str('social_push_notifications.vapid_private_key')
        if not vapid_public_key or not vapid_private_key:
            vapid_private_key, vapid_public_key = generate_vapid_keys()
            self.set_str('social_push_notifications.vapid_public_key', vapid_public_key)
            self.set_str('social_push_notifications.vapid_private_key', vapid_private_key)
            _logger.info('WebPush: missing public key, new VAPID keys generated.')
            self.env['website.visitor.push.subscription'].search([]).unlink()
        return vapid_public_key, vapid_private_key

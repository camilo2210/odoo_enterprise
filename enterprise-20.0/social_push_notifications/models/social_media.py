# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class SocialMedia(models.Model):
    _inherit = 'social.media'

    media_type = fields.Selection(selection_add=[('push_notifications', 'Push Notifications')])

    def _action_add_account(self):
        self.ensure_one()

        if self.media_type != 'push_notifications':
            return super()._action_add_account()

        return None

    def _get_utm_source(self):
        self.ensure_one()

        if self.media_type == 'push_notifications':
            return self.env['utm.mixin']._utm_ref('social_push_notifications.utm_source_push_notification')

        return super()._get_utm_source()

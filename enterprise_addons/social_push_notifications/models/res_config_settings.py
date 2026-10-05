# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    enable_push_notifications = fields.Boolean('Enable Web Push Notifications', readonly=False, related='website_id.enable_push_notifications')

    notification_request_title = fields.Char('Notification Request Title', readonly=False, related='website_id.notification_request_title')
    notification_request_body = fields.Text('Notification Request Text', readonly=False, related='website_id.notification_request_body')
    notification_request_delay = fields.Integer('Notification Request Delay (seconds)', readonly=False, related='website_id.notification_request_delay')
    notification_request_icon = fields.Binary("Notification Request Icon", readonly=False, related='website_id.notification_request_icon')

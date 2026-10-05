# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SocialAccount(models.Model):
    _inherit = 'social.account'

    website_id = fields.Many2one('website', string="Website", index='btree_not_null',
                                 help="This configuration will only be used for the specified website", ondelete='cascade')

    notification_request_title = fields.Char('Notification Request Title', related='website_id.notification_request_title')
    notification_request_body = fields.Text('Notification Request Text', related='website_id.notification_request_body')
    notification_request_delay = fields.Integer('Notification Request Delay (seconds)', related='website_id.notification_request_delay')
    notification_request_icon = fields.Binary("Notification Request Icon", related='website_id.notification_request_icon')

    _website_unique = models.Constraint(
        'unique(website_id)',
        "There is already a configuration for this website.",
    )

    @api.ondelete(at_uninstall=False)
    def _unlink_except_push_notification_account(self):
        if not self.env.user.has_group('base.group_system') and any(account.website_id for account in self):
            raise UserError(_("You can't delete a Push Notification account."))

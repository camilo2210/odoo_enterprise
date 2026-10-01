# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


from odoo import api, fields, models
from odoo.fields import Domain


class SocialPost(models.Model):
    _inherit = 'social.post'

    push_notifications_scheduled_date = fields.Datetime(
        string='Push Notifications Scheduled for',
        compute='_compute_scheduled_date_by_media',
        store=True, readonly=False, copy=False)

    @api.model
    def _scheduled_date_fields(self):
        return {**super()._scheduled_date_fields(), 'push_notifications': 'push_notifications_scheduled_date'}

    def _action_post(self):
        """ We also setup a CRON trigger at "now" to run the job as soon as possible to get the
        minimum amount of delay for the end user as push notifications are only sent when the CRON
        job runs (see social_push_notifications/social_live_post.py#_post). """

        super()._action_post()

        if 'push_notifications' in self.account_ids.mapped('media_type') and not all(self.mapped('push_notifications_scheduled_date')):
            # trigger CRON job ASAP so that push notifications are sent
            cron = self.env.ref('social.ir_cron_post_scheduled')
            cron._trigger()

    @api.model
    def _cron_publish_scheduled(self):
        """ This method is overridden to gather all pending push live.posts ('ready' state) and post them.
        This is done in the cron job instead of instantly to avoid blocking the 'Post' action of the user
        indefinitely.

        The related social.post will remain 'pending' until all live.posts are processed. """
        super()._cron_publish_scheduled()

        domain = Domain([
            ('state', 'in', ['ready', 'posting']),
            ('account_id.media_id.media_type', '=', 'push_notifications'),
        ]) & (
            Domain('post_id.push_notifications_scheduled_date', '=', False)
            | Domain('post_id.push_notifications_scheduled_date', '<=', fields.Datetime.now())
        )
        live_posts = self.env['social.live.post'].search(domain)
        live_posts.write({'state': 'posting'})
        live_posts._post_push_notifications()

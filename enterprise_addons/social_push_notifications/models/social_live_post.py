# Part of Odoo. See LICENSE file for full copyright and licensing details.

import ast
import json
import requests

from odoo import models, fields, _
from odoo.fields import Domain

from odoo.addons.mail.tools.web_push import push_to_end_point


class SocialLivePost(models.Model):
    _inherit = 'social.live.post'

    last_push_subscription_id = fields.Integer(default=0)

    # UI fields
    push_notification_title = fields.Char(related='post_id.push_notification_title')
    push_notification_target_url = fields.Char(related='post_id.push_notification_target_url')
    push_notification_image = fields.Binary(related='post_id.push_notification_image')

    def _post(self):
        """ The _post method of push notifications, unlike other social.media, doesn't post messages directly
        Instead, we keep them 'ready' and they are gathered by a cron job (see 'social.post#_cron_publish_scheduled'). """

        push_notifications_live_posts = self._filter_by_media_types(['push_notifications'])
        super(SocialLivePost, (self - push_notifications_live_posts))._post()

        push_notifications_live_posts.write({
            'state': 'ready'
        })

    def _post_push_notifications(self):
        if not self:
            return

        # Ignore live posts that are **not** linked to a website with push notifications enabled:
        live_posts_to_ignore = self.filtered(lambda live_post:
               not live_post.account_id.website_id
            or not live_post.account_id.website_id.enable_push_notifications)
        live_posts_to_ignore.write({'state': 'posted'})
        live_posts_to_process = self - live_posts_to_ignore
        live_posts_to_process = live_posts_to_process.filtered(lambda p: p.state == 'posting')

        if not self.env['ir.cron']._commit_progress(0, remaining=len(live_posts_to_process)):
            return
        if not live_posts_to_process:
            return

        IrConfigParameter = self.env['ir.config_parameter']
        vapid_public_key, vapid_private_key = IrConfigParameter._get_vapid_keys()
        batch_size = IrConfigParameter.get_int('social_push_notifications.batch_size', 100)
        assert batch_size > 0

        session = requests.Session()
        for live_post in live_posts_to_process:
            live_post = live_post.try_lock_for_update(allow_referencing=True)
            if not live_post or live_post.state != 'posting':
                continue

            while True:
                push_subscriptions = self.env['website.visitor.push.subscription'].search([
                    ('id', '>', live_post.last_push_subscription_id),
                    ('website_visitor_id', 'any', (
                        Domain(ast.literal_eval(live_post.post_id.visitor_domain))
                        & Domain('website_id', '=', live_post.account_id.website_id.id))),
                ], limit=batch_size, order='id')

                for push_subscription in push_subscriptions:
                    try:
                        push_to_end_point(
                            base_url=live_post.get_base_url(),
                            device={
                                'endpoint': push_subscription.endpoint,
                                'keys': push_subscription.keys
                            },
                            payload=json.dumps(live_post._prepare_push_notification_payload()),
                            vapid_private_key=vapid_private_key,
                            vapid_public_key=vapid_public_key,
                            session=session)
                    except Exception:  # noqa: BLE001
                        push_subscription.unlink()
                        self.env.cr.commit()
                        continue
                    live_post.write({
                        'last_push_subscription_id': push_subscription.id
                    })
                    self.env.cr.commit()

                if len(push_subscriptions) < batch_size:
                    live_post.write({'state': 'posted'})
                    break
                if not self.env['ir.cron']._commit_progress(0):
                    return
            if not self.env['ir.cron']._commit_progress(1):
                return

    def _prepare_push_notification_payload(self):
        self.ensure_one()
        payload = {
            'icon': f'/social_push_notifications/social_post/{self.post_id.id}/push_notification_image'
                if self.post_id.push_notification_image else '/mail/static/src/img/odoobot_transparent.webp',
            'title': self.post_id.push_notification_title or _('New Message'),
            'body': self.message
        }
        if self.post_id.push_notification_target_url:
            link_tracker_values = self._get_utm_values()
            link_tracker_values['url'] = self.post_id.push_notification_target_url
            link_tracker = self.env['link.tracker'].search_or_create([link_tracker_values])
            payload['target_url'] = link_tracker.short_url
        return payload

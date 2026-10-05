# Part of Odoo. See LICENSE file for full copyright and licensing details.

import contextlib
import datetime
import json
import logging
import requests
import traceback

from dateutil.relativedelta import relativedelta
from odoo import _, api, models, fields
from odoo.addons.social_facebook.utils import meta_run_request_batch
from odoo.tools.urls import urljoin as url_join


_logger = logging.getLogger(__name__)


class SocialLivePost(models.Model):
    _inherit = 'social.live.post'

    instagram_post_id = fields.Char('Instagram Post ID', readonly=True)
    instagram_post_as_story = fields.Boolean('Instagram Post Story', related="post_id.instagram_post_as_story")
    instagram_is_story_expired = fields.Boolean(
        "Instagram Story Expired",
        compute="_compute_instagram_is_story_expired")

    @api.depends('state', 'media_type', 'post_id.instagram_post_as_story', 'post_id.published_date')
    def _compute_instagram_is_story_expired(self):
        for post in self:
            post.instagram_is_story_expired = (
                post.media_type == 'instagram'
                and post.state == 'posted'
                and post.post_id.instagram_post_as_story
                and post.post_id.published_date
                and post.post_id.published_date < fields.Datetime.now() - datetime.timedelta(hours=24)
            )

    @api.depends('state', 'account_id.social_account_handle', 'post_id.instagram_post_as_story', 'instagram_is_story_expired')
    def _compute_live_post_link(self):
        instagram_live_posts = self._filter_by_media_types(['instagram']).filtered(lambda post: post.state == 'posted')
        super(SocialLivePost, (self - instagram_live_posts))._compute_live_post_link()

        for post in instagram_live_posts:
            if not post.post_id.instagram_post_as_story:
                post.live_post_link = f'https://www.instagram.com/{post.account_id.social_account_handle}'
            elif not post.instagram_is_story_expired:
                post.live_post_link = f"https://www.instagram.com/stories/{post.account_id.social_account_handle}"
            else:
                post.live_post_link = False

    @api.depends('post_id.instagram_post_as_story')
    def _compute_has_metrics(self):
        super()._compute_has_metrics()
        instagram_live_posts = self._filter_by_media_types(['instagram']).filtered(
            lambda post: not post.post_id.instagram_post_as_story)
        instagram_live_posts.has_likes = True
        instagram_live_posts.has_comments = True

    def _refresh_statistics(self):
        super()._refresh_statistics()
        accounts = self.env['social.account'].search([('media_type', '=', 'instagram')])

        responses = meta_run_request_batch(self.env, [{
            'url': f'{account.instagram_account_id}/media',
            'params': {
                'access_token': account._get_instagram_access_token(),
                'fields': 'id,comments_count,like_count',
            },
        } for account in accounts])

        for account, response in zip(accounts, responses, strict=True):
            if not response or 'data' not in response:
                self.account_id._action_disconnect_accounts()
                return False

            instagram_post_ids = [post.get('id') for post in response['data']]
            existing_live_posts = self.env['social.live.post'].sudo().search([
                ('instagram_post_id', 'in', instagram_post_ids)
            ])

            existing_live_posts_by_instagram_post_id = {
                live_post.instagram_post_id: live_post for live_post in existing_live_posts
            }

            for post in response['data']:
                existing_live_post = existing_live_posts_by_instagram_post_id.get(post.get('id'))
                if existing_live_post:
                    existing_live_post.write({
                        'likes_count': post.get('like_count', 0),
                        'comments_count': post.get('comments_count', 0),
                    })

    def _post(self):
        instagram_live_posts = self._filter_by_media_types(['instagram'])
        super(SocialLivePost, (self - instagram_live_posts))._post()

        for live_post in instagram_live_posts:
            live_post._post_instagram()

    def _post_instagram(self):
        self.ensure_one()
        try:
            self._post_instagram_request()
        except requests.exceptions.Timeout as e:
            _logger.error("Social Instagram: timeout while posting %s - %s", e, traceback.format_exc())
            self.write({
                'state': 'failed',
                'failure_reason': self.env._(
                    "Instagram took too long to process the request. "
                    "This can happen with large images, try posting a smaller one."
                ),
            })
        except requests.exceptions.RequestException as e:
            _logger.error("Social Instagram: error while posting %s - %s", e, traceback.format_exc())
            self.write({
                'state': 'failed',
                'failure_reason': self.env._("An error occurred while contacting the Instagram API, please try again."),
            })

    def _post_instagram_request(self):
        """
        Handles the process of posting images to Instagram, supporting both single and multiple (carousel) posts.

        Steps for Posting Image(s):
        1. Create Media Container(s):
            - Upload image(s) and associated data using an initial HTTP request to create media container(s).

        2. Create Carousel Container (if multiple images):
            - For carousel posts, group the individual media containers into a single carousel container using an additional HTTP request.

        3. Publish the Container:
            - Mark the media or carousel container as published using the ID returned from the previous request(s).

        This process is asynchronous: if a container is not immediately 'FINISHED', we store
        the pending ID(s) and retry via cron.

        More information & examples:
        - https://developers.facebook.com/docs/instagram-api/reference/ig-user/media
        - https://developers.facebook.com/docs/instagram-api/reference/ig-user/media_publish
        """

        self.ensure_one()
        account = self.account_id
        post = self.post_id

        base_url = self.get_base_url()
        endpoint = self.env['social.media']._INSTAGRAM_ENDPOINT
        media_url = url_join(endpoint, f"/{account.instagram_account_id}/media")
        media_publish_url = url_join(endpoint, f"/{account.instagram_account_id}/media_publish")

        session = requests.Session()
        container_id = False

        if self.instagram_post_id and self.instagram_post_id.startswith('containerID-'):
            container_id = self.instagram_post_id.split('containerID-', 1)[1]

        if not container_id:
            media_container_ids = []
            # Step 1: Create Media Container(s)
            for image in self.image_ids:
                data = {
                    'access_token': account._get_instagram_access_token(),
                    'image_url': url_join(
                        base_url,
                        f'/social_instagram/{post.instagram_access_token}/get_image/{image.id}'
                    )
                }

                if post.instagram_post_as_story:
                    data['media_type'] = 'STORIES'
                elif len(self.image_ids) == 1:
                    data['caption'] = self.message
                else:
                    data['is_carousel_item'] = True

                media_response = session.post(media_url, data, timeout=15)
                if not media_response.ok or not media_response.json().get('id'):
                    self._instagram_log_error(media_response)
                    return

                media_container_ids.append(media_response.json().get('id'))

            if len(media_container_ids) > 1:
                # Step 2: Create Carousel Container
                media_response = session.post(
                    media_url,
                    json={
                        'caption': self.message,
                        'access_token': account._get_instagram_access_token(),
                        'media_type': 'CAROUSEL',
                        'children': media_container_ids
                    },
                    timeout=15,
                )
                if not media_response.ok or not media_response.json().get('id'):
                    self._instagram_log_error(media_response)
                    return
                container_id = media_response.json()['id']
            else:
                container_id = media_container_ids[0]

        # Check status of the final container (single or carousel)
        status_response = session.get(f"{endpoint}/{container_id}", params={
            'access_token': account._get_instagram_access_token(),
            'fields': 'status_code'
        }, timeout=15)

        if not status_response.ok:
            self._instagram_log_error(status_response)
            return

        status_data = status_response.json()
        status_code = status_data.get('status_code')

        if status_code == 'ERROR':
            self.write({
                'state': 'failed',
                'failure_reason': self.env._("The media container failed to process.")
            })
            return
        elif status_code == 'EXPIRED':
            self.write({
                'state': 'failed',
                'failure_reason': self.env._("The media container expired.")
            })
            return
        elif status_code == 'PUBLISHED':
            status_response = session.get(f"{endpoint}/{container_id}", params={
                'access_token': account._get_instagram_access_token(),
                'fields': 'ig_id'
            }, timeout=15)
            status_data = status_response.json()
            self.write({
                'state': 'posted',
                'failure_reason': False,
                'instagram_post_id': status_data.get('ig_id') or status_data.get('id')
            })
            return
        elif status_code != 'FINISHED':
            self.write({
                'state': 'posting',
                'instagram_post_id': f'containerID-{container_id}'
            })
            cron = self.env.ref('social.ir_cron_post_scheduled')
            cron._trigger(at=fields.Datetime.now() + relativedelta(minutes=1))
            return

        # Step 3: Publish the Container
        publish_response = session.post(
            media_publish_url,
            data={
                'access_token': account._get_instagram_access_token(),
                'creation_id': container_id,
            },
            timeout=15,
        )

        if not publish_response.ok or not publish_response.json().get('id'):
            self._instagram_log_error(publish_response)
            return

        self.write({
            'state': 'posted',
            'failure_reason': False,
            'instagram_post_id': publish_response.json()['id']
        })

        if self.post_id.instagram_first_comment:
            comment = self.env['mail.render.mixin'].sudo()._shorten_links_text(
                self.post_id.instagram_first_comment,
                self._get_utm_values()
            )
            with contextlib.suppress(Exception):
                self.env['social.stream.post']._instagram_comment_add(
                    self.account_id,
                    comment,
                    self.instagram_post_id,
                )

    def _instagram_log_error(self, response):
        """Parse the Instagram response and log the appropriate error."""
        self.ensure_one()
        error = json.loads(response.text or '{}').get('error', {})
        error_message = error.get('message', '')
        if error.get('code') == 9004:
            error_message = "\n".join((
                _("Your media didn't go through. This is usually caused by one of the following:"),
                _("- Check your file: Ensure it isn't corrupted and is from 320 to 1440 pixels wide, 8MB maximum, aspect ratio between 4:5 and 1.91:1."),
                _("- Check your connection: Your server may be offline or temporarily unreachable."),
                _("- Check permissions: Your site's robots.txt might be blocking Instagram from accessing the media folder (make sure /social_instagram is not blocked)."),
            ))

        self.write({
            'state': 'failed',
            'failure_reason': error_message,
        })

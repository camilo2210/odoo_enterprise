# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import contextlib
import datetime
import json
import re
import requests

from odoo import api, models, fields, _
from odoo.addons.social_facebook.utils import meta_run_request_batch
from odoo.exceptions import UserError
from werkzeug.urls import url_join


class SocialLivePost(models.Model):
    _inherit = 'social.live.post'

    facebook_post_id = fields.Char('Actual Facebook ID of the post')
    facebook_post_as_story = fields.Boolean('Facebook Post Story', related="post_id.facebook_post_as_story")
    facebook_story_url = fields.Char('Facebook Story URL')
    facebook_is_story_expired = fields.Boolean(
        "Facebook Story Expired",
        compute="_compute_facebook_is_story_expired")

    @api.depends('state', 'media_type', 'post_id.facebook_post_as_story', 'post_id.published_date')
    def _compute_facebook_is_story_expired(self):
        for post in self:
            post.facebook_is_story_expired = (
                post.media_type == 'facebook'
                and post.state == 'posted'
                and post.post_id.facebook_post_as_story
                and post.post_id.published_date
                and post.post_id.published_date < fields.Datetime.now() - datetime.timedelta(hours=24)
            )

    @api.depends('state', 'facebook_story_url', 'post_id.facebook_post_as_story',
        'facebook_is_story_expired', 'facebook_post_id')
    def _compute_live_post_link(self):
        facebook_live_posts = self._filter_by_media_types(["facebook"]).filtered(lambda post: post.state == 'posted')
        super(SocialLivePost, self - facebook_live_posts)._compute_live_post_link()

        for post in facebook_live_posts:
            if not post.post_id.facebook_post_as_story:
                post.live_post_link = f"http://facebook.com/{post.facebook_post_id}"
            elif not post.facebook_is_story_expired:
                post.live_post_link = post.facebook_story_url
            else:
                post.live_post_link = False

    @api.depends('post_id.facebook_post_as_story')
    def _compute_has_metrics(self):
        super()._compute_has_metrics()
        facebook_live_posts = self._filter_by_media_types(['facebook']).filtered(
            lambda post: not post.post_id.facebook_post_as_story)
        facebook_live_posts.has_likes = True
        facebook_live_posts.has_comments = True
        facebook_live_posts.has_shares = True

    def _refresh_statistics(self):
        super()._refresh_statistics()
        accounts = self.env['social.account'].search([('media_type', '=', 'facebook')])

        queries = [{
            'url': f"/{account.facebook_account_id}/published_posts",
            'params': {
                'access_token': account._get_facebook_access_token(),
                'fields': 'id,shares,likes.limit(1).summary(true),comments.summary(true)'
            },
        } for account in accounts]

        responses = iter(meta_run_request_batch(self.env, queries))

        for account, response in zip(accounts, responses):
            result_posts = response and response.get('data')
            if not result_posts:
                account._action_disconnect_accounts()
                return

            facebook_post_ids = [post.get('id') for post in result_posts]
            existing_live_posts = self.env['social.live.post'].sudo().search([
                ('facebook_post_id', 'in', facebook_post_ids)
            ])

            existing_live_posts_by_facebook_post_id = {
                live_post.facebook_post_id: live_post for live_post in existing_live_posts
            }

            for post in result_posts:
                existing_live_post = existing_live_posts_by_facebook_post_id.get(post.get('id'))
                if existing_live_post:
                    likes_count = post.get('likes', {}).get('summary', {}).get('total_count', 0)
                    shares_count = post.get('shares', {}).get('count', 0)
                    comments_count = post.get('comments', {}).get('summary', {}).get('total_count', 0)
                    existing_live_post.write({
                        'likes_count': likes_count,
                        'comments_count': comments_count,
                        'shares_count': shares_count,
                    })

    def _post(self):
        facebook_live_posts = self._filter_by_media_types(['facebook'])
        super(SocialLivePost, (self - facebook_live_posts))._post()

        for live_post in facebook_live_posts:
            live_post._post_facebook(live_post.account_id.facebook_account_id)

    def _post_facebook(self, facebook_target_id):
        self.ensure_one()
        account = self.account_id
        post_endpoint_url = url_join(self.env['social.media']._FACEBOOK_ENDPOINT_VERSIONED, "%s/feed" % facebook_target_id)

        post = self.post_id

        params = {
            'message': self._format_facebook_mentions(self.message),
            'access_token': account._get_facebook_access_token()
        }

        if post.facebook_post_as_story:
            # Post as story
            photo_id = post._format_images_facebook(account.facebook_account_id, account._get_facebook_access_token())[0]['media_fbid']
            result = requests.post(
                url_join(
                    self.env['social.media']._FACEBOOK_ENDPOINT_VERSIONED,
                    f'{account.facebook_account_id}/photo_stories',
                ),
                data={"photo_id": photo_id, 'access_token': account._get_facebook_access_token()},
                timeout=15,
            )

        elif self.image_ids and len(self.image_ids) == 1:
            # if you have only 1 image, you have to use another endpoint with different parameters...
            image = self.image_ids[0]
            if image.mimetype == 'image/gif':
                # gifs are posted on the '/videos' endpoint, with a different base url
                endpoint_url = url_join(
                    "https://graph-video.facebook.com",
                    f'/v17.0/{facebook_target_id}/videos'
                )
                params['description'] = params['message']
            else:
                # a single regular image is posted on the '/photos' endpoint
                endpoint_url = url_join(
                    self.env['social.media']._FACEBOOK_ENDPOINT_VERSIONED,
                    f'{facebook_target_id}/photos'
                )
                params['caption'] = params['message']

            result = requests.request('POST', endpoint_url, params=params, timeout=15,
                files={'source': (image.name, image.raw, image.mimetype)})
            if not result.ok:
                generic_api_error = json.loads(result.text or '{}').get('error', {}).get('message', '')
                self.write({
                    'state': 'failed',
                    'failure_reason': _("We could not upload your image, try reducing its size and posting it again (error: %s).", generic_api_error)
                })
                return
        else:
            if self.image_ids:
                try:
                    images_attachments = post._format_images_facebook(account.facebook_account_id, account._get_facebook_access_token())
                except UserError as e:
                    self.write({
                        'state': 'failed',
                        'failure_reason': str(e)
                    })
                    return
                images_attachments = post._format_images_facebook(facebook_target_id, account._get_facebook_access_token())
                if images_attachments:
                    params.update({
                        f'attached_media[{index}]': json.dumps(attachment)
                        for index, attachment in enumerate(images_attachments)
                    })

            link_url = self.env['social.post']._extract_url_from_message(self.message)
            # can't combine with images
            if link_url and not self.image_ids:
                params.update({'link': link_url})

            result = requests.post(post_endpoint_url, data=params, timeout=15)

        if result.ok:
            result_json = result.json()

            # when posting an image, the id of the related post is in 'post_id'
            # otherwise, we use the 'id' key that matches the post id we retrieve in stream.posts
            self.facebook_post_id = result_json.get('post_id', result_json.get('id', False))
            values = {
                'state': 'posted',
                'failure_reason': False
            }

            if self.post_id.facebook_first_comment and not self.post_id.facebook_post_as_story:
                comment = self.env['mail.render.mixin'].sudo()._shorten_links_text(
                    self.post_id.facebook_first_comment,
                    self._get_utm_values()
                )
                endpoint = url_join(self.env['social.media']._FACEBOOK_ENDPOINT_VERSIONED, f"{self.facebook_post_id}/comments")
                with contextlib.suppress(Exception):
                    self.env['social.stream.post']._facebook_comment_post(
                        self.account_id,
                        endpoint,
                        comment,
                    )

            if post.facebook_post_as_story:
                # Get the URL of the story
                endpoint_url = url_join(
                    self.env['social.media']._FACEBOOK_ENDPOINT_VERSIONED,
                    f'{self.account_id.facebook_account_id}/stories'
                )
                result = requests.get(
                    endpoint_url,
                    params={'access_token': account._get_facebook_access_token()},
                    timeout=15,
                )
                if result.ok:
                    self.facebook_story_url = next((
                        p['url'] for p in result.json().get('data', ())
                        if p['post_id'] == self.facebook_post_id
                    ), False)

        else:
            values = {
                'state': 'failed',
                'failure_reason': json.loads(result.text or '{}').get('error', {}).get('message', '') or result.text
            }
        self.write(values)

    def _format_facebook_mentions(self, input_string, add_name=False):
        """
        Formats an input string to replace mentions to correct Facebook Mentions.
        See: https://developers.facebook.com/docs/pages-api/comments-mentions#-mention-or-tag
        """
        mention_items = json.loads(self.post_id.social_post_mentions or '{}').get('facebook', {}).items()
        tags = []
        for mention, values in mention_items:
            match = re.search(f'@{re.escape(mention)}', input_string)
            tags.append({
                'id': values['id'], 'name': values['name'] if add_name else '',
                'offset': match.start(), 'length': match.end() - match.start()
            })

        return self.env['social.stream']._format_facebook_message(input_string, tags)

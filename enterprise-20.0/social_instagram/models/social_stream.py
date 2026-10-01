# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import dateutil.parser
import requests

from odoo import Command, models
from odoo.addons.social_facebook.utils import meta_run_request_batch
from odoo.tools.urls import urljoin as url_join


class SocialStream(models.Model):
    _inherit = 'social.stream'

    def _apply_default_name(self):
        instagram_streams = self.filtered(lambda s: s.media_id.media_type == 'instagram')
        super(SocialStream, (self - instagram_streams))._apply_default_name()

        for stream in instagram_streams:
            stream.write({'name': '%s: %s' % (stream.stream_type_id.name, stream.account_id.name)})

    def _fetch_instagram_posts(self):
        self.ensure_one()

        posts_endpoint = url_join(
            self.env['social.media']._INSTAGRAM_ENDPOINT,
            '%s/media' % self.account_id.instagram_account_id)
        response = requests.get(posts_endpoint,
            params={
                'access_token': self.account_id._get_instagram_access_token(),
                'fields': 'id,comments_count,is_comment_enabled,like_count,username,permalink,timestamp,caption,media_type,media_url,thumbnail_url,children.fields(media_type,media_url,thumbnail_url)'
            },
            timeout=5
        ).json()

        if 'data' not in response:
            self.account_id._action_disconnect_accounts(response)
            return False

        posts_to_create = []

        existing_posts = {
            post.instagram_post_id: post
            for post in self.env['social.stream.post'].search([
                ('stream_id', '=', self.id)])}

        # The post query only returns basic statistic (like comment and like count)
        # to get the number of "views" and "saved" we have to request a different
        # endpoint.
        posts_statistics = meta_run_request_batch(self.env, [{
            'url': f'{post["id"]}/insights',
            'params': {
                'access_token': self.account_id._get_instagram_access_token(),
                'metric': 'saved,views',
                'period': 'lifetime',
            },
        } for post in response['data']])

        for post, post_statistics in zip(response['data'], posts_statistics, strict=True):
            post_statistics = {
                stat.get('name'): stat.get('values', [{}])[0].get('value')
                for stat in post_statistics.get('data', [])
            } if post_statistics else {}
            values = {
                'author_name': post.get('username'),
                'instagram_comments_disabled': not post.get('is_comment_enabled', True),
                'instagram_comments_count': post.get('comments_count', 0),
                'instagram_facebook_author_id': self.account_id.instagram_facebook_account_id,
                'instagram_likes_count': post.get('like_count', 0),
                'instagram_saved_count': post_statistics.get('saved', 0),
                'instagram_views_count': post_statistics.get('views', 0),
                'instagram_post_id': post.get('id'),
                'instagram_post_link': post.get('permalink'),
                'message': post.get('caption'),
                'published_date': dateutil.parser.parse(post.get('timestamp'), ignoretz=True),
                'stream_id': self.id,
            }

            media_data = (
                post.get('children', {}).get('data', [])
                if post.get('media_type') == 'CAROUSEL_ALBUM'
                else [post]
            )

            media_urls = [
                {
                    'content_url': self._enforce_url_scheme(media['media_url']),
                    'attachment_content_type': 'image' if media.get('media_type') == 'IMAGE' else 'video',
                    'thumbnail_url': self._enforce_url_scheme(media.get('thumbnail_url', False)) if media.get('media_type') == 'VIDEO' else False,
                }
                for media in media_data if media.get('media_url')
            ]

            if values['instagram_post_id'] in existing_posts:
                values['stream_post_attachment_ids'] = [Command.clear()] + [Command.create(url) for url in media_urls]
                existing_posts[values['instagram_post_id']].sudo().write(values)
            else:
                values['stream_post_attachment_ids'] = [Command.create(url) for url in media_urls]
                posts_to_create.append(values)

        if posts_to_create:
            self.env['social.stream.post'].sudo().create(posts_to_create)

        return bool(posts_to_create)

    def _fetch_stream_data(self):
        if self.media_id.media_type != 'instagram':
            return super()._fetch_stream_data()

        if self.stream_type_id.stream_type == 'instagram_posts':
            return self._fetch_instagram_posts()

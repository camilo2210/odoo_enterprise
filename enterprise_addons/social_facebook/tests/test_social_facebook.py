# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import requests
from unittest.mock import patch

from freezegun import freeze_time

from odoo.addons.social.tests.tools import mock_void_external_calls
from odoo.addons.social_facebook.models.social_post import SocialPost
from odoo.addons.social_facebook.tests.common import SocialFacebookCommon
from odoo.tests import tagged


@tagged('at_install', '-post_install')  # LEGACY at_install
class SocialFacebookCase(SocialFacebookCommon):
    def test_post_success(self):
        self._test_post()

    def test_post_failure(self):
        self._test_post(False)

    def _test_post(self, success=True):
        self.assertEqual(self.social_post.state, 'draft')

        def _patched_post(*args, **kwargs):
            response = requests.Response()
            if success:
                response._content = json.dumps({'id': 42}).encode('utf-8')
                response.status_code = 200
            else:
                response.status_code = 404
            return response

        with patch.object(SocialPost, '_format_images_facebook', lambda *args, **kwargs: {'media_fbid': 1}), \
             patch.object(requests, 'post', _patched_post):
                self.social_post._action_post()

        self._checkPostedStatus(success)

    @classmethod
    def _get_social_media(cls):
        return cls.env.ref('social_facebook.social_media_facebook')

    @mock_void_external_calls()
    def test_format_facebook_message(self):
        social_stream = self.env['social.stream'].create({
            'media_id': self.social_account.media_id.id,
            'account_id': self.social_account.id,
            'stream_type_id': self.env.ref('social_facebook.stream_type_page_posts').id,

        })

        message = "Hi, Social is so cool :) Thanks Odoo"
        tags = [{
            'id': 1337,
            'name': 'Odoo - Social',
            'offset': 32,
            'length': 4
        }]
        excepted_message = "Hi, Social is so cool :) Thanks @[1337] Odoo-Social"
        self.assertEqual(
            social_stream._format_facebook_message(message, tags),
            excepted_message)

        message = "Hi, Social is so cool :) Thanks Odoo @[45] thisisafaketag Tag another@[45] faketag"
        tags = [
            {
                'id': 1337,
                'name': 'Odoo - Social',
                'offset': 32,
                'length': 4
            }, {
                'id': 1338,
                'name': 'Odoo Mate and - Social',
                'offset': 58,
                'length': 3
            }]
        excepted_message = "Hi, Social is so cool :) Thanks @[1337] Odoo-Social @ [45] thisisafaketag @[1338] Odoo-Mate-and-Social another@[45] faketag"
        self.assertEqual(
            social_stream._format_facebook_message(message, tags),
            excepted_message)

    def test_format_facebook_mentions(self):
        social_post = self.social_post
        social_post.social_post_mentions = json.dumps({
            "facebook": {
                "[123456]": {
                    "id": "123456",
                    "name": "Random Account #1",
                    "description": "This is a random description"
                },
                "[654321]": {
                    "id": "654321",
                    "name": "Random Page #2",
                    "description": "This is another descriptive description",
                }
            }
        })
        live_post = self.env["social.live.post"].create({
            "post_id": social_post.id,
            "account_id": self.social_account.id
        })
        message = "Hello Facebook, do you mind mentioning @[123456] and @[654321] for me?"

        expected_message = "Hello Facebook, do you mind mentioning @[123456] Random-Account-#1 and @[654321] Random-Page-#2 for me?"
        self.assertEqual(live_post._format_facebook_mentions(message, add_name=True), expected_message)

    def test_format_facebook_post_date(self):
        """ Facebook has its own format to return date values.
        Let's make sure those are correctly formatted. """

        formatted_value = self.env['social.stream.post']._format_facebook_published_date({
            'created_time': "2000-07-07T09:12:30+0000"
        })
        self.assertEqual(formatted_value, '07/07/2000')

        with freeze_time('2000-07-07 09:16:30'):
            formatted_value = self.env['social.stream.post']._format_facebook_published_date({
                'created_time': "2000-07-07T09:12:30+0000"
            })
            self.assertEqual(formatted_value, '4 minutes')

    @freeze_time('2000-07-07 09:16:30')
    def test_compute_statistics(self):
        accounts = self.env['social.account'].search([('media_type', '=', 'facebook')])
        self.assertEqual(len(accounts), 2)

        accounts[0].write({
            'facebook_account_id': '1337',
            'facebook_access_token': '97',
            'audience': 500,
            'engagement': 10,
        })

        accounts[1].write({
            'facebook_account_id': '1338',
            'facebook_access_token': '98',
            'audience': 200,
            'engagement': 50,
        })

        def get_test_response(url, params, *args, **kwargs):
            data = []

            if params.get('access_token') == '97':
                if 'fan_count' in params.get('fields', ''):
                    return {'fan_count': '1001'}

                # One of two should be set, but not both at the same time
                self.assertTrue(bool(params.get('date_preset')) ^ bool(params.get('since')))

                if params.get('date_preset') == 'last_30d':
                    data = [{
                        'name': 'page_post_engagements',
                        'values': [{'value': 1}, {'value': 2}, {'value': 3}],
                    }, {
                        'name': 'page_follows',
                        'values': [
                            {'value': 1, 'end_time': '2025-08-20'},
                            {'value': 2, 'end_time': '2025-08-21'},
                            {'value': 13, 'end_time': '2025-08-22'},
                        ],
                    }]

                # Each timestamp represents the start of the "90 blocks"
                # >>> 931857390: 13 Jul 1999
                # >>> 955185390: 8 Apr 2000
                elif params.get('since') in (955185390, 947409390):
                    data = [{
                        'name': 'page_post_engagements',
                        'values': [{'value': 3}],
                    }, {
                        'name': 'page_follows',
                        'values': [
                            {'value': 13, 'end_time': '2025-08-23'},
                            {'value': 14, 'end_time': '2025-08-24'},
                        ],
                    }]

                elif params.get('since') == 939633390:
                    data = [{
                        'name': 'page_post_engagements',
                        'values': [{'value': 7}],
                    }, {
                        'name': 'page_follows',
                        'values': [
                            {'value': 14, 'end_time': '2025-08-25'},
                            {'value': 15, 'end_time': '2025-08-26'},
                        ],
                    }]

                elif params.get('since') == 931857390:
                    data = [{
                        'name': 'page_post_engagements',
                        'values': [{'value': 4}],
                    }, {
                        'name': 'page_follows',
                        'values': [
                            {'value': 16, 'end_time': '2025-08-27'},
                            {'value': 17, 'end_time': '2025-08-28'},
                        ],
                    }]

            elif params.get('access_token') == '98':
                if 'fan_count' in params.get('fields', ''):
                    return {'fan_count': '120'}

                if params.get('date_preset') == 'last_30d':
                    data = [{
                        'name': 'page_post_engagements',
                        'values': [{'value': 7}, {'value': 1}],
                    }, {
                        'name': 'page_follows',
                        'values': [
                            {'value': 22, 'end_time': '2025-08-23'},
                            {'value': 8, 'end_time': '2025-08-24'},
                        ],
                    }]

                elif params.get('since') == 955185390:
                    data = [{
                        'name': 'page_post_engagements',
                        'values': [{'value': 1}],
                    }, {
                        'name': 'page_follows',
                        'values': [
                            {'value': 8, 'end_time': '2025-08-25'},
                            {'value': 7, 'end_time': '2025-08-26'},
                        ],
                    }]

                elif params.get('since') == 947409390:
                    data = [{
                        'name': 'page_post_engagements',
                        'values': [{'value': 7}],
                    }, {
                        'name': 'page_follows',
                        'values': [
                            {'value': 7, 'end_time': '2025-08-26'},
                            {'value': 28, 'end_time': '2025-08-27'},
                        ],
                    }]

                elif params.get('since') == 939633390:
                    data = [{
                        'name': 'page_post_engagements',
                        'values': [{'value': 8}],
                    }, {
                        'name': 'page_follows',
                        'values': [
                            {'value': 28, 'end_time': '2025-08-28'},
                            {'value': 34, 'end_time': '2025-08-29'},
                        ],
                    }]

                elif params.get('since') == 931857390:
                    data = [{
                        'name': 'page_post_engagements',
                        'values': [{'value': 12}],
                    }, {
                        'name': 'page_follows',
                        'values': [
                            {'value': 34, 'end_time': '2025-08-29'},
                            {'value': 46, 'end_time': '2025-08-30'},
                        ],
                    }]

            return {'data': data}

        def _meta_run_request_batch(env, queries):
            return [get_test_response(query['url'], query.get('params')) for query in queries]

        with patch('odoo.addons.social_facebook.models.social_account.meta_run_request_batch',
            _meta_run_request_batch):
            accounts._compute_statistics()

        # what matter for the audience is the `fan_count` response (API returns 1001)
        # even if the `page_follows` doesn't match (not 100% accurate)
        self.assertEqual(accounts[0].audience, 1001)
        # the last 30 days we started at 1 follower and ended at 13
        # we had 500 before the API calls, and so
        # >>> (13 - 1) / (1001 - (13 - 1)) * 100 ~= 1%
        self.assertEqual(accounts[0].audience_trend, 1)
        # Sum of all engagements this year
        # >>> 3 + 3 + 7 + 4 = 17
        self.assertEqual(accounts[0].engagement, 17)
        # the last 30 days, the sum of all engagements is 6 (1+2+3)
        # this year, we got 17 in total (3+3+7+4)
        # >>> 6 / (17 - 6) * 100 ~= 55%
        self.assertEqual(accounts[0].engagement_trend, 55)

        self.assertEqual(accounts[1].audience, 120)
        self.assertEqual(accounts[1].audience_trend, -10)
        self.assertEqual(accounts[1].engagement, 28)
        self.assertEqual(accounts[1].engagement_trend, 40)

    @mock_void_external_calls()
    def test_social_user_update_likes(self):
        stream = self.env['social.stream'].create({
            'account_id': self.social_account.id,
            'media_id': self.social_account.media_id.id,
            'stream_type_id': self.env.ref('social_facebook.stream_type_page_posts').id,
        })
        stream_post = self.env['social.stream.post'].create({
            'facebook_likes_count': 4,
            'facebook_reactions_count': '{"LIKE": 4, "LOVE": 3}',
            'stream_id': stream.id,
        })

        stream_post.with_user(self.social_user)._facebook_update_likes(True)

        self.assertEqual(stream_post.facebook_likes_count, 5)
        self.assertEqual(stream_post.facebook_reactions_count, '{"LIKE": 5, "LOVE": 3}')
        self.assertTrue(stream_post.facebook_user_likes)

        stream_post.with_user(self.social_user)._facebook_update_likes(False)
        self.assertEqual(stream_post.facebook_likes_count, 4)
        self.assertEqual(stream_post.facebook_reactions_count, '{"LIKE": 4, "LOVE": 3}')
        self.assertFalse(stream_post.facebook_user_likes)

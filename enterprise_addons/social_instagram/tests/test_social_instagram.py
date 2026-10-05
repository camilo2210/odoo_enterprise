# Part of Odoo. See LICENSE file for full copyright and licensing details.

import requests

from freezegun import freeze_time
from unittest.mock import patch

from odoo.addons.social_instagram.tests.common import SocialInstagramCommon
from odoo.tools import mute_logger


class SocialInstagramCase(SocialInstagramCommon):

    def setUp(self):
        super().setUp()
        # default to single account to simplify basic tests
        self.social_post.account_ids = self.social_account

    @mute_logger('odoo.addons.social_instagram.models.social_live_post')
    def test_post_instagram_request_exception(self):
        """ Test that a network error during posting results in a clean failed state. """
        self.social_post.image_ids = self.social_post.image_ids[0]

        with patch.object(requests.Session, 'post', side_effect=requests.exceptions.ReadTimeout):
            self.social_post._action_post()

        live_post = self.social_post.live_post_ids
        self.assertEqual(live_post.state, 'failed')
        self.assertTrue(live_post.failure_reason)

    def test_post_instagram_success_immediate(self):
        """ Test immediate success: FINISHED status on first check. """
        self.social_post.image_ids = self.social_post.image_ids[0]
        self.assertEqual(self.social_post.state, 'draft')

        with self.mock_instagram_api(status='FINISHED', media_id='ig_media_id_1'):
            self.social_post._action_post()

        self.assertEqual(self.social_post.state, 'posted')
        live_post = self.social_post.live_post_ids
        self.assertEqual(len(live_post), 1)
        self.assertEqual(live_post.state, 'posted')
        self.assertEqual(live_post.instagram_post_id, 'ig_media_id_1')

    def test_post_instagram_async_flow(self):
        """ Test async flow: IN_PROGRESS then FINISHED. """
        self.social_post.image_ids = self.social_post.image_ids[0]
        self.assertEqual(self.social_post.state, 'draft')

        with self.mock_instagram_api(status='IN_PROGRESS', media_id='ig_media_id_async'):
            with self.capture_triggers('social.ir_cron_post_scheduled') as triggers:
                self.social_post._action_post()

            live_post = self.social_post.live_post_ids
            self.assertEqual(len(live_post), 1)
            self.assertEqual(live_post.state, 'posting')
            self.assertEqual(self.social_post.state, 'posting')
            self.assertEqual(len(triggers.records), 1)
            self.assertEqual(live_post.instagram_post_id, 'containerID-ig_media_id_async_0')

        with self.mock_instagram_api(status='FINISHED', media_id='ig_media_id_async'):
            live_post._post_instagram()

        self.assertEqual(self.social_post.state, 'posted')
        self.assertEqual(live_post.state, 'posted')
        self.assertEqual(live_post.instagram_post_id, 'ig_media_id_async')

    def test_post_instagram_published_status(self):
        """ Defensive test for the PUBLISHED status.
        This can happen if a previous cron retry successfully published the container but the response was lost
        before we could write state=posted, leaving the record stuck in 'posting'.
        On the next retry we find it already PUBLISHED and treat it as a success.
        """
        self.social_post.image_ids = self.social_post.image_ids[0]
        with self.mock_instagram_api(status='IN_PROGRESS', media_id='ig_media_id_pub'):
            self.social_post._action_post()
            live_post = self.social_post.live_post_ids
            self.assertEqual(len(live_post), 1)
            self.assertEqual(live_post.state, 'posting')

        with self.mock_instagram_api(status='PUBLISHED', media_id='ig_media_id_pub'):
            live_post._post_instagram()

        self.assertEqual(self.social_post.state, 'posted')
        self.assertEqual(live_post.state, 'posted')
        self.assertEqual(live_post.instagram_post_id, 'ig_media_id_pub')

    def test_post_instagram_carousel_async_flow(self):
        """ Test carousel async flow: items FINISHED then carousel container IN_PROGRESS. """
        self.assertEqual(self.social_post.state, 'draft')
        self.assertEqual(len(self.social_post.image_ids), 2)

        with self.mock_instagram_api(status='IN_PROGRESS', media_id='ig_carousel_id'):
            with self.capture_triggers('social.ir_cron_post_scheduled') as triggers:
                self.social_post._action_post()

            live_post = self.social_post.live_post_ids
            self.assertEqual(len(live_post), 1)
            self.assertEqual(live_post.state, 'posting')
            self.assertEqual(len(triggers.records), 1)
            self.assertEqual(live_post.instagram_post_id, 'containerID-ig_carousel_id_2')

        with self.mock_instagram_api(status='FINISHED', media_id='ig_carousel_id'):
            live_post._post_instagram()

        self.assertEqual(self.social_post.state, 'posted')
        self.assertEqual(live_post.state, 'posted')
        self.assertEqual(live_post.instagram_post_id, 'ig_carousel_id')

    def test_post_instagram_error_status(self):
        """ Test behavior when the container status is 'ERROR'. """
        self.social_post.image_ids = self.social_post.image_ids[0]
        with self.mock_instagram_api(status='IN_PROGRESS', media_id='ig_media_id_err'):
            self.social_post._action_post()
            live_post = self.social_post.live_post_ids
            self.assertEqual(len(live_post), 1)
            self.assertEqual(live_post.state, 'posting')

        with self.mock_instagram_api(status='ERROR', media_id='ig_media_id_err'):
            live_post._post_instagram()

        self.assertEqual(self.social_post.state, 'posted')
        self.assertEqual(live_post.state, 'failed')
        self.assertTrue(live_post.failure_reason)

    @freeze_time("2000-07-07 09:16:30")
    @mute_logger("odoo.addons.social_instagram.models.social_account")
    def test_compute_statistics(self):
        accounts = self.env['social.account'].search([('media_type', '=', 'instagram')])
        self.assertEqual(len(accounts), 2)

        accounts[0].write({
            'instagram_account_id': '1337',
            'instagram_access_token': '97',
            'audience': 500,
            'engagement': 10,
        })

        accounts[1].write({
            'instagram_account_id': '1338',
            'instagram_access_token': '98',
            'audience': 200,
            'engagement': 50,
        })

        def get_test_response(url, params, *args, **kwargs):
            data = []

            if params.get('access_token') == '97':
                if 'followers_count' in params.get('fields', ''):
                    return {'followers_count': 1001}

                # One of two should be set, but not both at the same time
                self.assertTrue(bool(params.get('date_preset')) ^ bool(params.get('since')))

                if params.get('metric') == 'follower_count':
                    data = [{
                        'name': 'follower_count',
                        'values': [{'value': 10}, {'value': 2}, {'value': 3}],
                    }]

                # Use the same timestamp as `@SocialFacebookCase.test_compute_statistics`
                # Value between the 90 days block are considered to be zero for the test
                elif params.get('since') == 960369390:
                    # value of the last month
                    data = [{
                        'name': 'total_interactions',
                        'total_value': {'value': 6},
                    }]

                elif params.get('since') in (955185390, 947409390):
                    data = [{
                        'name': 'total_interactions',
                        'total_value': {'value': 3},
                    }]

                elif params.get('since') == 939633390:
                    data = [{
                        'name': 'total_interactions',
                        'total_value': {'value': 7},
                    }]

            elif params.get('access_token') == '98':
                if 'followers_count' in params.get('fields', ''):
                    return {'followers_count': 120}

                if params.get('metric') == 'follower_count':
                    data = [{
                        'name': 'follower_count',
                        'values': [{'value': 1}, {'value': 2}],
                    }]

                elif params.get('since') == 960369390:
                    # value of the last month
                    data = [{
                        'name': 'total_interactions',
                        'total_value': {'value': 8},
                    }]

                elif params.get('since') == 957777390:
                    data = [{
                        'name': 'total_interactions',
                        'total_value': {'value': 11},
                    }]

                elif params.get('since') in (955185390, 931857390):
                    data = [{
                        'name': 'total_interactions',
                        'total_value': {'value': 1},
                    }]

                elif params.get('since') == 947409390:
                    data = [{
                        'name': 'total_interactions',
                        'total_value': {'value': 7},
                    }]

                elif params.get('since') == 939633390:
                    data = [{
                        'name': 'total_interactions',
                        'total_value': {'value': 8},
                    }]

            return {'data': data}

        def _meta_run_request_batch(env, queries):
            return [get_test_response(query['url'], query.get('params')) for query in queries]

        with patch('odoo.addons.social_instagram.models.social_account.meta_run_request_batch',
            _meta_run_request_batch):
            accounts._compute_statistics()

        # For the audience, what matter is the follower count returned by the first call
        self.assertEqual(accounts[0].audience, 1001)
        # 15 followers the last 30 days (10 + 2 + 3)
        # 1001 total followers
        # >>> 15 / (1001 - 15) * 100 ~= 1.52 (rounded to 2)
        self.assertEqual(accounts[0].audience_trend, 2)
        # Engagement are computed based on the engagement of the last year
        # >>> 3 + 3 + 7 + 6 = 19
        self.assertEqual(accounts[0].engagement, 19)
        # The engagement trend is computed based on the engagement of the last 30 days,
        # with the engagement of the last year
        # >>> (1+2+3)/(19-1-2-3) * 100 ~= 46
        self.assertEqual(accounts[0].engagement_trend, 46)

        self.assertEqual(accounts[1].audience, 120)
        self.assertEqual(accounts[1].audience_trend, 3)
        self.assertEqual(accounts[1].engagement, 36)
        self.assertEqual(accounts[1].engagement_trend, 29)

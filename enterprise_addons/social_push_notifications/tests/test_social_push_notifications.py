# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import random
import requests

from datetime import timedelta
from freezegun import freeze_time
from unittest.mock import patch

from odoo import fields
from odoo.tests import tagged

from odoo.addons.base.tests.test_ir_cron import CronMixinCase
from odoo.addons.mail.tools.jwt import generate_vapid_keys
from odoo.addons.social.tests.common import SocialCase


class PushNotificationCatcher:
    """ Test helper that intercepts and records outgoing POST requests
        made via the `requests` library for push notifications. """
    def __init__(self):
        self.captured_outgoing_post_requests = []
        self.patch = None

    def __enter__(self):
        def on_outgoing_post_request(url, **kwargs):
            self.captured_outgoing_post_requests.append({
                **kwargs,
                'url': url
            })
            response = requests.Response()
            response.status_code = 201
            return response
        self.patch = patch('requests.sessions.Session.post', side_effect=on_outgoing_post_request)
        self.patch.__enter__()
        return self.captured_outgoing_post_requests

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.patch:
            self.patch.__exit__(exc_type, exc_val, exc_tb)
        return False


class SocialPushNotificationsCommon(CronMixinCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.website_1 = cls.env['website'].create({
            'name': 'Website 1 WITHOUT push notifications',
            'domain': 'website1.example.com',
            'enable_push_notifications': False,
        })
        cls.website_2 = cls.env['website'].create({
            'name': 'Website 2 WITH push notifications',
            'domain': 'website2.example.com',
            'enable_push_notifications': True
        })
        cls.website_3 = cls.env['website'].create({
            'name': 'Website 3 WITH push notifications',
            'domain': 'website3.example.com',
            'enable_push_notifications': True,
        })
        cls.websites = cls.website_1 | cls.website_2 | cls.website_3

        # Generate VAPID keys for the tests:
        vapid_private_key, vapid_public_key = generate_vapid_keys()
        cls.env['ir.config_parameter'].set_str('social_push_notifications.vapid_public_key', vapid_public_key)
        cls.env['ir.config_parameter'].set_str('social_push_notifications.vapid_private_key', vapid_private_key)

        cls.visitors = cls.env['website.visitor'].create([{
            'access_token': '%032x' % random.randrange(16**32),
            'push_subscription_ids': [(0, 0, {
                'endpoint': f'https://fcm.googleapis.com/fcm/send/fake_token_{i}',
                'keys': json.dumps({
                    'p256dh': 'BE0m0ndx5urJmF0-bjA88yNPt8xNmUPVt5VAC48mbxv8HV6_s4xCjqyl_pydKCwd3ToR-514KepBKfcCt2YWDlU',
                    'auth': 'zqUqxk5qwjRbnHMmf4yS7w'
                }),
            })] if i != 0 else False,
            'website_id': cls.websites[i].id if i != 3 else False,
        } for i in range(0, 4)])

    def capture_push_notifications(self):
        """ Captures the POST requests sent by the server for push notifications. """
        return PushNotificationCatcher()


@tagged('at_install', '-post_install')  # LEGACY at_install
class SocialPushNotificationsCase(SocialPushNotificationsCommon, SocialCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.social_accounts = cls.env['social.account'].search(
            [('website_id', 'in', cls.websites.ids)]
        )

        cls.social_post.invalidate_model(['account_allowed_ids'])
        cls.social_post.write({
            'account_ids': [(6, 0, cls.social_accounts.filtered(lambda a: a.website_id.id != cls.website_3.id).ids)],
        })

    @freeze_time('2025-02-25')
    def test_send_push_notifications(self):
        cron = self.env.ref('social.ir_cron_post_scheduled')

        with self.capture_push_notifications() as captured_outgoing_post_requests, \
             self.capture_triggers('social.ir_cron_post_scheduled') as captured_triggers:

            # Check the initial conditions:
            self.assertEqual(self.social_post.state, 'draft')
            self.assertFalse(self.social_post.scheduled_date)
            self.assertFalse(self.social_post.live_post_ids)
            self.assertFalse(captured_triggers.records)
            self.assertFalse(captured_outgoing_post_requests)

            # Click on the "Post" button:
            self.social_post.action_post_now()

            # When clicking on the "Post" button, it must create the live posts
            # and the cron trigger to send the push notifications. No notification
            # should be sent.

            self.assertEqual(self.social_post.state, 'posting')
            self.assertFalse(self.social_post.scheduled_date)
            self.assertEqual(self.social_post.live_post_ids.mapped('state'), ['ready', 'ready'])
            self.assertEqual(len(captured_triggers.records), 1)
            self.assertEqual(captured_triggers.records.cron_id, cron)
            self.assertEqual(captured_triggers.records.call_at, fields.Datetime.now())
            self.assertFalse(captured_outgoing_post_requests)

            # Trigger the cron job sending the push notifications:
            with self.enter_registry_test_mode():
                cron.method_direct_trigger()

            # Check the new status of the posts:
            self.assertEqual(self.social_post.state, 'posted')
            self.assertEqual(self.social_post.live_post_ids.mapped('state'), ['posted', 'posted'])

            # Check that the notifications have been sent:
            target_visitors = self.env['website.visitor'].search([
                ('has_push_notifications', '=', True),
                ('website_id', 'in', self.social_post.live_post_ids.account_id.website_id.ids)
            ])

            self.assertEqual(len(target_visitors), 1)
            self.assertEqual(len(captured_outgoing_post_requests), 1)
            self.assertEqual(target_visitors.push_subscription_ids.endpoint, captured_outgoing_post_requests[0]['url'])

    @freeze_time('2025-02-22')
    def test_send_push_notifications_with_visitor_domain(self):
        cron = self.env.ref('social.ir_cron_post_scheduled')
        visitor = self.env['website.visitor'].create({
            'access_token': '%032x' % random.randrange(16**32),
            'push_subscription_ids': [(0, 0, {
                'endpoint': f'https://fcm.googleapis.com/fcm/send/fake_token_{len(self.visitors)}',
                'keys': json.dumps({
                    'p256dh': 'BE0m0ndx5urJmF0-bjA88yNPt8xNmUPVt5VAC48mbxv8HV6_s4xCjqyl_pydKCwd3ToR-514KepBKfcCt2YWDlU',
                    'auth': 'zqUqxk5qwjRbnHMmf4yS7w'
                }),
            })],
            'website_id': self.website_2.id,
        })

        with self.capture_push_notifications() as captured_outgoing_post_requests, \
             self.capture_triggers('social.ir_cron_post_scheduled') as captured_triggers:

            scheduled_date = fields.Datetime.now() + timedelta(days=10)
            self.social_post.write({
                'scheduled_date': scheduled_date,
                'visitor_domain': [('id', '=', visitor.id)]
            })

            # When clicking on the "Scheduled" button, it should create the CRON trigger
            self.social_post.action_add_to_queue()
            self.assertEqual(len(captured_triggers.records), 1)

            self.assertEqual(self.social_post.state, 'scheduled')
            self.assertFalse(self.social_post.live_post_ids)
            self.assertFalse(captured_outgoing_post_requests)

            # When triggering the cron job, it must not create the live posts
            # yet, as the scheduled date has not been reached.

            with self.enter_registry_test_mode():
                cron.method_direct_trigger()

            self.assertEqual(self.social_post.state, 'scheduled')
            self.assertFalse(self.social_post.live_post_ids)
            self.assertFalse(captured_outgoing_post_requests)

            # When the cron job is triggered and the scheduled date is reached,
            # it must create the live posts and send the push notifications:

            with self.enter_registry_test_mode(), freeze_time(self.social_post.scheduled_date):
                cron.method_direct_trigger()

            self.assertEqual(self.social_post.state, 'posted')
            self.assertEqual(self.social_post.live_post_ids.mapped('state'), ['posted', 'posted'])
            self.assertEqual(len(captured_outgoing_post_requests), 1)
            self.assertEqual(captured_outgoing_post_requests[0]['url'], visitor.push_subscription_ids.endpoint)

    @freeze_time('2025-11-12')
    def test_send_push_notifications_in_batch(self):
        self.env['ir.config_parameter'].set_str('social_push_notifications.batch_size', 1)
        self.env['website.visitor'].search([]).unlink()
        self.env['website.visitor'].create([{
            'access_token': '%032x' % random.randrange(16**32),
            'push_subscription_ids': [(0, 0, {
                'endpoint': f'https://fcm.googleapis.com/fcm/send/fake_token_{k}',
                'keys': json.dumps({
                    'p256dh': 'BE0m0ndx5urJmF0-bjA88yNPt8xNmUPVt5VAC48mbxv8HV6_s4xCjqyl_pydKCwd3ToR-514KepBKfcCt2YWDlU',
                    'auth': 'zqUqxk5qwjRbnHMmf4yS7w'
                }),
            })],
            'website_id': self.website_2.id,
        } for k in range(10)])

        self.social_post.write({
            'account_ids': [(6, 0, self.social_accounts.filtered(
                lambda a: a.website_id.id == self.website_2.id).ids)]})

        cron = self.env.ref('social.ir_cron_post_scheduled')
        with self.capture_push_notifications() as captured_outgoing_post_requests:
            # Click on the "Post" button:
            self.social_post.action_post_now()

            # When clicking on the "Post" button, it must create the live posts
            # and the cron trigger to send the push notifications. No notification
            # should be sent.

            self.assertEqual(len(self.social_post.live_post_ids), 1)
            self.assertEqual(self.social_post.live_post_ids.state, 'ready')
            self.assertFalse(captured_outgoing_post_requests)

            all_push_subscriptions = self.env['website.visitor.push.subscription'].search([], order='id')
            self.assertEqual(len(all_push_subscriptions), 10)

            # Trigger the cron job sending the push notifications:
            with self.enter_registry_test_mode():
                cron.method_direct_trigger()

            # Check that the notifications has been sent:
            self.assertEqual(self.social_post.state, 'posted')
            self.assertEqual(self.social_post.live_post_ids.state, 'posted')
            self.assertEqual(self.social_post.live_post_ids.last_push_subscription_id, all_push_subscriptions[-1].id)
            self.assertEqual(len(captured_outgoing_post_requests), 10)
            self.assertEqual(
                all_push_subscriptions.mapped('endpoint'),
                [post_request['url'] for post_request in captured_outgoing_post_requests])

            captured_outgoing_post_requests.clear()

            # Re-trigger the cron job to check that it does nothing:
            with self.enter_registry_test_mode():
                cron.method_direct_trigger()

            self.assertEqual(self.social_post.state, 'posted')
            self.assertEqual(self.social_post.live_post_ids.state, 'posted')
            self.assertEqual(self.social_post.live_post_ids.last_push_subscription_id, all_push_subscriptions[-1].id)
            self.assertFalse(captured_outgoing_post_requests)

    @classmethod
    def _get_social_media(cls):
        return cls.env.ref('social_push_notifications.social_media_push_notifications')

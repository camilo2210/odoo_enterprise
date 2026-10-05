# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
from datetime import datetime, timedelta

from odoo.addons.website.tests.test_website_visitor import WebsiteVisitorTests
from odoo.tests import tagged


@tagged('website_visitor')
class WebsiteVisitorTestsPush(WebsiteVisitorTests):
    def test_clean_inactive_visitors_social_push_notifications(self):
        """ Visitors that have subscribed to push notifications should not be deleted even if not
        connected recently. """

        active_visitors = self.env['website.visitor'].create([{
            'name': 'Push Subscriber Adam',
            'lang_id': self.env.ref('base.lang_en').id,
            'country_id': self.env.ref('base.be').id,
            'website_id': self.ref('base.default_website'),
            'last_connection_datetime': datetime.now() - timedelta(days=8),
            'access_token': 'f9d2f932a8f657d2d002638ea80fb97f',
            'push_subscription_ids': [(0, 0, {
                'endpoint': 'https://fcm.googleapis.com/fcm/send/fake_token_0',
                'keys': json.dumps({
                    'p256dh': 'BE0m0ndx5urJmF0-bjA88yNPt8xNmUPVt5VAC48mbxv8HV6_s4xCjqyl_pydKCwd3ToR-514KepBKfcCt2YWDlU',
                    'auth': 'zqUqxk5qwjRbnHMmf4yS7w'
                }),
            })]
        }])

        self._test_unlink_old_visitors(self.env['website.visitor'], active_visitors)

    def test_link_to_visitor_social_push_notifications(self):
        """ Same as parent's 'test_link_to_visitor' except we also test that push subscriptions
        are merged into main visitor. """

        [main_visitor, linked_visitor] = self.env['website.visitor'].create([
            self._prepare_main_visitor_data(),
            self._prepare_linked_visitor_data()
        ])

        [push_subscription_1, push_subscription_2] = self.env['website.visitor.push.subscription'].create([{
            'endpoint': 'https://fcm.googleapis.com/fcm/send/fake_token_0',
            'keys': json.dumps({
                'p256dh': 'BE0m0ndx5urJmF0-bjA88yNPt8xNmUPVt5VAC48mbxv8HV6_s4xCjqyl_pydKCwd3ToR-514KepBKfcCt2YWDlU',
                'auth': 'zqUqxk5qwjRbnHMmf4yS7w'
            }),
            'website_visitor_id': main_visitor.id,
        }, {
            'endpoint': 'https://fcm.googleapis.com/fcm/send/fake_token_1',
            'keys': json.dumps({
                'p256dh': 'BE0m0ndx5urJmF0-bjA88yNPt8xNmUPVt5VAC48mbxv8HV6_s4xCjqyl_pydKCwd3ToR-514KepBKfcCt2YWDlU',
                'auth': 'zqUqxk5qwjRbnHMmf4yS7w'
            }),
            'website_visitor_id': linked_visitor.id,
        }])

        linked_visitor._merge_visitor(main_visitor)

        self.assertVisitorDeactivated(linked_visitor, main_visitor)

        # push subscriptions of both visitors should be merged into main one
        self.assertEqual(push_subscription_1.website_visitor_id, main_visitor)
        self.assertEqual(push_subscription_2.website_visitor_id, main_visitor)
        self.assertEqual(
            main_visitor.push_subscription_ids,
            push_subscription_1 | push_subscription_2)

        self.assertTrue(main_visitor.has_push_notifications)
        self.assertFalse(linked_visitor.exists())

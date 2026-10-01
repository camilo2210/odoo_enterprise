# Part of Odoo. See LICENSE file for full copyright and licensing details.

from contextlib import contextmanager
from datetime import datetime
from dateutil.relativedelta import relativedelta
from freezegun import freeze_time
from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.social.tests.tools import mock_void_external_calls
from odoo.addons.social_test_full.tests.common import SocialTestFullCase
from odoo.addons.social_push_notifications.tests.test_social_push_notifications import SocialPushNotificationsCommon


@tagged('at_install', '-post_install')  # LEGACY at_install
class TestSocialBasic(SocialPushNotificationsCommon, SocialTestFullCase):
    def test_split_per_media(self):
        attachments = self.env["ir.attachment"].create(
            [{"name": "test", "raw": f"test {i}".encode()} for i in range(3)])

        images = self.env["social.post.image"].create([
            {"name": "img.jpg", "attachment_id": attachment.id}
            for attachment in attachments
        ])
        post = self.env["social.post"].create(
            {
                # Facebook - Twitter - Push Notification
                "account_ids": (self.accounts[1:3] + self.accounts[4]).ids,
                "image_ids": images[0].ids,
                "message": "test",
            }
        )
        self.assertEqual(post.facebook_message, "test")
        self.assertEqual(post.twitter_message, "test")
        self.assertEqual(post.push_notification_message, "test")
        self.assertEqual(post.facebook_image_ids, images[0], "Should not copy the image until we split")
        self.assertEqual(post.twitter_image_ids, images[0], "Should not copy the image until we split")
        self.assertEqual(post.facebook_image_ids.attachment_id, images[0].attachment_id, "Should not duplicate the attachment")
        self.assertEqual(post.twitter_image_ids.attachment_id, images[0].attachment_id, "Should not duplicate the attachment")

        post.message = "test 2"
        post.image_ids = images.ids
        self.assertEqual(post.facebook_message, "test 2")
        self.assertEqual(post.twitter_message, "test 2")
        self.assertEqual(post.push_notification_message, "test 2")
        self.assertEqual(post.facebook_image_ids, images)
        self.assertEqual(post.twitter_image_ids, images)
        self.assertEqual(post.facebook_image_ids.attachment_id, images.attachment_id)
        self.assertEqual(post.twitter_image_ids.attachment_id, images.attachment_id)

        post.is_split_per_media = True
        post.write(self.env['social.post.template'].action_copy_images(post.image_ids.ids))
        post.facebook_message = "test fb"
        post.twitter_image_ids = images[1].ids
        self.assertEqual(post.facebook_message, "test fb")
        self.assertEqual(post.twitter_message, "test 2")
        self.assertEqual(post.push_notification_message, "test 2")
        self.assertNotEqual(post.facebook_image_ids, images, "Should copy the image to not share the sequence across the media")
        self.assertEqual(post.facebook_image_ids.attachment_id, images.attachment_id)
        self.assertEqual(post.twitter_image_ids, images[1])

        post.action_post_now()
        self.assertEqual(post.live_post_ids[0].message, "test fb")
        self.assertNotEqual(post.live_post_ids[0].image_ids, images)
        self.assertEqual(post.live_post_ids[0].image_ids.attachment_id, images.attachment_id)
        self.assertEqual(post.live_post_ids[1].message, "test 2")
        self.assertEqual(post.live_post_ids[1].image_ids, images[1])
        self.assertEqual(post.live_post_ids[2].message, "test 2")
        self.assertFalse(post.live_post_ids[2].image_ids)

    def test_schedule_post(self):
        time_1 = datetime.now() + relativedelta(hours=1)
        time_2 = time_1 + relativedelta(hours=1)
        time_3 = time_2 + relativedelta(hours=1)
        push_account = self.env['social.account'].search([('website_id', '=', self.website_2.id)])
        post = self.env["social.post"].create(
            {
                # Facebook - Twitter - Push Notification
                "account_ids": (self.accounts[1:3] + push_account).ids,
                "message": "test",
                "scheduled_date": time_1,
            }
        )
        self.assertEqual(post.facebook_scheduled_date, time_1)
        self.assertEqual(post.twitter_scheduled_date, time_1)
        self.assertEqual(post.instagram_scheduled_date, time_1)
        self.assertEqual(post.push_notifications_scheduled_date, time_1)
        self.assertEqual(post.min_calendar_date, time_1)
        self.assertEqual(post.max_calendar_date, time_1)
        self.assertTrue(post.has_scheduled_date)

        post.is_split_per_media = True

        social_cron = self.env.ref('social.ir_cron_post_scheduled')
        with self.capture_triggers(social_cron.id) as capture:
            post.facebook_scheduled_date = time_2
            post.push_notifications_scheduled_date = time_3

        self.assertEqual(len(capture.records), 0)

        # does not create the live post yes
        with self.capture_triggers(social_cron.id) as capture:
            post.action_add_to_queue()

        self.assertEqual(len(capture.records), 3)
        self.assertEqual(set(capture.records.mapped('call_at')), {time_1, time_2, time_3})

        self.assertFalse(post.live_post_ids)
        self.assertEqual(post.state, 'scheduled')

        with self._mock_post_sending(time_1 + relativedelta(minutes=30)) as notif_catcher:
            social_cron.method_direct_trigger()

        self.assertEqual(len(post.live_post_ids), 3, 'Should have created the live post for all accounts')
        self.assertEqual(len(notif_catcher), 0)
        self.assertEqual(post.live_post_ids.mapped('media_type'), ['twitter', 'facebook', 'push_notifications'], "Should be sorted by scheduled date")
        self.assertEqual(post.live_post_ids.mapped('state'), ['posted', 'posting', 'posting'])
        self.assertEqual(post.state, 'posting', 'There are still live post to process, stay in posting state')

        with self._mock_post_sending(time_1 + relativedelta(hours=1, minutes=30)) as notif_catcher:
            social_cron.method_direct_trigger()

        self.assertEqual(len(post.live_post_ids), 3)
        self.assertEqual(len(notif_catcher), 0)
        self.assertEqual(post.live_post_ids.mapped('state'), ['posted', 'posted', 'posting'])
        self.assertEqual(post.state, 'posting', 'There are still live post to process, stay in posting state')

        with self._mock_post_sending(time_1 + relativedelta(hours=2, minutes=30)) as notif_catcher:
            social_cron.method_direct_trigger()

        self.assertEqual(len(post.live_post_ids), 3)
        self.assertEqual(len(notif_catcher), 1)
        self.assertEqual(post.live_post_ids.mapped('state'), ['posted', 'posted', 'posted'])
        self.assertEqual(post.state, 'posted', 'All live posts have been processed')

    def test_action_post_now(self):
        """Test that the "post now" action post right way the scheduled post."""
        social_cron = self.env.ref('social.ir_cron_post_scheduled')
        LivePost = self.env['social.live.post'].pool['social.live.post']
        time_1 = datetime.now() + relativedelta(hours=1)
        time_2 = time_1 + relativedelta(hours=1)
        post = self.env["social.post"].create(
            {
                # Facebook - Twitter
                "account_ids": (self.accounts[1:3]).ids,
                "message": "test",
                "scheduled_date": time_1,
            }
        )
        post.is_split_per_media = True
        post.facebook_scheduled_date = time_2
        post.action_add_to_queue()

        with (
            self._mock_post_sending(time_1 + relativedelta(minutes=30)),
            patch.object(LivePost, '_post', autospec=True, side_effect=LivePost._post) as live_post_post,
        ):
            social_cron.method_direct_trigger()
            self.assertEqual(live_post_post.call_count, 1, "Should have called `_post` only once for Twitter")

        self.assertEqual(len(post.live_post_ids), 2)
        self.assertEqual(post.live_post_ids.mapped('media_type'), ['twitter', 'facebook'], "Should be sorted by scheduled date")
        self.assertEqual(post.live_post_ids.mapped('state'), ['posted', 'posting'])
        self.assertEqual(post.state, 'posting')

        with (
            self._mock_post_sending(time_1 + relativedelta(minutes=30)),
            patch.object(LivePost, '_post', autospec=True, side_effect=LivePost._post) as live_post_post,
        ):
            post.action_post_now()
            self.assertEqual(live_post_post.call_count, 1, "Should have called `_post` only once for Facebook")

        self.assertEqual(len(post.live_post_ids), 2)
        self.assertEqual(post.live_post_ids.mapped('state'), ['posted', 'posted'])
        self.assertEqual(post.state, 'posted')

    @contextmanager
    def _mock_post_sending(self, mock_dt):
        with (
            freeze_time(mock_dt),
            patch.object(self.env.cr, 'now', lambda: mock_dt),
            self.enter_registry_test_mode(),
            self.capture_push_notifications() as notif_catcher,
            mock_void_external_calls(),
        ):
            yield notif_catcher

# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta

from odoo import fields
from odoo.addons.social.tests import common
from odoo.addons.social.tests.tools import mock_void_external_calls
from odoo.addons.base.tests.test_ir_cron import CronMixinCase
from odoo.tests.common import users, tagged


@tagged("utm")
@tagged('at_install', '-post_install')  # LEGACY at_install
class TestSocialBasics(common.SocialCase, CronMixinCase):
    @mock_void_external_calls()
    def test_cron_triggers(self):
        """ When scheduling social posts, CRON triggers should be created to run the CRON sending
        the post as close to the time frame as possible. """

        scheduled_date = fields.Datetime.now() + timedelta(days=1)
        with self.capture_triggers('social.ir_cron_post_scheduled') as captured_triggers:
            social_post = self.env['social.post'].create({
                'account_ids': [(4, self.social_account.id)],
                'message': 'Test CRON triggers',
                'scheduled_date': scheduled_date
            })
            social_post.action_add_to_queue()

        self.assertEqual(len(captured_triggers.records), 1)
        captured_trigger = captured_triggers.records[0]
        self.assertEqual(captured_trigger.call_at, scheduled_date)
        self.assertEqual(captured_trigger.cron_id, self.env.ref('social.ir_cron_post_scheduled'))

    @users('social_manager')
    @mock_void_external_calls()
    def test_social_post_click_count(self):
        url = 'https://odoo.com/test/click/count/computation'
        post = self.env['social.post'].create({
            'message': f"""
                Hi social users :)
                Visit {url}
            """,
            'account_ids': self.social_accounts.ids,
        })
        post.action_post_now()

        self.env['mail.render.mixin'].sudo()._shorten_links_text(
            post.message,
            post.live_post_ids[0]._get_utm_values()
        )
        link_tracker = self.env['link.tracker'].search([('url', '=', url)])
        self.env['link.tracker.click'].sudo().create([{'link_id': link_tracker.id} for _ in range(7)])

        self.env.invalidate_all()
        self.assertEqual(post.click_count, 7)

    def test_social_post_create_with_default_calendar_date(self):
        """ Make sure that when a default_calendar_date is passed and the scheduled_date is changed,
        We take into account the new scheduled_date as calendar_date.
        See social.post#create for more details."""
        default_calendar_date = fields.Datetime.now() + timedelta(hours=1)
        post = self.env['social.post'].with_context(default_min_calendar_date=default_calendar_date).new()
        post.message = 'this is a message'
        self.assertEqual(post.scheduled_date, default_calendar_date)
        new_scheduled_date = default_calendar_date + timedelta(minutes=20)
        post.scheduled_date = new_scheduled_date
        self.assertEqual(post.min_calendar_date, new_scheduled_date)
        self.assertEqual(post.max_calendar_date, new_scheduled_date)
        self.assertEqual(post.scheduled_date, new_scheduled_date)

    @classmethod
    def _get_social_media(cls):
        return cls.env['social.media'].create({
            'name': 'Social Media',
        })

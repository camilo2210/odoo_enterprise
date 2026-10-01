# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from freezegun import freeze_time

from odoo import fields
from odoo.addons.social.tests import common
from odoo.addons.digest.tests.common import TestDigestCommon
from odoo.addons.social.tests.tools import mock_void_external_calls
from odoo.tests import tagged
from odoo.tests.common import users


@tagged('post_install', '-at_install')
class TestSocialDigest(common.SocialCase, TestDigestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.reference_now = fields.Datetime.from_string('2024-02-05 08:11:34')
        one_hour_ago = cls.reference_now + relativedelta(hours=-1)
        with mock_void_external_calls(), freeze_time(one_hour_ago):
            cls.env.cr._now = one_hour_ago  # force create_date
            cls.company_1 = cls.social_manager.company_id
            cls.account_1 = cls.social_accounts[0]
            cls.url = 'https://odoo.com/test/click/count/computation'

            cls.post = cls.env['social.post'].create({
                'message': f"Hi social users :) Visit {cls.url}",
                'account_ids': cls.account_1.ids,
                'company_id': cls.company_1.id,
            })
            cls.post.action_post_now()
            for live_post in cls.post.live_post_ids:
                tracker = cls.env['link.tracker'].search_or_create([dict(live_post._get_utm_values(), url=cls.url)])
                for idx in range(3):
                    cls.env['link.tracker.click'].sudo().add_click(
                        tracker.code, ip=f'100.0.0.{idx}', country_code='BE')
                live_post.likes_count = 3
            cls.env.flush_all()

    @classmethod
    def _get_social_media(cls):
        return cls.env['social.media'].create({'name': 'Social Media'})

    @users('social_manager')
    def kpi_nbr_of_clicks(self):
        self.env['digest.digest'].invalidate_model(['kpi_nbr_of_clicks_value'])
        ctx_last_24_hours = {
            'start_datetime': self.reference_now - relativedelta(hours=24),
            'end_datetime': self.reference_now,
        }
        self.assertEqual(self.digest_1.with_context(**ctx_last_24_hours).kpi_nbr_of_clicks_value, 3)

        self.env['digest.digest'].invalidate_model(['kpi_nbr_of_clicks_value'])
        ctx_before_last_24_hours = {
            'start_datetime': self.reference_now - relativedelta(hours=48),
            'end_datetime': self.reference_now - relativedelta(hours=24),
        }
        self.assertEqual(self.digest_1.with_context(**ctx_before_last_24_hours).kpi_nbr_of_clicks_value, 0)

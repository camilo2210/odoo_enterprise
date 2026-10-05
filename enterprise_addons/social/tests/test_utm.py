# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.social.tests.common import SocialCase
from odoo.addons.social.tests.tools import mock_void_external_calls
from odoo.addons.utm.tests.common import TestUTMCommon
from odoo.exceptions import UserError
from odoo.tests.common import tagged, users


@tagged('post_install', '-at_install', 'utm_consistency')
class TestUTMConsistencySocial(TestUTMCommon, SocialCase):

    @classmethod
    def setUpClass(cls):
        super(TestUTMConsistencySocial, cls).setUpClass()

        cls.user_social_manager = cls.env['res.users'].create({
            'name': 'Social Manager',
            'login': 'user_social_manager',
            'email': 'user_social_manager@test.com',
            'group_ids': [(6, 0, [cls.env.ref('social.group_social_manager').id])],
        })

    @users('user_social_manager')
    @mock_void_external_calls()
    def test_utm_consistency_social_manager_user(self):
        # social manager user should be able to unlink all UTM models
        self.utm_campaign.unlink()
        self.utm_medium.unlink()
        self.utm_source.unlink()

    @classmethod
    def _get_social_media(cls):
        return cls.env['social.media'].create({
            'name': 'Social Media',
        })

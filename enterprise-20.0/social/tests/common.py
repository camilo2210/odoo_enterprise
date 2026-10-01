# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api
from odoo.addons.base.tests.files import PNG_RAW
from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.addons.social.tests.tools import mock_void_external_calls
from odoo.addons.social.models.social_post import SocialPost
from odoo.tests import common


class SocialCase(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super(SocialCase, cls).setUpClass()

        # The media type created for testing in `social` does not have a custom scheduled date
        # fields, fallback to `scheduled_date`
        scheduled_date_fields = SocialPost._scheduled_date_fields
        cls.classPatch(
            SocialPost,
            '_scheduled_date_fields',
            api.model(lambda model: {**scheduled_date_fields(model), False: 'scheduled_date'}),
        )

        with mock_void_external_calls():
            cls.social_media = cls._get_social_media()
            cls.social_account = cls._get_social_account()

            attachments = cls.env["ir.attachment"].create([{
                'name': 'first.png',
                'raw': PNG_RAW,
            }, {
                'name': 'second.png',
                'raw': PNG_RAW,
            }])

            cls.social_accounts = cls._get_post_social_accounts()

            cls.social_post = cls.env['social.post'].create({
                'message': 'A message',
                'image_ids': [(0, 0, {'attachment_id': attachment.id}) for attachment in attachments],
                'account_ids': [(4, account.id) for account in cls.social_accounts],
                'is_split_per_media': False,
            })

            cls.social_manager = mail_new_test_user(
                cls.env, name='Gustave Doré', login='social_manager', email='social.manager@example.com',
                groups='social.group_social_manager,base.group_user'
            )

            cls.social_user = mail_new_test_user(
                cls.env, name='Lukas Peeters', login='social_user', email='social.user@example.com',
                groups='social.group_social_user,base.group_user'
            )

            cls.user_emp = mail_new_test_user(
                cls.env, name='Eglantine Employee', login='user_emp', email='employee@example.com',
                groups='base.group_user', password='user_emp'
            )

    @classmethod
    def _get_social_media(cls):
        return None

    @classmethod
    def _get_social_account(cls):
        return cls.env['social.account'].create({
            'media_id': cls._get_social_media().id,
            'name': 'Social Account 1'
        })

    @classmethod
    def _get_post_social_accounts(cls):
        return cls.social_account | cls.env['social.account'].create({
            'media_id': cls._get_social_media().id,
            'name': 'Social Account 2'
        })

    def _checkPostedStatus(self, success):
        live_posts = self.env['social.live.post'].search([('post_id', '=', self.social_post.id)])

        self.assertEqual(len(live_posts), 2)
        self.assertTrue(all(live_post.state == 'posted' if success else 'failed' for live_post in live_posts))
        self.assertEqual(self.social_post.state, 'posted')

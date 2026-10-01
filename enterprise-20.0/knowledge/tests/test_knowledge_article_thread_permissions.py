# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.knowledge.tests.common import  KnowledgeArticlePermissionsCase
from odoo.tests.common import tagged, users
from odoo.exceptions import AccessError

@tagged('knowledge_comments')
@tagged('at_install', '-post_install')  # LEGACY at_install
class TestKnowledgeArticleThreadPermissions(KnowledgeArticlePermissionsCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Threads = cls.env['knowledge.article.thread'].with_context({'mail_create_nolog': True})

        # Every internal user can write on it
        cls.writable_article = cls.article_roots[0]
        cls.writable_article.invite_members(cls.partner_portal, 'write')
        cls.workspace_thread = Threads.create({
            'article_id': cls.writable_article.id
        })
        cls.workspace_thread.message_post(body='This is a public Thread')

        # Employee is readonly
        cls.shared_article = cls.article_roots[2]
        cls.shared_thread = Threads.create({
            'article_id': cls.shared_article.id
        })
        cls.shared_thread.message_post(body='This is a shared Thread')

        # Only employee_manager can write on it
        cls.private_article = cls.env['knowledge.article'].create([
            {'article_member_ids': [
                (0, 0, {'partner_id': cls.partner_employee_manager.id,
                        'permission': 'write',
                       }),
             ],
             'internal_permission': 'none',
             'name': 'Private Root',
            }])
        cls.private_thread = Threads.create({
            'article_id': cls.private_article.id
        })
        cls.private_thread.message_post(body='This is a private Thread')

    @users('employee')
    def test_create_article_thread_as_employee(self):
        article = self.writable_article.with_env(self.env)
        # writable article
        self.env['knowledge.article.thread'].create([{
            'article_id': article.id,
        }])
        with self.assertRaises(AccessError):
            # readonly article
            self.env['knowledge.article.thread'].create([{
                'article_id': self.shared_article.with_env(self.env).id
            }])

    @users('employee')
    def test_read_article_thread_as_employee(self):
        private_thread = self.private_thread.with_env(self.env)
        shared_thread = self.shared_thread.with_env(self.env)
        workspace_thread = self.workspace_thread.with_env(self.env)

        # When you have access to an article you can write and read on threads
        self.assertFalse(workspace_thread.is_resolved)
        self.assertFalse(shared_thread.is_resolved)

        #* No access to the article = No access to the linked thread
        with self.assertRaises(AccessError):
            private_thread.is_resolved

    @users('portal_test')
    def test_read_article_thread_as_portal(self):
        private_thread = self.private_thread.with_env(self.env)
        shared_thread = self.shared_thread.with_env(self.env)
        workspace_thread = self.workspace_thread.with_env(self.env)

        # When you have access to an article you can write and read on threads
        self.assertFalse(workspace_thread.is_resolved)
        with self.assertRaises(AccessError):
            shared_thread.is_resolved

        #* No access to the article = No access to the linked thread
        with self.assertRaises(AccessError):
            private_thread.is_resolved

    @users('employee')
    def test_security_thread_resolution(self):
        base_thread = self.private_thread.with_env(self.env)

        # No access to the article
        with self.assertRaises(AccessError):
            base_thread.write({'is_resolved': True})

        base_thread = self.workspace_thread.with_env(self.env)
        # Access to the article
        self.assertFalse(base_thread.is_resolved)
        base_thread.write({'is_resolved': True})
        self.assertTrue(base_thread.is_resolved)

    def test_message_post_on_thread(self):
        self.env = self.env(context={**self.env.context, 'lang': 'en_US'})
        with self.assertRaises(AccessError):
            self.private_thread.with_user(self.user_portal).message_post(body="It raises an error because of no access")

        self.private_article.sudo().invite_members(self.partner_portal, 'read')
        self.private_article.sudo().invite_members(self.partner_employee, 'read')

        self.assertMembers(self.private_article, 'none', {self.partner_employee_manager: 'write', self.partner_portal: 'read', self.partner_employee: 'read'})

        for test_user, exp_values in [
            (self.user_portal, {'message_type': 'comment', 'tracking_values': []}),
            (self.user_employee, {'message_type': 'tracking', 'tracking_values': [
                ('article_anchor_text', 'text', 'Old', 'New', {'html_string': 'Anchor Text'}),
            ]}),
        ]:
            with self.subTest(test_user=test_user.name):
                recipients = test_user.partner_id  # get only accessible partners
                with self.mock_mail_gateway(), self.mock_mail_app():
                    _message = self.private_thread.with_user(test_user).message_post(
                        body="Hello Everyone",
                        partner_ids=recipients.ids,
                        tracking_values=[
                            self.private_thread._create_mail_tracking_values(
                                'Old', 'New', 'article_anchor_text', {'string': 'Anchor Text', 'type': 'text'},
                            )
                        ],
                        message_type='tracking',
                    )
                # tracking values should have been filtered, or not, depending on user
                self.assertMessageFields(self._new_msgs, {
                    'author_id': test_user.partner_id,
                    **exp_values,
                })

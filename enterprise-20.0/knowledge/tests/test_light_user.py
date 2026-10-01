# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.addons.base.tests.common import BaseCommon


@tagged('-at_install', 'post_install', 'knowledge_tests')
class TestKnowledgeLightUser(BaseCommon):
    """ A light user reads articles but never writes them. """

    _test_user_groups = ('base.group_user',)
    _test_user_name = 'Light test User'

    def test_home_page_action(self):
        """ The Knowledge app menu runs a server action on `knowledge.article`.

        Without an explicit group on the action, running it would require write
        access on the model, which a light user does not have.
        """
        article = self.env['knowledge.article'].sudo().create({
            'name': "Public Article",
            'internal_permission': 'write',
        })
        readable = self.env['knowledge.article'].search([('id', '=', article.id)])
        self.assertEqual(readable, article, "a light user reads the articles it has access to")
        self.assertFalse(readable.has_access('write'), "a light user never writes an article")

        action = self.env.ref('knowledge.ir_actions_server_knowledge_home_page')
        self.assertEqual(action.env.user.role, 'light_user')
        result = action.run()
        self.assertEqual(result['res_model'], 'knowledge.article')

    def test_user_can_write(self):
        """ `user_can_write` drives the whole Knowledge UI: the editor, the
        "Share" panel and the options dropdown.

        It follows the ACLs and not only the article permission, otherwise a
        light user is offered every edition button of an article it is member
        of, and each of them raises an Access Error.
        """
        article = self.env['knowledge.article'].sudo().create({
            'name': "Shared Article",
            'internal_permission': 'none',
            'article_member_ids': [Command.create({
                'partner_id': self.env.user.partner_id.id,
                'permission': 'write',
            })],
        }).with_env(self.env)

        self.assertTrue(article.user_can_read)
        self.assertTrue(article.user_has_write_access, "the article grants write to its members")
        self.assertFalse(article.user_can_write, "but a light user never writes an article")
        with self.assertRaises(AccessError):
            article.write({'name': "Renamed"})

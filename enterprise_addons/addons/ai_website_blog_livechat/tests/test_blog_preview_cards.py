# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase

from odoo.addons.ai_website_livechat.tests.common import AIPreviewCardCase


class TestAIBlogPreviewCards(AIPreviewCardCase, TransactionCase):
    def test_blog_post_preview_card_renders(self):
        blog = self.env['blog.blog'].create({'name': 'AI Preview Blog'})
        post = self.env['blog.post'].create({
            'name': 'AI Preview Blog Post',
            'blog_id': blog.id,
            'website_published': True,
        })
        self.assertPreviewCardsRender(post, ['AI Preview Blog Post'], expected_count=1)

# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class BlogPost(models.Model):
    _name = 'blog.post'
    _inherit = ['blog.post', 'ai.preview.card.mixin']

    def _ai_get_preview_cards_render_context(self):
        website = self.env.website
        render_context = {
            'website': website,
            'is_view_active': website.is_view_active,
            'opt_blog_cards_design': True,
            'active_tag_ids': [],
            'posts_list_show_parent_blog': True,
            'blog_url': lambda **_: '/blog',
            'tags_list': lambda *_: '',
        }
        return (
            'website_blog.blog_post_card',
            [{**render_context, 'blog_post': record} for record in self],
            '',
        )

# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class SlideChannel(models.Model):
    _name = 'slide.channel'
    _inherit = ['slide.channel', 'ai.preview.card.mixin']

    def _ai_get_preview_cards_render_context(self):
        render_context = {
            'search_tags': self.env['slide.channel.tag'].browse(),
            'search_my': False,
            'search_term': '',
            'search_slide_category': '',
            'slide_query_url': lambda **_: '/slides',
            'slugify_tags': lambda *_, **__: '',
        }
        return (
            'website_slides.course_card',
            [{**render_context, 'channel': channel} for channel in self],
            '',
        )

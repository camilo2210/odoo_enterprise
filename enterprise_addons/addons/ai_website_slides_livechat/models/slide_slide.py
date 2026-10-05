# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class SlideSlide(models.Model):
    _name = 'slide.slide'
    _inherit = ['slide.slide', 'ai.preview.card.mixin']

    def _ai_get_preview_cards_render_context(self):
        return (
            'website_slides.lesson_card',
            [
                {
                    'slide': slide,
                    'channel': slide.channel_id,
                    'channel_progress': {slide.id: {'completed': False}},
                    'invite_preview': False,
                    'query_string': '',
                }
                for slide in self
            ],
            '',
        )

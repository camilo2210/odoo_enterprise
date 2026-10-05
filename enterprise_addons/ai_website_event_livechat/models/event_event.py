# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class EventEvent(models.Model):
    _name = 'event.event'
    _inherit = ['event.event', 'ai.preview.card.mixin']

    def _ai_get_preview_cards_render_context(self):
        website = self.env.website
        render_context = {
            'website': website,
            'opt_events_list_columns': True,
            'opt_events_list_cards': True,
        }
        return (
            'website_event.event_card',
            [{**render_context, 'event': record} for record in self],
            '',
        )

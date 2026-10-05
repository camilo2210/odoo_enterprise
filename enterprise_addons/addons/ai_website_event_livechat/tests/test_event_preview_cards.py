# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta

from odoo.tests import TransactionCase

from odoo.addons.ai_website_livechat.tests.common import AIPreviewCardCase


class TestAIEventPreviewCards(AIPreviewCardCase, TransactionCase):
    def test_event_preview_card_renders(self):
        event = self.env['event.event'].create({
            'name': 'AI Preview Event',
            'date_begin': datetime.now() + timedelta(days=7),
            'date_end': datetime.now() + timedelta(days=8),
            'date_tz': 'UTC',
            'website_published': True,
        })
        self.assertPreviewCardsRender(event, ['AI Preview Event'], expected_count=1)

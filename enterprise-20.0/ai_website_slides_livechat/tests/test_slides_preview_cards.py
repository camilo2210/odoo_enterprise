# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase

from odoo.addons.ai_website_livechat.tests.common import AIPreviewCardCase


class TestAISlidesPreviewCards(AIPreviewCardCase, TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.channel = cls.env['slide.channel'].create({
            'name': 'AI Preview Course',
            'channel_type': 'documentation',
            'enroll': 'public',
            'visibility': 'public',
            'is_published': True,
            'website_published': True,
        })
        cls.slide = cls.env['slide.slide'].create({
            'name': 'AI Preview Lesson',
            'channel_id': cls.channel.id,
            'slide_category': 'document',
            'is_published': True,
            'website_published': True,
            'is_preview': True,
        })

    def test_slide_channel_preview_card_renders(self):
        self.assertPreviewCardsRender(self.channel, ['AI Preview Course'], expected_count=1)

    def test_slide_preview_card_renders(self):
        self.assertPreviewCardsRender(self.slide, ['AI Preview Lesson'], expected_count=1)

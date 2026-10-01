# Part of Odoo. See LICENSE file for full copyright and licensing details.

from lxml import html


class AIPreviewCardCase:
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.website = cls.env.company.website_id or cls.env['website'].create({
            'name': 'AI Preview Test Website',
            'company_id': cls.env.company.id,
        })

    def assertPreviewCardsRender(self, records, expected_names, expected_count=None):
        expected_count = expected_count or len(records)
        website_public_records = records.with_user(self.website.user_id).with_context(website_id=self.website.id)
        result = website_public_records._ai_render_preview_cards()
        self.assertTrue(result, f"Expected preview cards for {records._name} to render.")
        cards_html, card_count = result
        self.assertEqual(card_count, expected_count)

        root = html.fragment_fromstring(cards_html, create_parent='div')
        cards_root_xpath = '//*[contains(concat(" ", normalize-space(@class), " "), " o_ai_preview_cards ")]'
        card_xpath = '//*[contains(concat(" ", normalize-space(@class), " "), " o_ai_preview_card ")]'
        self.assertEqual(len(root.xpath(cards_root_xpath)), 1)
        cards = root.xpath(card_xpath)
        self.assertEqual(len(cards), expected_count)
        for name in expected_names:
            self.assertIn(name, root.text_content())
        for record, card in zip(website_public_records, cards):
            preview_url = record._ai_get_preview_url()
            if preview_url:
                self.assertEqual(card.get('data-href'), preview_url)
        return root, cards_html

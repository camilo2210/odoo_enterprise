# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command
from odoo.tests import HttpCase

from odoo.addons.ai_website_livechat.tests.common import AIPreviewCardCase
from odoo.addons.website_sale.tests.common import WebsiteSaleCommon


class TestAIProductPreviewCards(AIPreviewCardCase, HttpCase, WebsiteSaleCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.preview_pricelist = cls.env['product.pricelist'].create({
            'name': 'AI Preview Discount Pricelist',
            'currency_id': cls.website.currency_id.id,
            'website_id': cls.website.id,
        })
        cls.product_template = cls.env['product.template'].create({
            'name': 'AI Preview Desk',
            'list_price': 100.0,
            'sale_ok': True,
            'website_published': True,
            'taxes_id': [Command.clear()],
        })
        cls.env['product.pricelist.item'].create({
            'pricelist_id': cls.preview_pricelist.id,
            'applied_on': '1_product',
            'product_tmpl_id': cls.product_template.id,
            'compute_price': 'discount',
            'price_discount': 50,
        })
        cls.product_variant = cls.product_template.product_variant_id
        cls.agent = cls.env['ai.agent'].create({'name': 'AI Preview Agent'})
        cls.pricing_context = {
            'website_id': cls.website.id,
            'pricelist_id': cls.preview_pricelist.id,
        }

    def test_product_template_preview_card_renders(self):
        self.assertPreviewCardsRender(
            self.product_template.with_context(**self.pricing_context),
            ['AI Preview Desk'],
            expected_count=1,
        )

    def test_product_variant_preview_card_renders(self):
        self.assertPreviewCardsRender(
            self.product_variant.with_context(**self.pricing_context),
            ['AI Preview Desk'],
            expected_count=1,
        )

    def test_product_template_preview_metadata_uses_final_website_price(self):
        result = self.env['ai.tool'].with_context(**self.pricing_context)._ai_tool_prepare_record_previews(
            {'state': {}},
            'product.template',
            [{'id': self.product_template.id}],
        )

        expected_prices = self.product_template.with_context(
            **self.pricing_context
        )._resolve_product_template_pricing()[self.product_template.id]
        metadata, = result['preview_metadata']
        self.assertEqual(metadata['id'], self.product_template.id)
        self.assertEqual(metadata['price_reduce'], expected_prices['price_reduce'])
        self.assertEqual(metadata['base_price'], expected_prices['base_price'])
        self.assertLess(metadata['price_reduce'], metadata['base_price'])

    def test_product_variant_preview_metadata_uses_final_combination_price(self):
        result = self.env['ai.tool'].with_context(**self.pricing_context)._ai_tool_prepare_record_previews(
            {'state': {}},
            'product.product',
            [{'id': self.product_variant.id}],
        )

        expected_info = self.product_variant.with_context(
            **self.pricing_context
        )._resolve_product_combination_info()[self.product_variant.id]
        metadata, = result['preview_metadata']
        self.assertEqual(metadata['id'], self.product_variant.id)
        self.assertEqual(metadata['price'], expected_info['price'])
        self.assertEqual(metadata['list_price'], expected_info['list_price'])
        self.assertTrue(metadata['has_discounted_price'])

    def test_product_card_html_uses_discounted_price(self):
        root, cards_html = self.assertPreviewCardsRender(
            self.product_template.with_context(**self.pricing_context),
            ['AI Preview Desk'],
            expected_count=1,
        )
        self.assertIn('50', root.text_content())
        self.assertIn('100', root.text_content())
        self.assertIn('<del aria-label="Original price"', cards_html)

    def test_preview_cards_route_checks_product_access(self):
        private_product = self.env['product.template'].create({
            'name': 'Private AI Preview Product',
            'list_price': 20.0,
            'sale_ok': True,
            'website_published': False,
        })
        self.assertEqual(
            self.make_jsonrpc_request(
                '/ai/preview_cards',
                {'model': 'product.template', 'record_ids': [private_product.id]},
            ),
            {'html': False, 'count': 0},
        )

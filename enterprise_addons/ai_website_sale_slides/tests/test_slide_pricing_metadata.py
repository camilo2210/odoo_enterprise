# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command

from odoo.addons.website_sale.tests.common import WebsiteSaleCommon


class TestAISlidePricingMetadata(WebsiteSaleCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.agent = cls.env['ai.agent'].create({'name': 'AI Preview Agent'})

    def test_slide_channel_preview_metadata_inherits_product_pricing(self):
        product = self.env['product.product'].create({
            'name': 'AI Preview Paid Course Product',
            'list_price': 120.0,
            'service_tracking': 'course',
            'taxes_id': [Command.clear()],
        })
        channel = self.env['slide.channel'].create({
            'name': 'AI Preview Paid Course',
            'channel_type': 'documentation',
            'enroll': 'payment',
            'visibility': 'public',
            'is_published': True,
            'product_id': product.id,
        })
        pricelist = self.env['product.pricelist'].create({
            'name': 'AI Course Discount Pricelist',
            'currency_id': self.website.currency_id.id,
            'website_id': self.website.id,
            'item_ids': [
                Command.create({
                    'applied_on': '1_product',
                    'product_tmpl_id': product.product_tmpl_id.id,
                    'compute_price': 'discount',
                    'price_discount': 40,
                }),
            ],
        })
        context = {'website_id': self.website.id, 'pricelist_id': pricelist.id}

        result = self.env['ai.tool'].with_context(**context)._ai_tool_prepare_record_previews(
            {'state': {}},
            'slide.channel',
            [{'id': channel.id}],
        )
        expected_info = product.with_context(
            **context
        )._resolve_product_combination_info()[product.id]

        metadata, = result['preview_metadata']
        self.assertEqual(metadata['price'], expected_info['price'])
        self.assertEqual(metadata['list_price'], expected_info['list_price'])
        self.assertTrue(metadata['has_discounted_price'])

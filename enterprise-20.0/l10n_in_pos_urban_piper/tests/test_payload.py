# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.pos_urban_piper.tests.test_frontend import CommonPosUrbanPiperTest


@tagged('post_install', '-at_install', 'post_install_l10n')
class TestL10nINUrbanPiperPayload(CommonPosUrbanPiperTest):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @AccountTestInvoicingCommon.setup_country('in')
    def setUpClass(cls):
        super().setUpClass()
        cls.zomato = cls.env.ref('pos_urban_piper.pos_delivery_provider_zomato')
        cls.urbanpiper_store.write({
            'aggregator_lines': [Command.create({'delivery_provider_id': cls.zomato.id})],
        })
        cls.taxes_5 = cls.env['account.tax'].create({
            'name': 'GST 5%',
            'amount': 5.00,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'country_id': cls.env.ref('base.in').id,
            'tax_group_id': cls.env['account.tax.group'].create({
                'name': 'GST',
                'country_id': cls.env.ref('base.in').id,
            }).id,
        })
        cls.taxes_18 = cls.env['account.tax'].create({
            'name': 'GST 18%',
            'amount': 18.00,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'country_id': cls.env.ref('base.in').id,
            'tax_group_id': cls.env['account.tax.group'].create({
                'name': 'GST',
                'country_id': cls.env.ref('base.in').id,
            }).id,
        })
        cls.product_tag_1 = cls.env['product.tag'].create({
            'name': 'allergen-milk',
        })
        cls.product_1 = cls.env['product.template'].create({
            'name': 'Product 1',
            'available_in_pos': True,
            'taxes_id': cls.taxes_5.ids,
            'product_tag_ids': [cls.product_tag_1.id],
            'type': 'consu',
            'list_price': 100.0,
            'urbanpiper_pos_platform_ids': [Command.set([cls.zomato.id])],
        })
        cls.product_2 = cls.env['product.template'].create({
            'name': 'Product 2',
            'available_in_pos': True,
            'taxes_id': cls.taxes_18.ids,
            'type': 'consu',
            'list_price': 200.0,
            'urbanpiper_pos_platform_ids': [Command.set([cls.zomato.id])],
        })

    def test_l10n_in_tags_included_in_urban_piper_items(self):
        """Test product tags are correctly sent to UrbanPiper."""
        products = self.product_1 | self.product_2
        items = products._prepare_urbanpiper_data(self.urbanpiper_store)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]['tags'].get('zomato', []), ['alcohol-absent', 'allergen-milk'])
        self.assertEqual(items[1]['tags'].get('default', []), ['packaged-good'])

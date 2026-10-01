# Part of Odoo. See LICENSE file for full copyright and licensing details.

from contextlib import contextmanager
from unittest.mock import patch

from odoo import Command
from odoo.addons.point_of_sale.tests.common import archive_products, CommonPosTest
from ..utils.urbanpiper_connector import UrbanPiperConnector


class CommonPosUrbanPiperTest(CommonPosTest):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        archive_products(cls.env)

        cls.justeat = cls.env.ref('pos_urban_piper.pos_delivery_provider_justeat')
        cls.urban_piper_config = cls.env['pos.config'].create({'name': 'UrbanPiper'})
        cls.urbanpiper_store = cls.env['pos.urbanpiper.store'].create({
            'name': 'Very Special UrbanPiper Store',
            'aggregator_lines': [Command.create({'delivery_provider_id': cls.justeat.id})],
            'urbanpiper_apikey': 'demo',
            'urbanpiper_username': 'demo',
            'city': 'Ahmedabad',
            'store_identifier': 'very-special-store',
            'config_id': cls.urban_piper_config.id
        })

        cls.category = cls.env['pos.category'].create({'name': 'Test Category', 'sequence': 21})
        # Products
        cls.product_1, cls.product_2 = cls.env['product.template'].create([
            {
                'name': 'Product 1',
                'available_in_pos': True,
                'taxes_id': [(5, 0, 0)],
                'type': 'consu',
                'list_price': 100.0,
                'urbanpiper_store_ids': [(4, cls.urbanpiper_store.id)],
                'pos_categ_ids': [Command.link(cls.category.id)],
            },
            {
                'name': 'Product 2',
                'available_in_pos': True,
                'taxes_id': [(5, 0, 0)],
                'type': 'consu',
                'list_price': 200.0,
                'pos_categ_ids': [Command.link(cls.category.id)],
            },
        ])

        # Product with Attributes
        cls.attr = cls.env['product.attribute'].create({
            'name': 'Size',
            'value_ids': [Command.create({'name': 'Small'}), Command.create({'name': 'Large'})],
        })
        cls.attr2 = cls.env['product.attribute'].create({
            'name': 'Toppings',
            'display_type': 'multi',
            'create_variant': 'no_variant',
            'value_ids': [
                Command.create({'name': 'Extra cheese'}),
                Command.create({'name': 'Mushroom'}),
                Command.create({'name': 'Black Olives'}),
            ],
        })
        cls.product = cls.env['product.template'].create({
            'name': 'Pizza',
            'attribute_line_ids': [
                Command.create({
                    'attribute_id': cls.attr.id,
                    'is_urbanpiper_multi_modifiers': False,
                    'value_ids': [Command.set(cls.attr.value_ids.ids)],
                }),
                Command.create({
                    'attribute_id': cls.attr2.id,
                    'is_urbanpiper_multi_modifiers': True,
                    'urbanpiper_min_qty': 0,
                    'urbanpiper_max_qty': 100,
                    'value_ids': [Command.set(cls.attr2.value_ids.ids)],
                }),
            ],
            'pos_categ_ids': [Command.link(cls.category.id)],
        })
        cls.product.attribute_line_ids.product_template_value_ids.filtered(
            lambda ptav: ptav.product_attribute_value_id == cls.attr.value_ids[1]  # Large
        ).write({'urbanpiper_meal_type': '2', 'price_extra': 2.0})

        # Product with attributes for dynamic variant creation
        cls.attribute_color = cls.env['product.attribute'].create({
            'name': 'Color',
            'create_variant': 'dynamic',
            'display_type': 'radio',
            'value_ids': [Command.create({'name': 'Red'}), Command.create({'name': 'Blue'})],
        })
        cls.attribute_size = cls.env['product.attribute'].create({
            'name': 'Size',
            'create_variant': 'dynamic',
            'display_type': 'radio',
            'value_ids': [Command.create({'name': 'Small'}), Command.create({'name': 'Large'})],
        })
        cls.attribute_material = cls.env['product.attribute'].create({
            'name': 'Material',
            'create_variant': 'no_variant',
            'display_type': 'radio',
            'value_ids': [Command.create({'name': 'Cotton'}), Command.create({'name': 'Polyester'})],
        })
        cls.product_tmpl = cls.env['product.template'].create({
            'name': 'T-Shirt',
            'type': 'consu',
            'available_in_pos': True,
            'list_price': 20.0,
            'taxes_id': [(5, 0, 0)],
            'attribute_line_ids': [
                Command.create({
                    'attribute_id': cls.attribute_color.id,
                    'value_ids': [Command.set(cls.attribute_color.value_ids.ids)],
                }),
                Command.create({
                    'attribute_id': cls.attribute_size.id,
                    'value_ids': [Command.set(cls.attribute_size.value_ids.ids)],
                }),
            ],
            'pos_categ_ids': [Command.link(cls.category.id)],
        })

        cls.tax_group = cls.env['account.tax.group'].create({'name': 'VAT'})
        cls.tax_15 = cls.env['account.tax'].create({
            'name': '15% VAT',
            'amount': 15,
            'amount_type': 'percent',
            'tax_group_id': cls.tax_group.id
        })

    def create_urbanpiper_order(self, product=False, qty=1, context=None, provider=False, **kwrgs):
        ctx = dict(self.env.context, store_id=self.urbanpiper_store.id)
        ctx.update(context or {})
        order = self.env['pos.urbanpiper.test.order.wizard'].with_context(ctx)\
            .create({
                'product_id': (product or self.product_1).id,
                'quantity': qty,
                'delivery_provider_id': (provider or self.justeat).id,
                **kwrgs,
            }).make_test_order()
        return order

    @contextmanager
    def capture_request_payloads(self):
        payloads = []

        def make_request_patched(self, endpoint, method, data=None):
            payloads.append(data)
            return {'status': 'success'}

        with patch.object(UrbanPiperConnector, "make_request", make_request_patched):
            yield payloads

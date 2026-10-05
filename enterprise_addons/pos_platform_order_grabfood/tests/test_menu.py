from odoo.fields import Command

from odoo.addons.point_of_sale.tests.common import CommonPosTest, archive_products


class TestGrabFoodMenu(CommonPosTest):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        archive_products(cls.env)

        cls.company_idr = cls.env['res.company'].create({
            'name': 'Company IDR',
            'currency_id': cls.env.ref('base.IDR').id,
        })
        cls.env.user.company_id = cls.company_idr
        cls.provider = cls.env['platform.order.provider'].search([
            ('code', '=', 'grabfood'),
            ('company_id', '=', cls.company_idr.id)], limit=1)
        cls.provider._setup_payment_method(cls.provider)
        cls.provider._setup_pricelist(cls.provider)
        cls.provider.write({
            'state': 'test',
            'grabfood_client_id': 'test_client_id',
            'grabfood_client_secret': 'test_client_secret',
        })

        cls.product_1 = cls.env['product.template'].create({
            'name': 'Product 1',
            'available_in_pos': True,
            'taxes_id': [(5, 0, 0)],
            'type': 'consu',
            'list_price': 100.0,
        })
        cls.product_2 = cls.env['product.template'].create({
            'name': 'Product 2',
            'available_in_pos': True,
            'taxes_id': [(5, 0, 0)],
            'type': 'consu',
            'list_price': 200.0,
        })

        cls.grabfood_config = cls.env['pos.config'].create({
            'name': 'GrabFood',
            'company_id': cls.company_idr.id,
        })

        cls.grabfood_store = cls.env['platform.order.entity'].create({
            'name': 'GrabFood Store',
            'provider_id': cls.provider.id,
            'config_id': cls.grabfood_config.id,
            'external_id': 'store_001',
        })

    def test_grabfood_menu_integration(self):
        pos_category_1 = self.env["pos.category"].create({"name": "Category 1"})
        pos_category_2 = self.env["pos.category"].create({"name": "Category 2"})

        self.grabfood_store.available_categ_ids = [Command.set([pos_category_1.id])]

        self.product_1.pos_categ_ids = [Command.set([pos_category_1.id, pos_category_2.id])]
        self.product_2.pos_categ_ids = [Command.set([pos_category_2.id])]

        menu = self.grabfood_store._prepare_grabfood_menu_data()

        self.assertEqual(menu.get('currency', {}).get('code'), "IDR")

        selling_times = menu.get('sellingTimes', [])
        self.assertEqual(len(selling_times), 1)
        self.assertEqual(len(selling_times[0].get('serviceHours', [])), 7)

        categories = menu.get('categories', [])
        self.assertEqual(len(categories), 1, "Should contain exactly 1 category")

        first_category_items = categories[0].get('items', [])
        self.assertEqual(len(first_category_items), 1, "Should contain exactly 1 product")
        self.assertEqual(first_category_items[0]['name'], "Product 1")

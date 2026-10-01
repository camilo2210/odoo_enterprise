# Part of Odoo. See LICENSE file for full copyright and licensing details
from odoo.addons.product.tests.common import ProductCommon
from odoo.tests import Form, tagged, TransactionCase


@tagged("post_install", "-at_install")
class TestPosPricer(ProductCommon, TransactionCase):
    _test_user_groups = None  # FIXME list needed groups

    def test_pos_pricer_tags_pricelist(self):
        """
        Test that the pricer sales pricelist is correctly applied to products
        """
        pricelist = self._enable_pricelists()
        self.env['product.pricelist.item'].create({
            'pricelist_id': pricelist.id,
            'compute_price': 'discount',
            'applied_on': '3_global',
            'price_discount': 10,
        })
        ProductForm = Form(self.env['product.product'])
        ProductForm.name = "Demo Product"
        ProductForm.lst_price = 100
        ProductForm.pricer_tags_pricelist_id = pricelist
        self.assertEqual(ProductForm.on_sale_price, 90)
        ProductForm.save()
        # After saving, on_sale_price should change if lst_price is modified
        ProductForm.lst_price = 100
        self.assertEqual(ProductForm.on_sale_price, 90)

    def test_pricer_display_price_compute(self):
        """Ensure the compute method sets a default value to avoid crash."""
        product_form = Form(self.env["product.product"])
        product_form.name = "Test Product"
        product = product_form.save()
        display_price = product.pricer_display_price
        self.assertFalse(display_price)

    def test_pos_pricer_tags_pricelist_cost_based(self):
        """
        Test that on_sale_price updates when standard_price changes,
        for a cost-based pricelist.
        """
        pricelist = self.env["product.pricelist"].create({"name": "Cost Pricelist"})
        self.env["product.pricelist.item"].create(
            {
                "pricelist_id": pricelist.id,
                "compute_price": "discount",
                "applied_on": "3_global",
                "base": "standard_price",
                "price_discount": -20,
            }
        )
        ProductForm = Form(self.env["product.product"])
        ProductForm.name = "Cost-Based Product"
        ProductForm.standard_price = 100
        ProductForm.pricer_tags_pricelist_id = pricelist
        self.assertEqual(ProductForm.on_sale_price, 120)
        ProductForm.standard_price = 200
        self.assertEqual(ProductForm.on_sale_price, 240)

    def test_pos_pricer_sales_pricelist_cost_based_onchange_rpc(self):
        """
        Test that on_sale_price updates when standard_price
        changes, for a cost-based pricelist. Uses raw onchange call
        to reproduce the _origin vs dirty value issue in the browser.
        """
        pricelist = self.env['product.pricelist'].create({'name': 'Cost Pricelist'})
        self.env['product.pricelist.item'].create({
            'pricelist_id': pricelist.id,
            'compute_price': 'discount',
            'applied_on': '3_global',
            'base': 'standard_price',
            'price_discount': -20,
        })
        product = self.env['product.product'].create({
            'name': 'Cost-Based Product',
            'standard_price': 100,
            'pricer_tags_pricelist_id': pricelist.id,
        })
        result = self.env['product.product'].browse(product.id).onchange(
            {
                'standard_price': 200,
                'lst_price': product.lst_price,
                'pricer_tags_pricelist_id': pricelist.id,
            },
            ['standard_price'],
            {'on_sale_price': {}}
        )
        self.assertEqual(result['value']['on_sale_price'], 240)

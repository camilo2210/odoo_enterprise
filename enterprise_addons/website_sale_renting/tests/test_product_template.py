# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.fields import Command
from odoo.tests import tagged

from odoo.addons.website_sale_renting.tests.common import WebsiteSaleRentingCommon


@tagged("post_install", "-at_install")
class TestWebsiteSaleRentingProductTemplate(WebsiteSaleRentingCommon):
    def test_get_price_before_discount_ignores_pricelist_for_rental_products(self):
        """Rental prices aggregate every pricelist rule applicable over the rental period, so no
        single rule can represent the whole price, and the generic `_get_price_before_discount`
        can never detect a discount for rental products because
        pricelist_item._show_discount_on_shop() always returns ``False`` for an empty recordset.
        """
        pricelist = self._create_pricelist(
            item_ids=[Command.create({"compute_price": "discount", "price_discount": 20})]
        )

        with self.mock_request() as request:
            combination_info = self.computer.product_tmpl_id._get_additional_combination_info(
                self.computer,
                1.0,
                self.computer.uom_id,
                self.website,
                pricelist,
                request.fiscal_position,
            )

        self.assertEqual(combination_info["list_price"], self.computer.list_price)
        self.assertAlmostEqual(combination_info["price"], self.computer.list_price * 0.8)
        self.assertTrue(combination_info["has_discounted_price"])

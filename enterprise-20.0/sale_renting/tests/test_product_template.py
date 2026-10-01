# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime

from odoo.tests import tagged, users

from odoo.addons.product.tests.common import ProductVariantsCommon
from odoo.addons.sale_renting.tests.common import SaleRentingCommon


@tagged("post_install", "-at_install")
class TestSaleRentingProductTemplate(ProductVariantsCommon, SaleRentingCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.rental_product = cls._create_product(rent_periodicity="days", lst_price=15)

    @users("salesman")
    def test_sale_renting_get_configurator_display_price(self):
        configurator_price = self.env["product.template"]._get_configurator_display_price(
            product_or_template=self.rental_product,
            quantity=3,
            date=datetime(2000, 1, 1),
            currency=self.currency,
            pricelist=self.env["product.pricelist"],
            start_date=datetime(2000, 1, 1),
            end_date=datetime(2000, 1, 3),
        )

        self.assertEqual(configurator_price[0], 30)

    @users("salesman")
    def test_sale_renting_get_additional_configurator_data(self):
        configurator_data = self.env["product.template"]._get_additional_configurator_data(
            product_or_template=self.rental_product,
            date=datetime(2000, 1, 1),
            currency=self.currency,
            pricelist=self.env["product.pricelist"],
            start_date=datetime(2000, 1, 1),
            end_date=datetime(2000, 1, 3),
        )

        self.assertEqual(configurator_data["price_info"], "/ 2 Days")

    def test_action_view_rentals_without_default_product(self):
        """Ensure action_view_rentals does not set default_product_id when no variants exist."""
        self.product_template_sofa.rent_periodicity = "days"
        self.product_template_sofa.product_variant_ids.unlink()

        action = self.product_template_sofa.action_view_rentals()
        self.assertNotIn("default_product_id", action["context"])

# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta

from odoo.fields import Command
from odoo.tests import tagged

from .common import ClickAndCollectRentingCommon


@tagged("post_install", "-at_install")
class TestSaleOrder(ClickAndCollectRentingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cart = cls._create_in_store_delivery_order(
            order_line=[Command.create({"product_id": cls.computer.id, "product_uom_qty": 5.0})]
        )

    def test_rental_product_in_stock_is_available(self):
        with self.mock_request(sale_order_id=self.cart.id):
            insufficient_stock_data = self.cart._get_insufficient_stock_data(self.warehouse.id)
            self.assertFalse(insufficient_stock_data)

    def test_rental_product_insufficient_stock_is_unavailable(self):
        self.cart.order_line.product_uom_qty = 15
        with self.mock_request(sale_order_id=self.cart.id):
            insufficient_stock_data = self.cart._get_insufficient_stock_data(self.warehouse.id)
            self.assertEqual(insufficient_stock_data[self.cart.order_line], 5.0)

    def test_rental_product_in_different_warehouse_is_unavailable(self):
        self.warehouse_2 = self._create_warehouse()
        with self.mock_request(sale_order_id=self.cart.id):
            insufficient_stock_data = self.cart._get_insufficient_stock_data(self.warehouse_2.id)
            self.assertIn(self.cart.order_line, insufficient_stock_data)

    def test_rental_product_order_before_return_is_unavailable(self):
        # Create and validate a SO with 5 rented computers
        so = self._create_in_store_delivery_order(
            order_line=[Command.create({"product_id": self.computer.id, "product_uom_qty": 5.0})]
        )
        so.action_confirm()

        # Check that the product is unavailable for the same dates
        with self.mock_request(sale_order_id=self.cart.id):
            insufficient_stock_data = self.cart.sudo()._get_insufficient_stock_data(
                self.warehouse.id
            )
            self.assertEqual(insufficient_stock_data[self.cart.order_line], 0.0)

    def test_rental_product_order_after_return_is_available(self):
        # Create and validate a SO with 5 rented computers
        # `self.cart` has no salesperson assigned, so it must be confirmed as sudo
        self.cart.sudo().action_confirm()

        # Check that the product is available for dates after the return date
        so = self._create_in_store_delivery_order(
            order_line=[Command.create({"product_id": self.computer.id, "product_uom_qty": 1.0})],
            rental_start_date=self.cart.rental_return_date + relativedelta(days=1),
            rental_return_date=self.cart.rental_return_date + relativedelta(days=2),
        )
        with self.mock_request(sale_order_id=so.id):
            insufficient_stock_data = so._get_insufficient_stock_data(self.warehouse.id)
            self.assertFalse(insufficient_stock_data)

    def test_rental_product_with_preparation_time_is_unavailable_right_after_return(self):
        """Insufficient stock accounts for the product's preparation time, not just its return
        date.
        """
        self.computer.sudo().preparation_time = 48
        self.cart.sudo().action_confirm()

        so = self._create_in_store_delivery_order(
            order_line=[Command.create({"product_id": self.computer.id, "product_uom_qty": 1.0})],
            rental_start_date=self.cart.rental_return_date + relativedelta(days=1),
            rental_return_date=self.cart.rental_return_date + relativedelta(days=2),
        )
        with self.mock_request(sale_order_id=so.id):
            insufficient_stock_data = so._get_insufficient_stock_data(self.warehouse.id)
            self.assertIn(so.order_line, insufficient_stock_data)

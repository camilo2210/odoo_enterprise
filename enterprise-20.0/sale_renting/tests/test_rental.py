# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.fields import Command

from odoo.addons.sale_renting.tests.common import SaleRentingCommon


class TestRental(SaleRentingCommon):
    _test_user_groups = None  # FIXME list needed groups

    def test_return_quantity_always_compliant(self):
        """Ensures one cannot return more than what has been picked up."""
        today = fields.Date.today()
        one_day_later = today + relativedelta(days=1)

        sale_order = self._create_so(
            rental_start_date=today,
            rental_return_date=one_day_later,
            order_line=[
                Command.create({
                    "product_id": self.projector.id,
                    "product_uom_qty": 5,
                    "price_unit": 10,
                })
            ],
        )

        # Pickup
        sale_order.action_confirm()
        action_dict = sale_order.action_open_pickup()
        pickup_wizard = (
            self.env["rental.order.wizard"].with_context(action_dict["context"]).create({})
        )
        pickup_wizard._get_wizard_lines()
        pickup_wizard.apply()

        # Return
        action_dict = sale_order.action_open_return()
        return_wizard = (
            self.env["rental.order.wizard"].with_context(action_dict["context"]).create({})
        )
        return_wizard._get_wizard_lines()
        return_wizard.rental_wizard_line_ids.qty_returned = 4
        return_wizard.apply()

        with self.assertRaises(ValidationError):
            # Try to return more than picked-up (4 + 4 > 5)
            action_dict = sale_order.action_open_return()
            return_wizard = (
                self.env["rental.order.wizard"].with_context(action_dict["context"]).create({})
            )
            return_wizard._get_wizard_lines()
            return_wizard.rental_wizard_line_ids.qty_returned = 4
            return_wizard.apply()

    def test_non_rental_line_does_not_change_description(self):
        sale_order = self._create_so(
            order_line=[
                Command.create({"product_id": self.projector.id}),
                Command.create({"product_id": self.product.id}),
            ]
        )
        _rental_order_line, non_rental_order_line = sale_order.order_line
        self.assertTrue(sale_order.is_rental_order)

        non_rental_order_line.name = "My Test Product"

        # Trigger order line name recompute by changing rental field.
        sale_order.rental_return_date = sale_order.rental_return_date + timedelta(days=1)

        self.assertEqual(
            non_rental_order_line.name,
            "My Test Product",
            "Description of non-rental lines shouldn't be recomputed on rental period change.",
        )

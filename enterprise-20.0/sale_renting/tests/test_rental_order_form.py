# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.fields import Command
from odoo.tests import Form, freeze_time

from odoo.addons.sale_renting.tests.common import SaleRentingCommon


class TestRentalOrderForm(SaleRentingCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.rental_order = cls._create_so(
            order_line=[Command.create({"product_id": cls.projector.id})]
        )
        cls.projector_sol = cls.rental_order.order_line[0]
        cls.rental_order.action_confirm()

        cls.env = cls.env["base"].with_context(default_partner_id=cls.partner.id).env

    def test_starts_as_sales_order(self):
        """
        Test that opening the form view does not initializes rental dates by default. The dates
        should be computed once the first rental product is added to the order.
        """
        order = Form(self.env["sale.order"])

        self.assertFalse(order.rental_start_date)
        self.assertFalse(order.rental_return_date)

    def test_adding_rental_product_switch_to_rental_order(self):
        with Form(self.env["sale.order"]) as order, order.order_line.new() as line:
            line.product_id = self.projector

        self.assertTrue(order.rental_start_date)
        self.assertTrue(order.rental_return_date)

    @freeze_time("2026-04-13 08:00")  # Monday April 13, 2026
    def test_switch_to_rental_order_computes_rental_unit_price(self):
        """
        Test that when ever an order switches to rental because a rental product was added, it
        computes the rental unit price after the rental dates are set.
        """
        self.env.company.rental_resource_calendar_id = self._create_rental_calendar({
            "tuesday": (9, 17),
            "thursday": (9, 17),
        })
        self.projector.write({"rent_periodicity": "nights", "pickup_time": 15, "return_time": 10})

        with Form(self.env["sale.order"]) as order, order.order_line.new() as line:
            line.product_id = self.projector

        self.assertEqual(
            order.record.order_line.price_unit,
            3.5 * 2,
            msg="Tuesday @3pm till Thursday @10am (2 nights) as you can't checkout on Wednesdays",
        )

    def test_remove_rental_dates_switch_to_sales_order(self):
        with Form(self.rental_order) as order:
            order.rental_start_date = False
            order.rental_return_date = False

        self.assertFalse(order.is_rental_order)

    def test_not_allowed_to_remove_part_of_the_rental_period(self):
        order = Form(self.rental_order)

        with (
            self.subTest("rental_start_date"),
            self.assertRaisesRegex(AssertionError, "rental_start_date is a required field"),
        ):
            order.rental_start_date, old_start_date = False, order.rental_start_date
            order.save()

        order.rental_start_date = old_start_date

        with (
            self.subTest("rental_return_date"),
            self.assertRaisesRegex(AssertionError, "rental_return_date is a required field"),
        ):
            order.rental_return_date = False
            order.save()

    def test_recompute_name_of_rental_lines_on_rental_period_change(self):
        old_description = self.projector_sol.name

        with Form(self.rental_order) as order:
            order.rental_start_date = fields.Datetime.now()
            order.rental_return_date = fields.Datetime.now() + relativedelta(days=5)

        new_description = self.projector_sol.name
        self.assertNotEqual(old_description, new_description)

    def test_recompute_name_of_old_rental_lines_when_rental_period_is_removed(self):
        old_line_name = self.projector_sol.name

        with Form(self.rental_order) as order:
            order.rental_start_date = False
            order.rental_return_date = False

        self.assertNotEqual(self.projector_sol.name, old_line_name)

    def test_change_unrelated_order_line_field_does_not_trigger_rental_dates_computation(self):
        # Initialize a sales order with a rentable product
        sales_order = self._create_so(
            rental_start_date=False,
            rental_return_date=False,
            order_line=[Command.create({"product_id": self.projector.id, "is_rental": False})],
        )
        self.assertFalse(sales_order.is_rental_order)

        with Form(sales_order) as order, order.order_line.edit(0) as line:
            # Update a field on the order line that has nothing to do with rental
            line.product_uom_qty = 5

        self.assertFalse(
            order.is_rental_order,
            msg="Changing a field on `order_line` must not toggle update `is_rental_order` unless"
            " an order line's `is_product_rentable` value changes.",
        )

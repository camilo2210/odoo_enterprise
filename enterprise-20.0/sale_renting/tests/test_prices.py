# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.fields import Command

from odoo.addons.sale_renting.tests.common import SaleRentingCommon


class TestRentalPrices(SaleRentingCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.pricelist = cls._enable_pricelists()

        cls.printer = cls._create_product(
            name="Test Printer", rent_periodicity="days", list_price=2
        )
        cls.room = cls._create_product(name="Test Room", rent_periodicity="nights", list_price=10)
        cls.bike = cls._create_product(name="Test Bike", rent_periodicity="weeks", list_price=100)

        cls.day = fields.Datetime.to_datetime("2011-11-02 12:00:00")
        cls.next_hour = cls.day + timedelta(hours=1)
        cls.next_day = cls.day + timedelta(days=1)
        cls.next_week = cls.day + timedelta(weeks=1)

    def _create_pricelist_rule(self, **create_values):
        return self.env["product.pricelist.item"].create({
            "pricelist_id": self.pricelist.id,
            **create_values,
        })

    def test_contextual_price_is_pickup_return_dependant(self):
        price = self.projector.with_context(
            start_date=fields.Datetime.now() + relativedelta(days=1),
            end_date=fields.Datetime.now() + relativedelta(days=1, hours=2),
        )._get_contextual_price()
        self.assertEqual(
            price, 7, "Contextual price should take pickup and return date into account"
        )

    def test_rental_product_prices_no_dates(self):
        self.assertEqual(self.pricelist._get_product_price(self.projector, 1.0), 3.5)

    def test_rental_product_prices_with_dates(self):
        self.assertEqual(
            self.pricelist._get_product_price(
                self.projector, 1.0, start_date=self.day, end_date=self.next_hour
            ),
            3.5,
        )

    def test_rental_prices_includes_number_of_periods(self):
        self.assertEqual(
            self.pricelist._get_product_price(
                self.projector, 1.0, start_date=self.day, end_date=self.next_day
            ),
            3.5 * 24,
        )

    def test_number_of_periods_is_considered_for_rules_minimal_quantities(self):
        self.assertEqual(self.pricelist._get_product_price(self.projector, 1.0), 3.5)
        self._create_pricelist_rule(product_id=self.projector.id, min_quantity=5, fixed_price=2)
        self.assertEqual(
            self.pricelist._get_product_price(
                self.projector, 5.0, start_date=self.day, end_date=self.next_hour
            ),
            2,
            "Price should be 2$/hour",
        )
        self.assertEqual(
            self.pricelist._get_product_price(
                self.projector, 1.0, start_date=self.day, end_date=self.next_day
            ),
            2 * 24,
            "Price should be 48$/24 hours",
        )

    def test_number_of_periods_is_considered_for_rules_minimal_quantities_of_base_pricelist(self):
        base_pricelist = self._create_pricelist()
        self._create_pricelist_rule(pricelist_id=base_pricelist.id, min_quantity=5, fixed_price=2)
        self._create_pricelist_rule(pricelist_id=base_pricelist.id, min_quantity=2, fixed_price=10)
        self._create_pricelist_rule(
            pricelist_id=self.pricelist.id,
            compute_price="discount",
            price_discount=50.0,
            base="pricelist",
            base_pricelist_id=base_pricelist.id,
        )
        start_date, end_date = self.day, self.next_day
        self.assertEqual(self.projector._get_number_of_periods(start_date, end_date), 24)

        price = self.pricelist._get_product_price(
            self.projector, 1, start_date=start_date, end_date=end_date
        )

        self.assertEqual(price, 2 * 0.5 * 24)

    def test_rental_price_rule_is_always_false(self):
        rule = self._create_pricelist_rule(date_start=self.day)
        self.assertEqual(self.pricelist._get_product_rule(self.projector, 1), rule.id)

        for compute_price in (True, False):
            with self.subTest(compute_price=compute_price):
                self.assertFalse(
                    self.pricelist._get_product_price_rule(
                        self.projector,
                        1,
                        start_date=self.day,
                        end_date=self.next_hour,
                        compute_price=compute_price,
                    )[1]
                )

    def test_rental_order_line_does_not_fallback_on_list_price(self):
        """Since a rental product cannot have one price rule, ensure that rental order lines do not
        fallback on the list price."""
        self._create_pricelist_rule(date_start=self.day, fixed_price=10)

        rental_order = self._create_so(
            rental_start_date=self.day,
            rental_return_date=self.next_hour,
            order_line=[Command.create({"product_id": self.projector.id})],
        )

        self.assertFalse(rental_order.order_line.pricelist_item_id)
        self.assertEqual(rental_order.amount_untaxed, 10)

    def test_periodic_rental_price_in_batch_case_all_periodicities(self):
        self._create_pricelist_rule(date_start=self.next_day, fixed_price=10)
        self._create_pricelist_rule(date_start=self.next_week, fixed_price=5)

        prices = self.pricelist._get_products_price(
            self.projector + self.printer + self.room + self.bike,
            1,
            start_date=self.day,
            end_date=self.day + timedelta(days=10),
        )

        self.assertEqual(prices[self.projector.id], (3.5 * 24) + (10 * 6 * 24) + (5 * 3 * 24))
        self.assertEqual(prices[self.printer.id], 2 + (10 * 6) + (5 * 3))
        self.assertEqual(prices[self.room.id], 10 + (10 * 6) + (5 * 3))
        self.assertEqual(prices[self.bike.id], 100 + 5)

    def test_periodic_rental_price_in_batch_case_subset_of_periodicities(self):
        self._create_pricelist_rule(date_start=self.next_day, fixed_price=10)
        self._create_pricelist_rule(date_start=self.next_week, fixed_price=5)

        prices = self.pricelist._get_products_price(
            self.room + self.bike, 1, start_date=self.day, end_date=self.day + timedelta(days=10)
        )

        self.assertEqual(prices[self.room.id], 10 + (10 * 6) + (5 * 3))
        self.assertEqual(prices[self.bike.id], 100 + 5)

    def test_rental_dates_are_ignored_for_sales_products(self):
        price = self.pricelist._get_product_price(
            self.product, 1, start_date=self.day, end_date=self.day + timedelta(days=10)
        )

        self.assertEqual(price, 20.0)

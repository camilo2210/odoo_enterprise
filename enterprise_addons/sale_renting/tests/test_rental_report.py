# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import timedelta

from odoo import Command, fields
from odoo.tests import tagged

from .common import SaleRentingCommon


@tagged("post_install", "-at_install")
class TestRentalReport(SaleRentingCommon):
    _test_user_groups = None  # FIXME list needed groups

    def test_5_days_rental_generates_5_rows_with_5_dates(self):
        """Test that a rental order of 5 days generates 5 rows, with 5 dates."""
        start_date = fields.Datetime.now().replace(hour=0, minute=0, second=0)
        return_date = start_date + timedelta(days=5, seconds=-1)
        rental_order = self._create_so(
            rental_start_date=start_date,
            rental_return_date=return_date,
            order_line=[Command.create({"product_id": self.projector.id})],
        )
        report_lines = self.env["sale.rental.report"].search([("order_id", "=", rental_order.id)])
        self.assertEqual(len(report_lines), 5, "The report should have 5 rows")
        # Verify dates
        report_dates = [line.date.date() for line in report_lines]
        rental_dates = [
            (rental_order.rental_start_date.date() + timedelta(days=i)) for i in range(5)
        ]
        self.assertEqual(report_dates, rental_dates, "Report dates should match rental dates.")
        # Verify product and price
        for line in report_lines:
            self.assertEqual(line.product_id.id, rental_order.order_line.product_id.id)
            self.assertEqual(line.price, rental_order.order_line.price_unit / 5)

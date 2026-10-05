# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import datetime

from dateutil.relativedelta import relativedelta

from odoo.tests import HttpCase, tagged

from odoo.addons.website_sale_renting.tests.common import WebsiteSaleRentingCommon


@tagged("post_install", "-at_install")
class TestRentalCalendar(HttpCase, WebsiteSaleRentingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.closed_for_christmas_calendar = cls.rental_calendar.copy({"name": "Christmas"})
        cls.env["resource.calendar.leaves"].create({
            "name": "Christmas",
            "calendar_id": cls.closed_for_christmas_calendar.id,
            "date_from": "2025-12-25 00:00",
            "date_to": "2025-12-25 23:59",
        })
        cls.env.company.rental_resource_calendar_id = cls.closed_for_christmas_calendar

    def test_rental_constraints_considers_closed_days(self):
        """No rentals allowed on weekends nor Christmas day."""
        constraints = self.make_jsonrpc_request(
            "/rental/product/constraints", {"min_date": "2025-12-01", "max_date": "2026-01-01"}
        )
        all_dates = [(datetime(2025, 12, 1) + relativedelta(days=i)) for i in range(31)]
        non_working_days = [
            date.strftime("%Y-%m-%d")
            for date in all_dates
            # Exclude weekends and Christmas
            if date.weekday() in [5, 6] or date.strftime("%Y-%m-%d") == "2025-12-25"
        ]
        working_days = [
            date.strftime("%Y-%m-%d")
            for date in all_dates
            if date.strftime("%Y-%m-%d") not in non_working_days
        ]
        self.assertIsInstance(constraints, dict)
        for working_day in working_days:
            self.assertIn(working_day, constraints["working_days_and_hours"])
        for non_working_day in non_working_days:
            self.assertNotIn(non_working_day, constraints["working_days_and_hours"])

    def test_rental_constraints_includes_closing_hour(self):
        # Default hours are from 8 to 16h on weekdays. 01/12/2025 is a Monday.
        constraints = self.make_jsonrpc_request(
            "/rental/product/constraints", {"min_date": "2025-12-01", "max_date": "2025-12-02"}
        )
        monday_hours = [
            option["hour"] for option in constraints["working_days_and_hours"]["2025-12-01"]
        ]
        self.assertEqual(monday_hours, [8, 9, 10, 11, 12, 13, 14, 15, 16])

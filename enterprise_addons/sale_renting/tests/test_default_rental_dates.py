# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta
from zoneinfo import ZoneInfo

from odoo import fields
from odoo.fields import Command
from odoo.tests import tagged
from odoo.tests.common import freeze_time
from odoo.tools.date_utils import to_timezone

from odoo.addons.sale_renting.tests.common import SaleRentingCommon


@freeze_time("2026-02-11 18:00:00")  # Wednesday 11th of February
@tagged("post_install", "-at_install")
class TestDefaultRentalDates(SaleRentingCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.jp_tzinfo = ZoneInfo("Asia/Tokyo")  # UTC+9
        cls.now = fields.Datetime.now()
        cls.utc_now = cls.now.replace(tzinfo=ZoneInfo("UTC"))
        cls.next_hour = cls.now + timedelta(hours=1)
        cls.next_day = cls.now + timedelta(days=1)
        cls.company.rental_resource_calendar_id = False

        cls.projector_template = cls.projector.product_tmpl_id

        cls.rental_order = cls._create_so(
            rental_start_date=cls.now,
            rental_return_date=cls.next_hour,
            order_line=[Command.create({"product_id": cls.projector.id})],
        )
        cls.sale_order = cls._create_so(
            is_rental_order=False,
            rental_start_date=False,
            rental_return_date=False,
            order_line=[Command.create({"product_id": cls.projector.id, "is_rental": False})],
        )

    def test_first_potential_day_without_rental_calendar(self):
        # There is no rental calendar. Return the given date.
        potential_date = self.projector_template._get_first_potential_date(self.utc_now)

        self.assertEqual(potential_date, self.utc_now)

    def test_first_potential_day_with_some_forbidden_days(self):
        # Today (Wednesday) is NOT in the attendances. Return next open hour.
        self.company.rental_resource_calendar_id = self._create_rental_calendar({
            "tuesday": (9, 18),
            "friday": (9, 18),
            "sunday": (9, 18),
        })
        potential_date = self.projector_template._get_first_potential_date(self.utc_now)

        self.assertEqual(potential_date, (self.utc_now + timedelta(days=2)).replace(hour=9))

    def test_first_potential_day_with_all_forbidden_days(self):
        # Today = Wednesday, there are NO attendances. Return the given date.
        self.company.rental_resource_calendar_id = self._create_rental_calendar({})
        potential_date = self.projector_template._get_first_potential_date(self.utc_now)

        self.assertEqual(potential_date, self.utc_now)

    def test_default_dates_without_template(self):
        """Without template, the default period should last 24h, starting at the next hour."""
        start, end = self.env["product.template"]._get_default_rental_dates()

        self.assertEqual(start, self.next_hour)
        self.assertEqual(end, self.next_hour + timedelta(days=1))

    def test_default_dates_by_hours(self):
        self.projector.write({"pickup_time": 9, "return_time": 18})

        start, end = self.projector_template._get_default_rental_dates()

        self.assertEqual(start, self.next_hour, msg="Shouldn't consider pickup & return times")
        self.assertEqual(
            end, self.next_hour + timedelta(hours=1), msg="Shouldn't consider pickup & return times"
        )
        self.assertEqual(self.projector._get_number_of_periods(start, end), 1)

    def test_default_dates_by_days_case_pickup_time_smaller_than_return_time(self):
        self.projector.write({"rent_periodicity": "days", "pickup_time": 9, "return_time": 18})

        start, end = self.projector_template._get_default_rental_dates()

        self.assertEqual(start, self.next_day.replace(hour=9))
        self.assertEqual(end, self.next_day.replace(hour=18))
        self.assertEqual(self.projector._get_number_of_periods(start, end), 1)

    def test_default_dates_by_days_case_pickup_time_bigger_than_return_time(self):
        self.projector.write({"rent_periodicity": "days", "pickup_time": 18, "return_time": 9})

        start, end = self.projector_template._get_default_rental_dates()

        self.assertEqual(start, self.next_day.replace(hour=18))
        self.assertEqual(end, (self.next_day + timedelta(days=1)).replace(hour=9))
        self.assertEqual(self.projector._get_number_of_periods(start, end), 1)

    def test_default_dates_by_nights(self):
        self.projector.write({"rent_periodicity": "nights", "pickup_time": 15, "return_time": 10})

        start, end = self.projector_template._get_default_rental_dates()

        self.assertEqual(start, self.next_day.replace(hour=15))
        self.assertEqual(end, (self.next_day + timedelta(days=1)).replace(hour=10))
        self.assertEqual(self.projector._get_number_of_periods(start, end), 1)

    def test_default_dates_by_weeks_case_pickup_time_smaller_than_return_time(self):
        self.projector.write({"rent_periodicity": "weeks", "pickup_time": 9, "return_time": 18})

        start, end = self.projector_template._get_default_rental_dates()

        self.assertEqual(start, self.next_day.replace(hour=9))
        self.assertEqual(end, (self.next_day + timedelta(days=6)).replace(hour=18))
        self.assertEqual(self.projector._get_number_of_periods(start, end), 1)

    def test_default_dates_by_weeks_case_pickup_time_bigger_than_return_time(self):
        self.projector.write({"rent_periodicity": "weeks", "pickup_time": 18, "return_time": 9})

        start, end = self.projector_template._get_default_rental_dates()

        self.assertEqual(start, self.next_day.replace(hour=18))
        self.assertEqual(end, (self.next_day + timedelta(weeks=1)).replace(hour=9))
        self.assertEqual(self.projector._get_number_of_periods(start, end), 1)

    def test_default_dates_in_jp(self):
        self.projector.write({"rent_periodicity": "weeks", "pickup_time": 18, "return_time": 9})

        start, end = self.projector_template._get_default_rental_dates(tzinfo=self.jp_tzinfo)

        to_jp_tz = to_timezone(self.jp_tzinfo)
        self.assertEqual(to_jp_tz(start), to_jp_tz(self.next_day).replace(hour=18))
        self.assertEqual(
            to_jp_tz(end), to_jp_tz(self.next_day + timedelta(weeks=1)).replace(hour=9)
        )
        self.assertEqual(self.projector._get_number_of_periods(start, end), 1)

    def test_ensure_rental_dates_on_empty_order(self):
        self.sale_order.order_line = False

        self.sale_order._ensure_rental_dates()

        self.assertRecordValues(self.sale_order, [{
            "rental_start_date": self.next_hour,
            "rental_return_date": self.next_hour + timedelta(days=1),
        }])  # fmt: skip

    def test_ensure_rental_dates_from_first_rental_product_in_order(self):
        room = self._create_product(rent_periodicity="nights", pickup_time=15, return_time=11)
        self.sale_order.order_line = [
            Command.clear(),
            Command.create({"product_id": self.product.id}),
            Command.create({"product_id": room.id, "is_rental": False}),
            Command.create({"product_id": self.projector.id, "is_rental": False}),
        ]

        self.sale_order._ensure_rental_dates()

        self.assertRecordValues(self.sale_order, [{
            "rental_start_date": self.next_day.replace(hour=15),
            "rental_return_date": (self.next_day + timedelta(days=1)).replace(hour=11),
        }])  # fmt: skip

    def test_ensure_rental_dates_with_some_forbidden_days(self):
        # Today = Wednesday, is NOT in the attendances.
        self.projector.write({"rent_periodicity": "weeks", "pickup_time": 9, "return_time": 18})
        self.company.rental_resource_calendar_id = self._create_rental_calendar({
            "tuesday": (9, 18),
            "friday": (9, 18),
            "sunday": (9, 18),
        })
        order = self.sale_order.with_context(tz=str(self.jp_tzinfo))

        order._ensure_rental_dates()

        to_order_tz = order._to_order_tz
        self.assertEqual(
            to_order_tz(order.rental_start_date), to_order_tz(self.next_day).replace(hour=9)
        )
        self.assertEqual(
            to_order_tz(order.rental_return_date),
            to_order_tz(self.next_day + timedelta(weeks=1)).replace(hour=18),
            msg="Add a full week even if `pickup_time < return_time` as 6 days later is forbidden",
        )

# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime

from odoo import Command

from odoo.addons.sale.tests.common import SaleCommon


class SaleRentingCommon(SaleCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.start_date = datetime(2023, 1, 1, hour=9)
        cls.end_date = datetime(2023, 1, 1, hour=18)

        cls.projector = cls._create_product(
            name="Projector", list_price=3.5, rent_periodicity="hours"
        )

        # Avoid non-determinism in tests.
        cls.company.rental_resource_calendar_id = False

    @classmethod
    def default_env_context(cls):
        # With demo data installed, Robodoo has the Europe/Brussels timezone. This override ensures
        # the environment timezone (`self.env.tz`) is stable.
        return {**super().default_env_context(), "tz": "UTC"}

    @classmethod
    def _create_product(cls, **kwargs):
        if "rent_periodicity" not in kwargs:
            kwargs["rent_periodicity"] = "days"
        return super()._create_product(**kwargs)

    @classmethod
    def _create_so(cls, **values):
        # Provide a default start & end date
        values.setdefault("rental_start_date", cls.start_date)
        values.setdefault("rental_return_date", cls.end_date)
        return super()._create_so(**values)

    @classmethod
    def _create_rental_calendar(cls, attendance_values):
        """Create a calendar with specific daily attendances.
        param attendance_values: dict {day (str): (hour_from, hour_to)}.
        return: resource.calendar.
        """
        days = {
            "monday": "0",
            "tuesday": "1",
            "wednesday": "2",
            "thursday": "3",
            "friday": "4",
            "saturday": "5",
            "sunday": "6",
        }
        return cls.env["resource.calendar"].create({
            "attendance_ids": [
                Command.create({"dayofweek": days[day], "hour_from": hour_from, "hour_to": hour_to})
                for day, (hour_from, hour_to) in attendance_values.items()
            ]
        })

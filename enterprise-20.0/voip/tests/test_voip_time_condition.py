from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("voip", "post_install", "-at_install")
class TestVoipTimeCondition(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.condition = cls.env["voip.time.condition"].create({"timezone": "UTC"})

    def test_default_name_and_timezone(self):
        self.assertEqual(
            self.condition.name,
            f"Time Condition {self.condition.id}",
        )
        self.assertEqual(self.condition.timezone, "UTC")

    def test_period_defaults_represent_all_day(self):
        period = self.env["voip.time.condition.period"].create({
            "time_condition_id": self.condition.id,
        })

        self.assertEqual(period.mode, "open")
        self.assertTrue(period.all_day)
        self.assertEqual(period.hours_display, "All day")
        self.assertEqual(period._get_pbx_values(), {
            "hours_start": "00:00",
            "hours_end": "23:59",
            "week_days": list(range(1, 8)),
            "month_days": list(range(1, 32)),
            "months": list(range(1, 13)),
        })

    def test_period_compact_ranges_are_expanded_for_wazo(self):
        period = self.env["voip.time.condition.period"].create({
            "time_condition_id": self.condition.id,
            "all_day": False,
            "hours_start": 9.0,
            "hours_end": 18.0,
            "week_days": "1-5,7",
            "month_days": "1,15,30-31",
            "months": "1-3,12",
        })

        self.assertEqual(period._get_pbx_values(), {
            "hours_start": "09:00",
            "hours_end": "18:00",
            "week_days": [1, 2, 3, 4, 5, 7],
            "month_days": [1, 15, 30, 31],
            "months": [1, 2, 3, 12],
        })

    def test_float_hour_is_formatted_for_wazo(self):
        period = self.env["voip.time.condition.period"].create({
            "time_condition_id": self.condition.id,
            "all_day": False,
            "hours_start": 9.5,
            "hours_end": 17.0,
        })

        self.assertEqual(period._get_pbx_values()["hours_start"], "09:30")

    def test_period_requires_valid_ordered_hours(self):
        for values in (
            {"hours_start": -1.0, "hours_end": 18.0},
            {"hours_start": 9.0, "hours_end": 25.0},
            {"hours_start": 18.0, "hours_end": 9.0},
            {"hours_start": 9.0, "hours_end": 9.0},
        ):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                self.env["voip.time.condition.period"].create({
                    "time_condition_id": self.condition.id,
                    "all_day": False,
                    **values,
                })

    def test_period_rejects_values_outside_wazo_ranges(self):
        for field_name, value in (
            ("week_days", "0,1"),
            ("week_days", "8"),
            ("month_days", "1-32"),
            ("months", "0-12"),
            ("months", "4-2"),
        ):
            with self.subTest(field_name=field_name), self.assertRaises(ValidationError):
                self.env["voip.time.condition.period"].create({
                    "time_condition_id": self.condition.id,
                    field_name: value,
                })

    def test_copy_keeps_periods_but_clears_all_graph_and_pbx_state(self):
        destination = self.env["res.partner"].create({"name": "Destination"})
        condition = self.env["voip.time.condition"].with_context(
            voip_skip_pbx_sync=True
        ).create({
            "name": "Office hours",
            "timezone": "Europe/Brussels",
            "open_destination_ref": destination,
            "closed_destination_ref": destination,
            "pbx_schedule_id": 42,
            "period_ids": [Command.create({
                "mode": "closed",
                "all_day": False,
                "hours_start": 9.0,
                "hours_end": 12.0,
                "week_days": "1",
            })],
        })

        duplicate = condition.copy()

        self.assertFalse(duplicate.callflow_id)
        self.assertFalse(duplicate.call_group_id)
        self.assertFalse(duplicate.queue_id)
        self.assertFalse(duplicate.pbx_schedule_id)
        self.assertFalse(duplicate.open_destination_ref)
        self.assertFalse(duplicate.closed_destination_ref)
        self.assertEqual(len(duplicate.period_ids), 1)
        duplicate_period = duplicate.period_ids
        self.assertEqual(duplicate_period.mode, "closed")
        self.assertFalse(duplicate_period.all_day)
        self.assertEqual(duplicate_period.hours_start, 9.0)
        self.assertEqual(duplicate_period.hours_end, 12.0)
        self.assertEqual(duplicate_period.week_days, "1")

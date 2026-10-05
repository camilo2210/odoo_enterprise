# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import datetime, timedelta, UTC
from zoneinfo import ZoneInfo

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestAIAgentComputeDate(TransactionCase):
    """Test suite for AI agent compute_date tool."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.agent = cls.env["ai.agent"].create({
            "name": "Test AI Agent",
        })
        # Create a test model with date and datetime fields (using mail.activity as it has both)
        cls.test_model = "mail.activity"
        cls.date_field = "date_done"  # date field
        cls.datetime_field = "create_date"  # datetime field

    def test_validate_inputs(self):
        """Test input validation."""
        # Test invalid model_name
        with self.assertRaises(ValueError):
            self.env['ai.tool']._ai_tool_compute_date("", "create_date")

        with self.assertRaises(ValueError):
            self.env['ai.tool']._ai_tool_compute_date("invalid.model", "create_date")

        # Test invalid field_name
        with self.assertRaises(ValueError):
            self.env['ai.tool']._ai_tool_compute_date(self.test_model, "")

        with self.assertRaises(ValueError):
            self.env['ai.tool']._ai_tool_compute_date(self.test_model, "nonexistent_field")

        # Test non-date field
        with self.assertRaises(ValueError):
            self.env['ai.tool']._ai_tool_compute_date(self.test_model, "name")

    def test_navigate_day(self):
        """Test navigation by day."""
        # Yesterday
        result = self.env['ai.tool']._ai_tool_compute_date(
            self.test_model,
            self.date_field,
            operations=[{"type": "navigate", "period": "day", "offset": -1}]
        )['response']
        expected = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        self.assertEqual(result, expected)

        # Tomorrow
        result = self.env['ai.tool']._ai_tool_compute_date(
            self.test_model,
            self.date_field,
            operations=[{"type": "navigate", "period": "day", "offset": 1}]
        )['response']
        expected = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        self.assertEqual(result, expected)

        # 3 days ago
        result = self.env['ai.tool']._ai_tool_compute_date(
            self.test_model,
            self.date_field,
            operations=[{"type": "navigate", "period": "day", "offset": -3}]
        )['response']
        expected = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
        self.assertEqual(result, expected)

    def test_navigate_day_with_boundary(self):
        """Test navigation by day with boundaries."""
        # Yesterday at start (midnight)
        with self.mock_datetime_and_now(datetime(2025, 10, 14)):
            result = self.env['ai.tool']._ai_tool_compute_date(
                self.test_model,
                self.datetime_field,
                operations=[{"type": "navigate", "period": "day", "offset": -1, "boundary": "start"}]
            )['response']
            # Result should be in UTC
            # October 13, 2025 00:00:00 in user timezone
            expected_dt = datetime(2025, 10, 13, 0, 0, 0, tzinfo=ZoneInfo(self.env.user.tz or 'UTC'))
            expected_utc = expected_dt.astimezone(UTC)
            self.assertEqual(result, expected_utc.strftime('%Y-%m-%d %H:%M:%S'))

    def test_navigate_week(self):
        """Test navigation by week."""
        # Start of this week
        # Use Wednesday, October 15, 2025
        with self.mock_datetime_and_now(datetime(2025, 10, 15)):
            result = self.env['ai.tool']._ai_tool_compute_date(
                self.test_model,
                self.date_field,
                operations=[{"type": "navigate", "period": "week", "offset": 0, "boundary": "start"}]
            )['response']
            # Start of week is Monday (ISO 8601), so October 13, 2025
            self.assertEqual(result, "2025-10-13")

        # End of last week
        with self.mock_datetime_and_now(datetime(2025, 10, 15)):
            result = self.env['ai.tool']._ai_tool_compute_date(
                self.test_model,
                self.date_field,
                operations=[{"type": "navigate", "period": "week", "offset": -1, "boundary": "end"}]
            )['response']
            # End of last week is Sunday October 12, 2025
            self.assertEqual(result, "2025-10-12")

    def test_navigate_month(self):
        """Test navigation by month."""
        # Start of this month
        with self.mock_datetime_and_now(datetime(2025, 10, 15)):
            result = self.env['ai.tool']._ai_tool_compute_date(
                self.test_model,
                self.date_field,
                operations=[{"type": "navigate", "period": "month", "offset": 0, "boundary": "start"}]
            )['response']
            self.assertEqual(result, "2025-10-01")

        # End of last month
        with self.mock_datetime_and_now(datetime(2025, 10, 15)):
            result = self.env['ai.tool']._ai_tool_compute_date(
                self.test_model,
                self.date_field,
                operations=[{"type": "navigate", "period": "month", "offset": -1, "boundary": "end"}]
            )['response']
            self.assertEqual(result, "2025-09-30")

        # Month navigation with day clamping (Jan 31 -> Feb 28/29)
        with self.mock_datetime_and_now(datetime(2025, 1, 31)):
            result = self.env['ai.tool']._ai_tool_compute_date(
                self.test_model,
                self.date_field,
                operations=[{"type": "navigate", "period": "month", "offset": 1}]
            )['response']
            # February 2025 has 28 days, so day should be clamped to 28
            self.assertEqual(result, "2025-02-28")

    def test_navigate_quarter(self):
        """Test navigation by quarter."""
        # Start of this quarter (Q4 2025)
        with self.mock_datetime_and_now(datetime(2025, 10, 15)):
            result = self.env['ai.tool']._ai_tool_compute_date(
                self.test_model,
                self.date_field,
                operations=[{"type": "navigate", "period": "quarter", "offset": 0, "boundary": "start"}]
            )['response']
            self.assertEqual(result, "2025-10-01")

        # End of last quarter (Q3 2025)
        with self.mock_datetime_and_now(datetime(2025, 10, 15)):
            result = self.env['ai.tool']._ai_tool_compute_date(
                self.test_model,
                self.date_field,
                operations=[{"type": "navigate", "period": "quarter", "offset": -1, "boundary": "end"}]
            )['response']
            self.assertEqual(result, "2025-09-30")

    def test_navigate_year(self):
        """Test navigation by year."""
        # Start of this year
        with self.mock_datetime_and_now(datetime(2025, 10, 15)):
            result = self.env['ai.tool']._ai_tool_compute_date(
                self.test_model,
                self.date_field,
                operations=[{"type": "navigate", "period": "year", "offset": 0, "boundary": "start"}]
            )['response']
            self.assertEqual(result, "2025-01-01")

        # End of last year
        with self.mock_datetime_and_now(datetime(2025, 10, 15)):
            result = self.env['ai.tool']._ai_tool_compute_date(
                self.test_model,
                self.date_field,
                operations=[{"type": "navigate", "period": "year", "offset": -1, "boundary": "end"}]
            )['response']
            self.assertEqual(result, "2024-12-31")

    def test_find_previous_weekday(self):
        """Test finding previous occurrence of weekday."""
        # Last Monday (starting from Wednesday October 15, 2025)
        with self.mock_datetime_and_now(datetime(2025, 10, 15)):
            result = self.env['ai.tool']._ai_tool_compute_date(
                self.test_model,
                self.date_field,
                operations=[{"type": "find_previous", "weekday": 0}]  # Monday
            )['response']
            # Previous Monday is October 13, 2025
            self.assertEqual(result, "2025-10-13")

        # Last Friday
        with self.mock_datetime_and_now(datetime(2025, 10, 15)):
            # Wednesday
            result = self.env['ai.tool']._ai_tool_compute_date(
                self.test_model,
                self.date_field,
                operations=[{"type": "find_previous", "weekday": 4}]  # Friday
            )['response']
            # Previous Friday is October 10, 2025
            self.assertEqual(result, "2025-10-10")

    def test_find_next_weekday(self):
        """Test finding next occurrence of weekday."""
        # Next Monday (starting from Wednesday October 15, 2025)
        with self.mock_datetime_and_now(datetime(2025, 10, 15)):
            # Wednesday
            result = self.env['ai.tool']._ai_tool_compute_date(
                self.test_model,
                self.date_field,
                operations=[{"type": "find_next", "weekday": 0}]  # Monday
            )['response']
            # Next Monday is October 20, 2025
            self.assertEqual(result, "2025-10-20")

        # Next Friday
        with self.mock_datetime_and_now(datetime(2025, 10, 15)):
            # Wednesday
            result = self.env['ai.tool']._ai_tool_compute_date(
                self.test_model,
                self.date_field,
                operations=[{"type": "find_next", "weekday": 4}]  # Friday
            )['response']
            # Next Friday is October 17, 2025
            self.assertEqual(result, "2025-10-17")

    def test_pin_time(self):
        """Test pinning to specific time."""
        # 3 days ago at noon
        with self.mock_datetime_and_now(datetime(2025, 10, 15)):
            result = self.env['ai.tool']._ai_tool_compute_date(
                self.test_model,
                self.datetime_field,
                operations=[{"type": "navigate", "period": "day", "offset": -3}],
                pin={"time": "12:00"}
            )['response']
            # October 12, 2025 12:00:00 in user timezone
            expected_dt = datetime(2025, 10, 12, 12, 0, 0, tzinfo=ZoneInfo(self.env.user.tz or 'UTC'))
            expected_utc = expected_dt.astimezone(UTC)
            self.assertEqual(result, expected_utc.strftime('%Y-%m-%d %H:%M:%S'))

        # Tomorrow at 5 PM
        with self.mock_datetime_and_now(datetime(2025, 10, 15)):
            result = self.env['ai.tool']._ai_tool_compute_date(
                self.test_model,
                self.datetime_field,
                operations=[{"type": "navigate", "period": "day", "offset": 1}],
                pin={"time": "17:00"}
            )['response']
            expected_dt = datetime(2025, 10, 16, 17, 0, 0, tzinfo=ZoneInfo(self.env.user.tz or 'UTC'))
            expected_utc = expected_dt.astimezone(UTC)
            self.assertEqual(result, expected_utc.strftime('%Y-%m-%d %H:%M:%S'))

    def test_pin_day(self):
        """Test pinning to specific day of month."""
        # 15th of this month
        with self.mock_datetime_and_now(datetime(2025, 10, 20)):
            result = self.env['ai.tool']._ai_tool_compute_date(
                self.test_model,
                self.date_field,
                operations=[{"type": "navigate", "period": "month", "offset": 0}],
                pin={"day": 15}
            )['response']
            self.assertEqual(result, "2025-10-15")

    def test_pin_weekday_occurrence(self):
        """Test pinning to Nth occurrence of weekday in month."""
        # Second Tuesday of October 2025
        with self.mock_datetime_and_now(datetime(2025, 10, 20)):
            result = self.env['ai.tool']._ai_tool_compute_date(
                self.test_model,
                self.date_field,
                operations=[{"type": "navigate", "period": "month", "offset": 0, "boundary": "start"}],
                pin={"day": {"weekday": 1, "occurrence": 2}},  # Tuesday, 2nd occurrence
            )['response']
            # October 2025: 1st Tuesday is Oct 7, 2nd Tuesday is Oct 14
            self.assertEqual(result, "2025-10-14")

        # First Monday of last month
        with self.mock_datetime_and_now(datetime(2025, 10, 20)):
            result = self.env['ai.tool']._ai_tool_compute_date(
                self.test_model,
                self.date_field,
                operations=[{"type": "navigate", "period": "month", "offset": -1, "boundary": "start"}],
                pin={"day": {"weekday": 0, "occurrence": 1}},  # Monday, 1st occurrence
            )['response']
            # September 2025: 1st Monday is Sep 1
            self.assertEqual(result, "2025-09-01")

        # 2nd Friday of March last year
        with self.mock_datetime_and_now(datetime(2025, 10, 30)):
            result = self.env['ai.tool']._ai_tool_compute_date(
                self.test_model,
                self.date_field,
                operations=[
                    {"type": "navigate", "period": "year", "offset": -1, "boundary": "start"},  # Jan 1, 2024
                    {"type": "navigate", "period": "month", "offset": 2, "boundary": "start"},  # Mar 1, 2024
                ],
                pin={"day": {"weekday": 4, "occurrence": 2}},  # Friday, 2nd occurrence
            )['response']
            # March 2024: 1st Friday is Mar 1, 2nd Friday is Mar 8
            self.assertEqual(result, "2024-03-08")

    def test_navigate_to_specific_month_and_day(self):
        """Test navigating to a specific month and day without using pin.month."""
        # February 15th of this quarter (Q1 2025)
        with self.mock_datetime_and_now(datetime(2025, 1, 20)):
            result = self.env['ai.tool']._ai_tool_compute_date(
                self.test_model,
                self.date_field,
                operations=[
                    {"type": "navigate", "period": "quarter", "offset": 0, "boundary": "start"},  # Jan 1, 2025
                    {"type": "navigate", "period": "month", "offset": 1, "boundary": "start"},  # Feb 1, 2025
                ],
                pin={"day": 15},
            )['response']
            self.assertEqual(result, "2025-02-15")

    def test_combined_operations(self):
        """Test combining multiple operations."""
        # Last Monday at 5 PM
        with self.mock_datetime_and_now(datetime(2025, 10, 15)):
            # Wednesday
            result = self.env['ai.tool']._ai_tool_compute_date(
                self.test_model,
                self.datetime_field,
                operations=[{"type": "find_previous", "weekday": 0}],  # Monday
                pin={"time": "17:00"}
            )['response']
            expected_dt = datetime(2025, 10, 13, 17, 0, 0, tzinfo=ZoneInfo(self.env.user.tz or 'UTC'))
            expected_utc = expected_dt.astimezone(UTC)
            self.assertEqual(result, expected_utc.strftime('%Y-%m-%d %H:%M:%S'))

    def test_offset_limits(self):
        """Test offset validation."""
        # Test offset too large
        with self.assertRaises(ValueError):
            self.env['ai.tool']._ai_tool_compute_date(
                self.test_model,
                self.date_field,
                operations=[{"type": "navigate", "period": "day", "offset": 101}]
            )

        # Test offset too small
        with self.assertRaises(ValueError):
            self.env['ai.tool']._ai_tool_compute_date(
                self.test_model,
                self.date_field,
                operations=[{"type": "navigate", "period": "day", "offset": -101}]
            )

    def test_offset_none(self):
        """Test that None offsets are treated as 0 (no movement)."""
        with self.mock_datetime_and_now(datetime(2025, 10, 15)):
            result = self.env['ai.tool']._ai_tool_compute_date(
                self.test_model,
                self.date_field,
                operations=[{"type": "navigate", "period": "day", "offset": None}]
            )['response']
            self.assertEqual(result, "2025-10-15")

    def test_datetime_field_returns_utc(self):
        """Test that datetime fields return UTC timestamps."""
        with self.mock_datetime_and_now(datetime(2025, 10, 15)):
            result = self.env['ai.tool']._ai_tool_compute_date(
                self.test_model,
                self.datetime_field,
                operations=[{"type": "navigate", "period": "day", "offset": 0, "boundary": "start"}]
            )['response']
            # Result should be in UTC and contain time
            self.assertRegex(result, r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$')

    def test_date_field_returns_date_only(self):
        """Test that date fields return date-only format."""
        with self.mock_datetime_and_now(datetime(2025, 10, 15)):
            result = self.env['ai.tool']._ai_tool_compute_date(
                self.test_model,
                self.date_field,
                operations=[{"type": "navigate", "period": "day", "offset": 0}]
            )['response']
            # Result should be date-only
            self.assertRegex(result, r'^\d{4}-\d{2}-\d{2}$')
            self.assertNotIn(':', result)

    def test_pin_with_none_values(self):
        """Test that pin fields with None values are properly ignored (LLM pattern)."""
        # LLMs often generate complete JSON with None for unused fields
        # This should work without raising validation errors
        with self.mock_datetime_and_now(datetime(2025, 10, 15)):
            result = self.env['ai.tool']._ai_tool_compute_date(
                self.test_model,
                self.datetime_field,
                operations=[{"type": "navigate", "period": "day", "offset": -1}],
                pin={"time": "23:59:59"},
            )['response']
            # Should succeed and use only the time pin
            expected_dt = datetime(2025, 10, 14, 23, 59, 59, tzinfo=ZoneInfo(self.env.user.tz or 'UTC'))
            expected_utc = expected_dt.astimezone(UTC)
            self.assertEqual(result, expected_utc.strftime('%Y-%m-%d %H:%M:%S'))

    def test_pin_weekday_occurrence_with_none_fields(self):
        """Test weekday_occurrence with None values for other pin fields."""
        # Second Monday of last month with None for unused pin fields
        with self.mock_datetime_and_now(datetime(2025, 10, 20)):
            result = self.env['ai.tool']._ai_tool_compute_date(
                self.test_model,
                self.date_field,
                operations=[{"type": "navigate", "period": "month", "offset": -1, "boundary": "start"}],
                pin={"day": {"weekday": 0, "occurrence": 2}},
            )['response']
            # September 2025: 2nd Monday is Sep 8
            self.assertEqual(result, "2025-09-08")

    def test_operations_with_none_values(self):
        """Test that operation fields with None values are properly ignored."""
        # LLMs may include None for optional operation fields
        with self.mock_datetime_and_now(datetime(2025, 10, 15)):
            result = self.env['ai.tool']._ai_tool_compute_date(
                self.test_model,
                self.date_field,
                operations=[
                    {"type": "navigate", "period": "month", "offset": -1, "boundary": "start", "weekday": None},
                    {"type": "find_next", "weekday": 0, "offset": None, "period": None, "boundary": None},
                ],
            )['response']
            # Start of last month (Sept 1 is Monday), find_next Monday goes forward 7 days = Sept 8
            self.assertEqual(result, "2025-09-08")

    def test_pin_with_only_time_no_other_fields(self):
        """Test pin with only time field, no other fields present."""
        with self.mock_datetime_and_now(datetime(2025, 10, 15)):
            result = self.env['ai.tool']._ai_tool_compute_date(
                self.test_model,
                self.datetime_field,
                operations=[{"type": "navigate", "period": "day", "offset": 0}],
                pin={"time": "12:30:45"},
            )['response']
            expected_dt = datetime(2025, 10, 15, 12, 30, 45, tzinfo=ZoneInfo(self.env.user.tz or 'UTC'))
            expected_utc = expected_dt.astimezone(UTC)
            self.assertEqual(result, expected_utc.strftime('%Y-%m-%d %H:%M:%S'))

    def test_complex_query_with_none_values(self):
        """Test complex date computation matching production pattern from logs."""
        # Simulates: "invoiced sales orders from 2nd week of last month"
        # Navigate to start of last month, find next Monday, add 1 week
        with self.mock_datetime_and_now(datetime(2025, 10, 14)):
            result = self.env['ai.tool']._ai_tool_compute_date(
                self.test_model,
                self.date_field,
                operations=[
                    {"type": "navigate", "period": "month", "offset": -1, "boundary": "start", "weekday": None},
                    {"type": "find_next", "weekday": 0, "offset": None, "period": None, "boundary": None},
                    {"type": "navigate", "period": "week", "offset": 1, "boundary": None, "weekday": None},
                ],
                pin=None,
            )['response']
            # Sept 1 is Monday, find_next Monday = Sept 8, + 1 week = Sept 15
            self.assertEqual(result, "2025-09-15")

    def test_find_weekday_crosses_dst_boundary(self):
        """Test find_weekday operations that cross DST boundaries without pin."""
        self.env.user.tz = 'Europe/Brussels'

        # Test crossing DST end boundary (CEST UTC+2 -> CET UTC+1)
        # Start: Friday Oct 24, 2025 (CEST, UTC+2) at default midnight
        # Find next Monday: Oct 27, 2025 (CET, UTC+1) - crosses DST boundary on Oct 26
        with self.mock_datetime_and_now(datetime(2025, 10, 24)):
            # Friday
            result = self.env['ai.tool']._ai_tool_compute_date(
                self.test_model,
                self.datetime_field,
                operations=[{"type": "find_next", "weekday": 0}],  # Monday
                pin=None,  # No pin - this is critical for the bug
            )['response']
            # Oct 27, 2025 00:00:00 CET (UTC+1) = Oct 26, 2025 23:00:00 UTC
            self.assertEqual(result, "2025-10-26 23:00:00")

        # Test crossing DST start boundary (CET UTC+1 -> CEST UTC+2)
        # Start: Friday Mar 28, 2025 (CET, UTC+1) at default midnight
        # Find next Monday: Mar 31, 2025 (CEST, UTC+2) - crosses DST boundary on Mar 30
        with self.mock_datetime_and_now(datetime(2025, 3, 28)):
            # Friday
            result = self.env['ai.tool']._ai_tool_compute_date(
                self.test_model,
                self.datetime_field,
                operations=[{"type": "find_next", "weekday": 0}],  # Monday
                pin=None,
            )['response']
            # Mar 31, 2025 00:00:00 CEST (UTC+2) = Mar 30, 2025 22:00:00 UTC
            self.assertEqual(result, "2025-03-30 22:00:00")

    def test_dst_timezone_handling(self):
        """Test that DST transitions are handled correctly when navigating between seasons."""
        # Set user timezone to Europe/Brussels (has DST)
        self.env.user.tz = 'Europe/Brussels'

        # Test: Navigate from winter (CET, UTC+1) to summer (CEST, UTC+2)
        # Start in October (CET, UTC+1), navigate to May (CEST, UTC+2)
        with self.mock_datetime_and_now(datetime(2025, 10, 30)):
            result = self.env['ai.tool']._ai_tool_compute_date(
                self.test_model,
                self.datetime_field,
                operations=[
                    {"type": "navigate", "period": "quarter", "offset": -2, "boundary": "start"},  # Apr 1, 2025
                    {"type": "navigate", "period": "month", "offset": 1, "boundary": "start"},  # May 1, 2025
                ],
                pin={"day": 16, "time": "00:00:00"},
            )['response']
            # May 16, 2025 00:00:00 in Brussels (UTC+2) = May 15, 2025 22:00:00 UTC
            self.assertEqual(result, "2025-05-15 22:00:00")

        # Test: Navigate from summer (CEST, UTC+2) to winter (CET, UTC+1)
        # Start in May (CEST, UTC+2), navigate to November (CET, UTC+1)
        # DST ends last Sunday of October (Oct 26, 2025), so Nov 1 is definitely CET
        with self.mock_datetime_and_now(datetime(2025, 5, 16)):
            result = self.env['ai.tool']._ai_tool_compute_date(
                self.test_model,
                self.datetime_field,
                operations=[
                    {"type": "navigate", "period": "quarter", "offset": 2, "boundary": "start"},  # Oct 1, 2025
                    {"type": "navigate", "period": "month", "offset": 1, "boundary": "start"},  # Nov 1, 2025
                ],
                pin={"time": "00:00:00"},
            )['response']
            # November 1, 2025 00:00:00 in Brussels (UTC+1) = October 31, 2025 23:00:00 UTC
            self.assertEqual(result, "2025-10-31 23:00:00")

        # Test: Verify 3rd Friday of May with time pins
        # This is the actual case from the user's log
        with self.mock_datetime_and_now(datetime(2025, 10, 30)):
            # Start of day
            result_start = self.env['ai.tool']._ai_tool_compute_date(
                self.test_model,
                self.datetime_field,
                operations=[
                    {"type": "navigate", "period": "quarter", "offset": -2, "boundary": "start"},  # Apr 1, 2025
                    {"type": "navigate", "period": "month", "offset": 1, "boundary": "start"},  # May 1, 2025
                ],
                pin={"day": {"weekday": 4, "occurrence": 3}, "time": "00:00:00"},
            )['response']
            # End of day
            result_end = self.env['ai.tool']._ai_tool_compute_date(
                self.test_model,
                self.datetime_field,
                operations=[
                    {"type": "navigate", "period": "quarter", "offset": -2, "boundary": "start"},  # Apr 1, 2025
                    {"type": "navigate", "period": "month", "offset": 1, "boundary": "start"},  # May 1, 2025
                ],
                pin={"day": {"weekday": 4, "occurrence": 3}, "time": "23:59:59"},
            )['response']
            # May 2025: 3rd Friday is May 16, 2025
            # May 16, 2025 00:00:00 CEST (UTC+2) = May 15, 2025 22:00:00 UTC
            # May 16, 2025 23:59:59 CEST (UTC+2) = May 16, 2025 21:59:59 UTC
            self.assertEqual(result_start, "2025-05-15 22:00:00")
            self.assertEqual(result_end, "2025-05-16 21:59:59")

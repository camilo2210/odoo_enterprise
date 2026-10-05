# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install', 'time_rule_payslip')
class TestTimeRulePayslip(TransactionCase):
    """Payslip worked-days rounding for leaves cut by the time rule pipeline.

    After a rule fires and splits a leave into a trimmed source + output, the payslip
    must show the exact fractional number_of_days instead of snapping to 0 or 1 via
    _round_days.  Normal (non-split) leaves must still round as usual.

    Leaves are created the same way a user would: request_date_from / request_date_to
    (date fields only, not pre-computed UTC datetimes).  _compute_date_from_to resolves
    the exact UTC boundaries from the employee's calendar, and action_approve() triggers
    the time rule pipeline just as it would from the UI.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Test Structure Type',
            'default_schedule_pay': 'monthly',
        })
        cls.structure = cls.env['hr.payroll.structure'].create({
            'name': 'Test Structure',
            'type_id': cls.structure_type.id,
        })

        # 8h/day: 08:00-12:00 + 13:00-17:00, Mon-Fri (1h lunch break 12:00-13:00)
        cls.calendar = cls.env['resource.calendar'].create({
            'name': '40h/week UTC',
            'attendance_ids': [
                (0, 0, {'dayofweek': wd, 'hour_from': h, 'hour_to': h + 4})
                for wd in ['0', '1', '2', '3', '4']
                for h in [8, 13]
            ],
        })
        cls.env.company.resource_calendar_id = cls.calendar

        # source WET: day-unit leave (user requests by day)
        cls.source_wet = cls.env['hr.work.entry.type'].create({
            'name': 'Source Leave',
            'code': 'SRCLV',
            'request_unit': 'day',
            'requires_allocation': False,
            'count_as': 'absence',
            'leave_validation_type': 'no_validation',
        })
        # output WET: where excess/deficit hours go after the split
        cls.output_wet = cls.env['hr.work.entry.type'].create({
            'name': 'Output Leave',
            'code': 'OUTLV',
            'request_unit': 'day',
            'requires_allocation': False,
            'count_as': 'absence',
            'leave_validation_type': 'no_validation',
        })

        cls.employee = cls.env['hr.employee'].create({
            'name': 'Test Employee',
            'tz': 'UTC',
            'resource_calendar_id': cls.calendar.id,
            'contract_date_start': date(2022, 1, 1),
            'date_version': date(2022, 1, 1),
            'structure_type_id': cls.structure_type.id,
            'wage': 2400.0,
        })
        cls.version = cls.employee.version_id

    def setUp(self):
        super().setUp()
        self.env['hr.time.rule'].search([]).write({'active': False})

    def _make_leave(self, date_from, date_to=None, wet=None):
        """Create a leave using natural user request fields (date objects only).

        _compute_date_from_to resolves the UTC start/end from the employee's calendar,
        and the auto-approve path in create() triggers time rules = exactly as the UI does.
        """
        wet = wet or self.source_wet
        date_to = date_to or date_from
        return self.env['hr.leave'].with_context(
            tracking_disable=True,
            mail_activity_automation_skip=True,
        ).sudo().create({
            'employee_id': self.employee.id,
            'work_entry_type_id': wet.id,
            'request_date_from': date_from,
            'request_date_to': date_to,
        })

    def _make_hour_leave(self, request_date, hour_from, hour_to, wet):
        """Create a validated hour-unit leave on a single day (user sets specific hours)."""
        return self.env['hr.leave'].with_context(
            tracking_disable=True,
            mail_activity_automation_skip=True,
        ).sudo().create({
            'employee_id': self.employee.id,
            'work_entry_type_id': wet.id,
            'request_date_from': request_date,
            'request_date_to': request_date,
            'request_hour_from': hour_from,
            'request_hour_to': hour_to,
        })

    def _make_payslip(self):
        payslip = self.env['hr.payslip'].create({
            'name': 'January Payslip',
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'struct_id': self.structure.id,
            'date_from': date(2022, 1, 1),
            'date_to': date(2022, 1, 31),
        })
        payslip.compute_sheet()
        return payslip

    def test_no_rule_normal_rounding_preserved(self):
        """Regression guard: without a time rule a full-day leave produces exactly 1.0 day.

        User requests one full day (Jan 3, Monday).  Calendar gives 08:00-17:00 = 8h.
        No rule is active, so trimmed_duration stays 0 and _round_days is applied normally:
        8h / 8h = 1.0 -> rounds to 1.0 day (unchanged because it is already a whole number).
        Verifies the fix does not break the baseline path.
        """
        self._make_leave(date(2022, 1, 3))

        payslip = self._make_payslip()

        src_line = payslip.worked_days_line_ids.filtered(
            lambda l: l.work_entry_type_id == self.source_wet)

        self.assertTrue(src_line, "payslip must have a SRCLV line")
        self.assertAlmostEqual(src_line.number_of_hours, 8.0, places=5)
        self.assertAlmostEqual(src_line.number_of_days, 1.0, places=5,
            msg="full-day leave with no rule must give exactly 1.0 day")

    def test_split_leave_exact_days(self):
        """Rule splits a full-day leave at 4h wall-clock (08:00+4h = 12:00).

        Calendar: 08:00-12:00 = 4 scheduled hours (morning block).
        Source  (is_time_rule_trimmed, 4h): 0.5 days = must not round DOWN to 0.
        Output  (source_leave_id set,  4h): 0.5 days = must not round DOWN to 0.

        User requests one full day (Jan 3, Monday).  The rule engine trims the source
        to 08:00-12:00 and creates an output leave for 12:00-17:00 (= 4h scheduled after
        the lunch break).
        """
        self.env['hr.time.rule'].create({
            'name': 'Split at 4h',
            'condition_work_entry_type_ids': [(4, self.source_wet.id)],
            'work_entry_type_id': self.output_wet.id,
            'working_hours_mode': 'day',
            'expected_hours': 4.0,
        })
        self._make_leave(date(2022, 1, 3))  # Mon = calendar gives 08:00-17:00

        payslip = self._make_payslip()

        src_line = payslip.worked_days_line_ids.filtered(
            lambda l: l.work_entry_type_id == self.source_wet)
        out_line = payslip.worked_days_line_ids.filtered(
            lambda l: l.work_entry_type_id == self.output_wet)

        self.assertTrue(src_line, "trimmed source WET must appear in payslip")
        self.assertTrue(out_line, "output WET must appear in payslip")

        self.assertAlmostEqual(src_line.number_of_hours, 4.0, places=5)
        self.assertAlmostEqual(src_line.number_of_days, 0.5, places=5,
            msg="4h trimmed source (is_time_rule_trimmed) must give 0.5 days, not rounded to 0")

        self.assertAlmostEqual(out_line.number_of_hours, 4.0, places=5)
        self.assertAlmostEqual(out_line.number_of_days, 0.5, places=5,
            msg="4h output (source_leave_id set) must give 0.5 days, not rounded to 0")

    def test_two_separate_days_each_trimmed(self):
        """Rule fires independently on two 1-day leave requests; trimmed_duration accumulates.

        User requests two separate full-day leaves: Monday (Jan 3) and Tuesday (Jan 4).
        Calendar: 8 scheduled hours per day (08:00-12:00 + 13:00-17:00, lunch 12:00-13:00).
        Rule threshold expected_hours=7: pipeline clips to 8 scheduled hours, excess = 8-7 = 1h.
          each day: source trimmed to 7 scheduled hours (08:00-16:00, covering 4h+3h),
                    output created for 16:00-17:00 (1h scheduled, last hour of afternoon).

        Without fix: 7h rounds DOWN to 0 on each day -> SRCLV 0 days.
        With fix:    7h trimmed -> exact 0.875d per day -> SRCLV 14h = 1.75 days total.
                     1h output -> exact 0.125d per day -> OUTLV  2h = 0.25 days total.
        """
        self.env['hr.time.rule'].create({
            'name': 'Split at 7 scheduled hours',
            'condition_work_entry_type_ids': [(4, self.source_wet.id)],
            'work_entry_type_id': self.output_wet.id,
            'working_hours_mode': 'day',
            'expected_hours': 7.0,
        })
        self._make_leave(date(2022, 1, 3))  # Mon = separate 1-day request
        self._make_leave(date(2022, 1, 4))  # Tue = separate 1-day request

        payslip = self._make_payslip()

        src_line = payslip.worked_days_line_ids.filtered(
            lambda l: l.work_entry_type_id == self.source_wet)
        out_line = payslip.worked_days_line_ids.filtered(
            lambda l: l.work_entry_type_id == self.output_wet)

        self.assertTrue(src_line)
        self.assertTrue(out_line)

        # each 1-day leave: 7h trimmed -> 0.875d; 2 leaves -> 14h = 1.75d
        self.assertAlmostEqual(src_line.number_of_hours, 14.0, places=5,
            msg="2 x 7h trimmed = 14h source")
        self.assertAlmostEqual(src_line.number_of_days, 1.75, places=5,
            msg="14h trimmed (is_time_rule_trimmed) -> exact 1.75 days, not rounded to 0")
        # each 1-day leave: 1h output -> 0.125d; 2 leaves -> 2h = 0.25d
        self.assertAlmostEqual(out_line.number_of_hours, 2.0, places=5,
            msg="2 x 1h output = 2h")
        self.assertAlmostEqual(out_line.number_of_days, 0.25, places=5,
            msg="2h output (source_leave_id set) -> exact 0.25 days, not rounded to 0")

    def test_split_three_days_accumulates(self):
        """Rule fires on three separate full-day leave requests; trimmed_duration accumulates.

        User requests three separate 1-day leaves: Mon, Tue, Wed (Jan 3-5).
        Rule splits each at 4h (trim at 12:00): source 4h + output 4h per day.
        """
        self.env['hr.time.rule'].create({
            'name': 'Split at 4h',
            'condition_work_entry_type_ids': [(4, self.source_wet.id)],
            'work_entry_type_id': self.output_wet.id,
            'working_hours_mode': 'day',
            'expected_hours': 4.0,
        })
        for day in [3, 4, 5]:  # Mon, Tue, Wed
            self._make_leave(date(2022, 1, day))

        payslip = self._make_payslip()

        src_line = payslip.worked_days_line_ids.filtered(
            lambda l: l.work_entry_type_id == self.source_wet)
        out_line = payslip.worked_days_line_ids.filtered(
            lambda l: l.work_entry_type_id == self.output_wet)

        self.assertTrue(src_line)
        self.assertTrue(out_line)
        self.assertAlmostEqual(src_line.number_of_hours, 12.0, places=5)
        self.assertAlmostEqual(src_line.number_of_days, 1.5, places=5,
            msg="3 x 4h trimmed = 1.5 days exact (no _round_days)")
        self.assertAlmostEqual(out_line.number_of_hours, 12.0, places=5)
        self.assertAlmostEqual(out_line.number_of_days, 1.5, places=5,
            msg="3 x 4h output (source_leave_id set) = 1.5 days exact")

    def test_sequential_two_rules_both_exact(self):
        """R1 splits SRCLV at 4h wall-clock; R2 splits the R1 output at 2h wall-clock.

        User requests one full day (Jan 3, Monday).  Pipeline:
          R1 (expected_hours=4): SRCLV trimmed to 08:00-12:00 (4h sched); OUTLV1 12:00-17:00.
          R2 (expected_hours=2, conditions on OUTLV): OUTLV1 trimmed to 12:00-14:00.
            12:00-14:00 scheduled = 0h lunch + 1h (13:00-14:00) = 1h.
          OUTLV2 created for 14:00-17:00 = 3h scheduled.

        All three leaves must produce non-zero exact days:
          SRCLV 4h -> 0.5d, OUTLV1 1h -> 0.125d, OUTLV2 3h -> 0.375d.
        Total = 8h = 1.0 day (the original full day).
        """
        outlv2 = self.env['hr.work.entry.type'].create({
            'name': 'Output Leave 2',
            'code': 'OUTLV2',
            'request_unit': 'day',
            'requires_allocation': False,
            'count_as': 'absence',
            'leave_validation_type': 'no_validation',
        })
        self.env['hr.time.rule'].create({
            'name': 'R1: Split SRCLV at 4h',
            'sequence': 10,
            'condition_work_entry_type_ids': [(4, self.source_wet.id)],
            'work_entry_type_id': self.output_wet.id,
            'working_hours_mode': 'day',
            'expected_hours': 4.0,
        })
        self.env['hr.time.rule'].create({
            'name': 'R2: Split OUTLV at 2h',
            'sequence': 20,
            'condition_work_entry_type_ids': [(4, self.output_wet.id)],
            'work_entry_type_id': outlv2.id,
            'working_hours_mode': 'day',
            'expected_hours': 2.0,
        })
        self._make_leave(date(2022, 1, 3))  # Mon

        payslip = self._make_payslip()

        src_line = payslip.worked_days_line_ids.filtered(
            lambda l: l.work_entry_type_id == self.source_wet)
        outlv1_line = payslip.worked_days_line_ids.filtered(
            lambda l: l.work_entry_type_id == self.output_wet)
        outlv2_line = payslip.worked_days_line_ids.filtered(
            lambda l: l.work_entry_type_id == outlv2)

        self.assertTrue(src_line, "SRCLV line must exist")
        self.assertTrue(outlv1_line, "OUTLV1 line must exist after R1 trim")
        self.assertTrue(outlv2_line, "OUTLV2 line must exist after R2 trim")

        self.assertAlmostEqual(src_line.number_of_hours, 4.0, places=5)
        self.assertAlmostEqual(src_line.number_of_days, 0.5, places=5,
            msg="SRCLV 4h trimmed -> 0.5 days (not 0)")

        # three leaves must sum to the original 8h
        total_hours = (src_line.number_of_hours
                       + (outlv1_line.number_of_hours or 0.0)
                       + outlv2_line.number_of_hours)
        self.assertAlmostEqual(total_hours, 8.0, places=5,
            msg="SRCLV + OUTLV1 + OUTLV2 must sum to the original 8h")

        # no line that has hours should show 0 days
        for line, name in [(src_line, 'SRCLV'), (outlv1_line, 'OUTLV1'), (outlv2_line, 'OUTLV2')]:
            if line.number_of_hours > 0:
                self.assertGreater(line.number_of_days, 0.0,
                    msg=f"{name} has {line.number_of_hours}h but 0 days = must be exact fraction")

    def test_full_reclassify_no_threshold(self):
        """Rule with expected_hours=0: the entire leave is 'excess'; source converted in-place.
        Expected payslip: OUTLV 8h = 1.0 day.
        """
        self.env['hr.time.rule'].create({
            'name': 'Full reclassify (0h threshold)',
            'condition_work_entry_type_ids': [(4, self.source_wet.id)],
            'work_entry_type_id': self.output_wet.id,
            'working_hours_mode': 'day',
            'expected_hours': 0.0,
        })
        self._make_leave(date(2022, 1, 3))

        payslip = self._make_payslip()

        out_line = payslip.worked_days_line_ids.filtered(
            lambda l: l.work_entry_type_id == self.output_wet)

        self.assertTrue(out_line, "output WET must appear after full reclassification")
        self.assertAlmostEqual(out_line.number_of_hours, 8.0, places=5)
        self.assertAlmostEqual(out_line.number_of_days, 1.0, places=5,
            msg="8h fully-reclassified output must give 1.0 day exactly")

    def test_output_small_fraction_not_zeroed(self):
        """Small output fraction (1h = 0.125 days) must not be zeroed by _round_days.

        User requests one full day (Jan 3, Monday).  Calendar: 8 scheduled hours.
        Rule threshold expected_hours=7: pipeline clips absence to 8 scheduled hours,
        excess = 8 - 7 = 1h -> output 16:00-17:00.  Source trimmed to 7 scheduled hours.
        """
        self.env['hr.time.rule'].create({
            'name': 'Split at 7 scheduled hours',
            'condition_work_entry_type_ids': [(4, self.source_wet.id)],
            'work_entry_type_id': self.output_wet.id,
            'working_hours_mode': 'day',
            'expected_hours': 7.0,
        })
        self._make_leave(date(2022, 1, 3))  # Mon

        payslip = self._make_payslip()

        src_line = payslip.worked_days_line_ids.filtered(
            lambda l: l.work_entry_type_id == self.source_wet)
        out_line = payslip.worked_days_line_ids.filtered(
            lambda l: l.work_entry_type_id == self.output_wet)

        self.assertTrue(src_line, "SRCLV line must exist")
        self.assertTrue(out_line, "OUTLV line must exist (even for small output fraction)")

        # source: 7 scheduled hours (4h morning 08:00-12:00 + 3h afternoon 13:00-16:00)
        self.assertAlmostEqual(src_line.number_of_hours, 7.0, places=5,
            msg="source: 7 scheduled hours (8 total - 1h excess)")
        self.assertAlmostEqual(src_line.number_of_days, 0.875, places=5,
            msg="7h trimmed source -> 0.875 days exact (not 0)")

        # output: 16:00-17:00 = 1h scheduled
        self.assertAlmostEqual(out_line.number_of_hours, 1.0, places=5,
            msg="output: 16:00-17:00 = 1h scheduled (8h sched - 7h threshold)")
        self.assertAlmostEqual(out_line.number_of_days, 0.125, places=5,
            msg="1h output (source_leave_id set) -> 0.125 days exact (not _round_days DOWN to 0)")

    def test_deficit_rule_gap_in_calendar_hours(self):
        """Deficit rule: output leave must land within scheduled calendar slots, not at end-of-day.

        User requests a 3h hour-unit leave Monday morning (08:00-11:00).
        Rule fires because 3h < 8h (threshold_operator='less_than', expected_hours=8.0).
        Deficit = 5h.

            available = schedule (leave already subtracted) = [11:00-12:00, 13:00-17:00];
            gap = available - total_worked = exactly 5h within calendar hours;
            GAPLV placed at [11:00-12:00, 13:00-17:00] -> 5h = 0.625 days exact via source_leave_id.

        SRCLV (hour-unit, 3h, not trimmed): 3h / 8h = 0.375 days.
          For request_unit='hour' _round_days returns days unchanged, so 0.375 stays.
        GAPLV (5h, source_leave_id set): 0.625 days exact (not rounded).
        """
        hour_wet = self.env['hr.work.entry.type'].create({
            'name': 'Hour Leave',
            'code': 'HRSLV',
            'request_unit': 'hour',
            'requires_allocation': False,
            'count_as': 'absence',
            'leave_validation_type': 'no_validation',
        })
        gap_wet = self.env['hr.work.entry.type'].create({
            'name': 'Gap Leave',
            'code': 'GAPLV',
            'request_unit': 'day',
            'requires_allocation': False,
            'count_as': 'absence',
            'leave_validation_type': 'no_validation',
        })
        self.env['hr.time.rule'].create({
            'name': 'Deficit fill (< 8h taken)',
            'condition_work_entry_type_ids': [(4, hour_wet.id)],
            'work_entry_type_id': gap_wet.id,
            'working_hours_mode': 'day',
            'threshold_operator': 'less_than',
            'expected_hours': 8.0,
        })
        # user requests 3h hour-type leave Monday morning
        self._make_hour_leave(date(2022, 1, 3), hour_from=8.0, hour_to=11.0, wet=hour_wet)

        payslip = self._make_payslip()

        src_line = payslip.worked_days_line_ids.filtered(
            lambda l: l.work_entry_type_id == hour_wet)
        gap_line = payslip.worked_days_line_ids.filtered(
            lambda l: l.work_entry_type_id == gap_wet)

        # source: 3h hour-unit leave = _round_days returns days as-is for hour WETs
        self.assertTrue(src_line, "HRSLV line must exist")
        self.assertAlmostEqual(src_line.number_of_hours, 3.0, places=5)
        self.assertAlmostEqual(src_line.number_of_days, 0.375, places=5,
            msg="3h hour-unit source -> 0.375 days (hour-unit, no _round_days snap)")

        self.assertTrue(gap_line,
            "GAPLV line must appear = deficit output must land within calendar hours "
            "([11:00-12:00, 13:00-17:00]), not at end-of-day")
        self.assertAlmostEqual(gap_line.number_of_hours, 5.0, places=5,
            msg="GAPLV: 1h (11:00-12:00) + 4h (13:00-17:00) = 5h remaining schedule")
        self.assertAlmostEqual(gap_line.number_of_days, 0.625, places=5,
            msg="5h gap (source_leave_id set) -> exact 0.625 days, no _round_days")

    def test_source_and_output_different_wets_sum_to_one_day(self):
        """Source and output belong to different WETs; their days must sum to the original 1 day.

        User requests one full day (Jan 3).  Rule splits at 4h wall-clock (trim at 12:00):
          SRCLV 4h (is_time_rule_trimmed) -> 0.5 days exact.
          OUTLV 4h (source_leave_id set) -> 0.5 days exact.
        Both bypass _round_days; together they equal the original 1.0 day.
        """
        self.env['hr.time.rule'].create({
            'name': 'Split at 4h',
            'condition_work_entry_type_ids': [(4, self.source_wet.id)],
            'work_entry_type_id': self.output_wet.id,
            'working_hours_mode': 'day',
            'expected_hours': 4.0,
        })
        self._make_leave(date(2022, 1, 3))  # Mon

        payslip = self._make_payslip()

        src_line = payslip.worked_days_line_ids.filtered(
            lambda l: l.work_entry_type_id == self.source_wet)
        out_line = payslip.worked_days_line_ids.filtered(
            lambda l: l.work_entry_type_id == self.output_wet)

        self.assertTrue(src_line)
        self.assertTrue(out_line)
        self.assertAlmostEqual(src_line.number_of_days, 0.5, places=5)
        self.assertAlmostEqual(out_line.number_of_days, 0.5, places=5)
        self.assertAlmostEqual(
            src_line.number_of_days + out_line.number_of_days, 1.0, places=5,
            msg="split source + output must sum to the original 1.0 day")

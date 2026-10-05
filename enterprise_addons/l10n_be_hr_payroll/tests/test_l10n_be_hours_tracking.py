# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.exceptions import ValidationError
from odoo.fields import Command
from odoo.tests import tagged

from .common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestL10nBeHoursTracking(TestPayrollCommon):
    """The secondary hour counter tracked alongside the day counter for the 3 Belgian
    legal-leave types: only the day counter blocks, the hour counter only warns."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.legal_leave_type = cls.env.ref('hr_work_entry.be_work_entry_type_legal_leave')
        # Mon-Thu 8h/day, Fri 6h/day (38h/week): the example from the spec.
        cls.calendar_8_8_8_8_6 = cls.env['resource.calendar'].create({
            'name': 'Calendar (8-8-8-8-6)',
            'company_id': cls.belgian_company.id,
            'full_time_required_hours': 38,
            'attendance_ids': [
                Command.create({'dayofweek': str(day), 'hour_from': 8, 'hour_to': 12})
                for day in range(5)
            ] + [
                Command.create({'dayofweek': str(day), 'hour_from': 13, 'hour_to': 17})
                for day in range(4)
            ] + [
                Command.create({'dayofweek': '4', 'hour_from': 13, 'hour_to': 15}),
            ],
        })
        cls.employee = cls.create_employee({
            'name': 'Nathalie',
            'resource_calendar_id': cls.calendar_8_8_8_8_6.id,
        })
        # Every day is the same length: days * hours/day always matches the real hour balance.
        cls.calendar_uniform = cls.env['resource.calendar'].create({
            'name': 'Calendar (Uniform 7.6h/day)',
            'company_id': cls.belgian_company.id,
            'full_time_required_hours': 38,
            'attendance_ids': [
                Command.create({'dayofweek': str(day), 'hour_from': 8, 'hour_to': 15.6})
                for day in range(5)
            ],
        })
        cls.employee_uniform = cls.create_employee({
            'name': 'Uniform Schedule',
            'resource_calendar_id': cls.calendar_uniform.id,
        })

    def _create_allocation(self, employee, work_entry_type, number_of_days, number_of_hours, date_from=None, date_to=None):
        allocation = self.env['hr.leave.allocation'].create({
            'name': 'Allocation',
            'employee_id': employee.id,
            'work_entry_type_id': work_entry_type.id,
            'number_of_days': number_of_days,
            'number_of_hours': number_of_hours,
            'date_from': date_from or date(2026, 1, 1),
            'date_to': date_to,
        })
        allocation.action_approve()
        return allocation

    def _create_leave(self, employee, work_entry_type, date_from, date_to, pending=False):
        leave = self.env['hr.leave'].with_context(leave_fast_create=pending).create({
            'name': 'Leave',
            'employee_id': employee.id,
            'work_entry_type_id': work_entry_type.id,
            'request_date_from': date_from,
            'request_date_to': date_to,
        })
        # _compute_leaves doesn't depend on hr.leave (fetched via search, not a related field).
        self.env['hr.leave.allocation'].invalidate_model()
        return leave

    def test_dual_reduction_full_day_vs_short_friday(self):
        """A full day off on a normal (8h) day consumes 1 day and 8 hours; a full day off on
        the short Friday (6h) consumes 1 day but only 6 hours -- both reduce the day counter
        by exactly 1, but reduce the hour counter by the real number of hours from the WS."""
        allocation = self._create_allocation(self.employee, self.legal_leave_type, 20, 200)

        monday_leave = self._create_leave(self.employee, self.legal_leave_type, date(2026, 1, 5), date(2026, 1, 5))
        self.assertEqual(monday_leave.number_of_days, 1)
        self.assertEqual(monday_leave.number_of_hours, 8)
        monday_leave.action_approve()
        self.env['hr.leave.allocation'].invalidate_model()

        self.assertEqual(allocation.virtual_remaining_leaves, 19)
        self.assertEqual(allocation.l10n_be_hours_taken, 8)
        self.assertEqual(allocation.l10n_be_hours_remaining, 192)

        friday_leave = self._create_leave(self.employee, self.legal_leave_type, date(2026, 1, 9), date(2026, 1, 9))
        self.assertEqual(friday_leave.number_of_days, 1)
        self.assertEqual(friday_leave.number_of_hours, 6)
        friday_leave.action_approve()
        self.env['hr.leave.allocation'].invalidate_model()

        self.assertEqual(allocation.virtual_remaining_leaves, 18)
        self.assertEqual(allocation.l10n_be_hours_taken, 14)
        self.assertEqual(allocation.l10n_be_hours_remaining, 186)

    def test_block_when_days_exhausted_even_with_hours_remaining(self):
        """Edge case: 0 days left, hours still remaining, uom='day' (the type's own unit): we
        block -- the hour counter is never consulted for blocking."""
        allocation = self._create_allocation(self.employee, self.legal_leave_type, 1, 100)
        monday_leave = self._create_leave(self.employee, self.legal_leave_type, date(2026, 1, 5), date(2026, 1, 5))
        monday_leave.action_approve()
        self.env['hr.leave.allocation'].invalidate_model()

        self.assertEqual(allocation.virtual_remaining_leaves, 0)
        self.assertGreater(allocation.l10n_be_hours_remaining, 0)

        with self.assertRaises(ValidationError):
            self._create_leave(self.employee, self.legal_leave_type, date(2026, 1, 6), date(2026, 1, 6))

    def test_allow_and_warn_when_hours_go_negative(self):
        """Edge case: days still remaining, uom='day': the leave is allowed (the day counter is
        fine), but the now-negative hour balance is warned about -- on the allocation and, while
        the leave itself is still pending, on the leave. Approving (or refusing) it clears the
        warning from the leave, since it's no longer pending."""
        allocation = self._create_allocation(self.employee, self.legal_leave_type, 5, 1)
        monday_leave = self._create_leave(self.employee, self.legal_leave_type, date(2026, 1, 5), date(2026, 1, 5), pending=True)

        # Even before approval, the pending leave already counts against the virtual balance.
        self.assertEqual(allocation.virtual_remaining_leaves, 4)
        self.assertEqual(allocation.l10n_be_hours_remaining, 1 - 8)
        self.assertIn('hour', allocation.l10n_be_negative_balance_warning)

        # issues carries the specific per-allocation message (not the warning's generic
        # description), matching hr_payroll_warning_l10n_be_negative_leave_balance's danger level.
        self.assertIn(allocation.l10n_be_negative_balance_warning, [issue['message'] for issue in monday_leave.issues.values()])
        self.assertIn('danger', [issue['level'] for issue in monday_leave.issues.values()])

        monday_leave.action_approve()  # must not raise: the day counter is fine
        self.env['hr.leave.allocation'].invalidate_model()

        # Now validated, it's no longer "pending": the warning no longer applies to it.
        self.assertFalse(monday_leave.issues)

    def test_warning_scoped_to_matching_type_only(self):
        """The negative-balance warning on a leave only applies when that same leave's own work
        entry type is the one with the negative balance -- a different type's pending leave for
        the same employee (even on dates within the same negative allocation's validity window)
        must not pick it up. Distinct dates per leave: an employee can't have two overlapping
        time off requests regardless of type, so same-day reuse isn't an option here."""
        self._create_allocation(self.employee, self.legal_leave_type, 5, 1)
        monday_leave = self._create_leave(self.employee, self.legal_leave_type, date(2026, 1, 5), date(2026, 1, 5), pending=True)
        self.assertTrue(monday_leave.issues, "legal_leave_type is negative: this leave should be warned about")

        # Another tracked type (N-1), same employee, its own allocation is fine: must not
        # inherit legal_leave_type's warning even though both allocations are active that week.
        postponed_n1 = self.env.ref('hr_work_entry.l10n_be_work_entry_type_postponed_paid_time_off_n1')
        self._create_allocation(self.employee, postponed_n1, 5, 100, date_from=date(2026, 1, 1))
        n1_leave = self._create_leave(self.employee, postponed_n1, date(2026, 1, 6), date(2026, 1, 6), pending=True)
        self.assertFalse(n1_leave.issues)

        # An untracked type, same employee: never even considered.
        self._create_allocation(self.employee, self.holiday_work_entry_types, 5, 40)
        untracked_leave = self._create_leave(self.employee, self.holiday_work_entry_types, date(2026, 1, 7), date(2026, 1, 7), pending=True)
        self.assertFalse(untracked_leave.issues)

    def test_untracked_type_not_affected(self):
        """A non-tracked BE work entry type never gets the secondary counter/warning."""
        allocation = self._create_allocation(self.employee, self.holiday_work_entry_types, 5, 40)
        self.assertFalse(allocation.l10n_be_hours_tracked)
        self.assertEqual(allocation.l10n_be_hours_taken, 0)
        self.assertFalse(allocation.l10n_be_negative_balance_warning)

    def test_fifo_split_across_multiple_allocations(self):
        """With two allocations of the same tracked type, the hour counter is split across
        them in the same FIFO order (soonest-expiring first) as the day counter."""
        soon_expiring = self._create_allocation(
            self.employee, self.legal_leave_type, 1, 8,
            date_from=date(2025, 1, 1), date_to=date(2026, 1, 31))
        later = self._create_allocation(self.employee, self.legal_leave_type, 5, 100, date_from=date(2026, 1, 1))

        leave = self._create_leave(self.employee, self.legal_leave_type, date(2026, 1, 5), date(2026, 1, 6))
        self.assertEqual(leave.number_of_days, 2)
        leave.action_approve()
        self.env['hr.leave.allocation'].invalidate_model()

        self.assertEqual(soon_expiring.virtual_remaining_leaves, 0)
        self.assertEqual(soon_expiring.l10n_be_hours_remaining, 0)
        self.assertEqual(later.virtual_remaining_leaves, 5 - 1)
        self.assertEqual(later.l10n_be_hours_remaining, 100 - 8)

    def test_number_of_hours_follows_days_when_not_explicit(self):
        """user puts 20 days -> computes hours to 152h, then user corrects days to 10
        days -> number_of_hours must follow to 76h, not stay still at 152h"""
        allocation = self.env['hr.leave.allocation'].create({
            'name': 'Allocation',
            'employee_id': self.employee_uniform.id,
            'work_entry_type_id': self.legal_leave_type.id,
            'number_of_days': 20,
            'date_from': date(2026, 1, 1),
        })
        self.assertEqual(allocation.number_of_hours, 20 * 7.6, "left implicit, so it auto-computes from days")

        allocation.write({'number_of_days': 10})
        self.assertEqual(allocation.number_of_hours, 10 * 7.6)

        allocation.write({'number_of_days': 5, 'number_of_hours': 123.4})
        self.assertEqual(allocation.number_of_hours, 123.4)

        allocation.write({'number_of_days': 8})
        self.assertEqual(allocation.number_of_hours, 8 * 7.6)

    def _get_allocation_data_info(self, employee, work_entry_type, target_date):
        result = work_entry_type.get_allocation_data(employee, target_date=target_date)
        _name, info, _requires_allocation, _wet_id = result[employee][0]
        return info

    def test_get_allocation_data_no_deviation(self):
        """get_allocation_data (the Time Off Dashboard/Summary panel's data source) does not
        surface the exact hour balance when it agrees with the day-count estimate (days *
        average hours/day) -- nothing to call out."""
        self._create_allocation(self.employee_uniform, self.legal_leave_type, 20, 20 * 7.6)

        info = self._get_allocation_data_info(self.employee_uniform, self.legal_leave_type, date(2026, 1, 10))
        self.assertNotIn('l10n_be_hours_remaining', info)

    def test_get_allocation_data_shows_deviation(self):
        """A short-Friday leave consumes fewer hours than the average hours/day, so the exact
        hour balance disagrees with the day-count estimate -- get_allocation_data surfaces it."""
        allocation = self._create_allocation(self.employee, self.legal_leave_type, 20, 20 * 7.6)
        friday_leave = self._create_leave(self.employee, self.legal_leave_type, date(2026, 1, 9), date(2026, 1, 9))
        friday_leave.action_approve()
        self.env['hr.leave.allocation'].invalidate_model()

        info = self._get_allocation_data_info(self.employee, self.legal_leave_type, date(2026, 1, 10))
        self.assertIn('l10n_be_hours_remaining', info)
        self.assertEqual(info['l10n_be_hours_remaining'], allocation.l10n_be_hours_remaining)

    def test_get_allocation_data_negative_balance_warning(self):
        """get_allocation_data (the Time Off Dashboard card's data source) also surfaces the
        negative-balance warning message, for the card's own warning indicator/popover."""
        allocation = self._create_allocation(self.employee, self.legal_leave_type, 5, 1)
        self._create_leave(self.employee, self.legal_leave_type, date(2026, 1, 5), date(2026, 1, 5))

        info = self._get_allocation_data_info(self.employee, self.legal_leave_type, date(2026, 1, 10))
        self.assertIn('l10n_be_negative_balance_warning', info)
        self.assertEqual(info['l10n_be_negative_balance_warning'], allocation.l10n_be_negative_balance_warning)

    def test_get_allocation_data_no_warning_when_balance_ok(self):
        """No negative-balance key at all on the dashboard card's data when nothing is wrong."""
        self._create_allocation(self.employee, self.legal_leave_type, 20, 200)
        info = self._get_allocation_data_info(self.employee, self.legal_leave_type, date(2026, 1, 10))
        self.assertNotIn('l10n_be_negative_balance_warning', info)

    def test_get_allocation_data_untracked_type_not_affected(self):
        """A non-tracked BE work entry type is never surfaced, even with an irregular schedule."""
        self._create_allocation(self.employee, self.holiday_work_entry_types, 5, 40)
        info = self._get_allocation_data_info(self.employee, self.holiday_work_entry_types, date(2026, 1, 10))
        self.assertNotIn('l10n_be_hours_remaining', info)
        self.assertNotIn('l10n_be_negative_balance_warning', info)

# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import timezone
from dateutil.relativedelta import relativedelta

from odoo.exceptions import UserError

from odoo import models


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    # ----------------
    # Business methods
    # ----------------

    def _action_validate(self, check_state=True):
        res = super()._action_validate(check_state=check_state)
        self._l10n_hk_check_consecutive_leaves()
        return res

    def _l10n_hk_check_consecutive_leaves(self):
        """
        Check that the total days of consecutive leaves are limited by the setting of the work entry type.
        When limiting the work entry type using 'Up To', we will check previous/next leaves as well to ensure we don't allow
        bypassing the limit by booking consecutive leaves of a same work entry type.
        """
        for leave in self:
            limit_type = leave.work_entry_type_id.l10n_hk_consecutive_days_limit_type
            if not limit_type:
                continue
            limit = leave.work_entry_type_id.l10n_hk_consecutive_days_limit
            if limit_type == 'from' and leave.number_of_days < limit:
                raise UserError(leave.env._("You cannot take less than %(limit)s consecutive days of %(leave_name)s.", limit=limit, leave_name=leave.work_entry_type_id.name))
            if limit_type == 'to':
                consecutive_leave_days = leave._get_consecutive_leave_days()
                if (leave.number_of_days + consecutive_leave_days) > limit:
                    raise UserError(leave.env._("You cannot take more than %(limit)s consecutive days of %(leave_name)s.", limit=limit, leave_name=leave.work_entry_type_id.name))

    def _get_consecutive_leave_days(self):
        """
        Returns to sum of consecutive days of leave of the same work entry type before and after self.
        We only check 10 days in both directions, which should be enough to detect misusage of the system.
        """
        self.ensure_one()
        employee = self.employee_id
        work_entry_type = self.work_entry_type_id
        # Start by looking backward and count the amount of consecutive days.
        prior_days = 0.0
        current_start_boundary = self.date_from
        previous_leaves = self.env['hr.leave'].search([
            ('employee_id', '=', employee.id),
            ('work_entry_type_id', '=', work_entry_type.id),
            ('state', '=', 'validate'),
            ('date_to', '<', self.date_from),
            ('date_to', '>', self.date_from - relativedelta(days=10)),
        ], order='date_to desc')
        for leave in previous_leaves:
            has_work_in_gap = self._check_work_interval_between_dates_hk(
                leave.date_to, current_start_boundary, employee
            )
            if has_work_in_gap:
                break
            prior_days += leave.number_of_days
            current_start_boundary = leave.date_from
        # Then, we look forward and repeat the process.
        next_days = 0.0
        current_end_boundary = self.date_to
        next_leaves = self.env['hr.leave'].search([
            ('employee_id', '=', employee.id),
            ('work_entry_type_id', '=', work_entry_type.id),
            ('state', '=', 'validate'),
            ('date_from', '>', self.date_to),
            ('date_from', '<', self.date_to + relativedelta(days=10)),
        ], order='date_from asc')
        for leave in next_leaves:
            has_work_in_gap = self._check_work_interval_between_dates_hk(
                current_end_boundary, leave.date_from, employee
            )
            if has_work_in_gap:
                break

            next_days += leave.number_of_days
            current_end_boundary = leave.date_to

        return prior_days + next_days

    def _check_work_interval_between_dates_hk(self, date_from, date_to, employee):
        """
        Check if there is a work interval between two dates for an employee
        Returns true if there is a period where the employee worked
        or had a leave borne by the employee (e.g. not a public holiday)
        between date_from and date_to
        """
        if date_from >= date_to:
            return False

        calendar = employee._get_calendars()[employee.id]
        dt_from = date_from.replace(tzinfo=timezone.utc)
        dt_to = date_to.replace(tzinfo=timezone.utc)
        resource_per_tz = employee._get_resources_per_tz(date_from)

        # Make sure to ignore weekends entries.
        attendance_intervals = calendar._attendance_intervals_batch(dt_from, dt_to, resource_per_tz,
            domain=[
                '|',
                    ('work_entry_type_id', '=', False),
                    ('work_entry_type_id.code', '!=', 'HKLEAVE600'),
            ]
        )
        leave_intervals = calendar._leave_intervals_batch(dt_from, dt_to, resource_per_tz)

        employee_leave_intervals = leave_intervals[employee.resource_id.id]
        # remove holidays taken by the user from employee_leave_intervals
        employee_leave_intervals -= [
            (start, end, leave)
            for start, end, leave in employee_leave_intervals
            if leave.holiday_id
        ]
        attendance_intervals = attendance_intervals[employee.resource_id.id] - employee_leave_intervals
        return bool(attendance_intervals)

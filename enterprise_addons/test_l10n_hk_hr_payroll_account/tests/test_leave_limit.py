# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import date

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import TestL10NHkHrPayrollAccountCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestLeaveLimit(TestL10NHkHrPayrollAccountCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids |= cls.env.ref('hr.group_hr_manager') + cls.env.ref("hr_holidays.group_hr_holidays_manager")

    def test_from_limit(self):
        leave_type = self.env['hr.work.entry.type'].create({
            'name': 'HR Leave',
            'code': 'HRL',
            'requires_allocation': False,
            'request_unit': 'half_day',
            'country_id': self.env.ref('base.hk').id,
            'allocation_validation_type': 'hr',
            'leave_validation_type': 'hr',
            'l10n_hk_consecutive_days_limit_type': 'from',
            'l10n_hk_consecutive_days_limit': 3,
        })
        with self.assertRaises(UserError):
            self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'work_entry_type_id': leave_type.id,
            'request_date_from': date(2025, 12, 1),
            'request_date_to': date(2025, 12, 2),
        })
        self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'work_entry_type_id': leave_type.id,
            'request_date_from': date(2025, 12, 1),
            'request_date_to': date(2025, 12, 3),
        })

    def test_up_to_limit(self):
        leave_type = self.env['hr.work.entry.type'].create({
            'name': 'HR Leave',
            'code': 'HRL',
            'requires_allocation': False,
            'request_unit': 'half_day',
            'country_id': self.env.ref('base.hk').id,
            'allocation_validation_type': 'hr',
            'leave_validation_type': 'hr',
            'l10n_hk_consecutive_days_limit_type': 'to',
            'l10n_hk_consecutive_days_limit': 3,
        })
        with self.assertRaises(UserError):
            self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'work_entry_type_id': leave_type.id,
            'request_date_from': date(2025, 12, 1),
            'request_date_to': date(2025, 12, 4),
        })
        self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'work_entry_type_id': leave_type.id,
            'request_date_from': date(2025, 12, 1),
            'request_date_to': date(2025, 12, 3),
        })

    def test_no_limit(self):
        leave_type = self.env['hr.work.entry.type'].create({
            'name': 'HR Leave',
            'code': 'HRL',
            'requires_allocation': False,
            'request_unit': 'half_day',
            'country_id': self.env.ref('base.hk').id,
            'allocation_validation_type': 'hr',
            'leave_validation_type': 'hr',
            'l10n_hk_consecutive_days_limit_type': False,
            'l10n_hk_consecutive_days_limit': 0,
        })
        self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'work_entry_type_id': leave_type.id,
            'request_date_from': date(2025, 12, 1),
            'request_date_to': date(2025, 12, 4),
        })

    def test_up_to_limit_consecutive_leaves(self):
        """ Test a leave with a limit up to 3 days, where we book two separate consecutive leaves. """
        leave_type = self.env['hr.work.entry.type'].create({
            'name': 'HR Leave',
            'code': 'HRL',
            'requires_allocation': False,
            'request_unit': 'half_day',
            'country_id': self.env.ref('base.hk').id,
            'allocation_validation_type': 'hr',
            'leave_validation_type': 'hr',
            'l10n_hk_consecutive_days_limit_type': 'to',
            'l10n_hk_consecutive_days_limit': 3,
        })
        # First leave of two days.
        self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'work_entry_type_id': leave_type.id,
            'request_date_from': date(2025, 12, 1),
            'request_date_to': date(2025, 12, 2),
        })
        # Second leave, consecutive, of two days (will be blocked)
        with self.assertRaises(UserError):
            self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'work_entry_type_id': leave_type.id,
            'request_date_from': date(2025, 12, 3),
            'request_date_to': date(2025, 12, 4),
        })
        self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'work_entry_type_id': leave_type.id,
            'request_date_from': date(2025, 12, 3),
            'request_date_to': date(2025, 12, 3),
        })

    def test_up_to_limit_non_consecutive_leaves(self):
        """ Test a leave with a limit up to 3 days, where we book two separate non-consecutive leaves. """
        leave_type = self.env['hr.work.entry.type'].create({
            'name': 'HR Leave',
            'code': 'HRL',
            'requires_allocation': False,
            'request_unit': 'half_day',
            'country_id': self.env.ref('base.hk').id,
            'allocation_validation_type': 'hr',
            'leave_validation_type': 'hr',
            'l10n_hk_consecutive_days_limit_type': 'to',
            'l10n_hk_consecutive_days_limit': 3,
        })
        # First leave of two days.
        self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'work_entry_type_id': leave_type.id,
            'request_date_from': date(2025, 12, 1),
            'request_date_to': date(2025, 12, 2),
        })
        # Second leave of two days, a few days later.
        # As it is not consecutive, it will be allowed
        self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'work_entry_type_id': leave_type.id,
            'request_date_from': date(2025, 12, 4),
            'request_date_to': date(2025, 12, 5),
        })

    def test_up_to_limit_consecutive_leaves_with_weekend(self):
        """ Test a leave with a limit up to 3 days, where we book two separate consecutive leaves with a weekend inbetween. """
        leave_type = self.env['hr.work.entry.type'].create({
            'name': 'HR Leave',
            'code': 'HRL',
            'requires_allocation': False,
            'request_unit': 'half_day',
            'country_id': self.env.ref('base.hk').id,
            'allocation_validation_type': 'hr',
            'leave_validation_type': 'hr',
            'l10n_hk_consecutive_days_limit_type': 'to',
            'l10n_hk_consecutive_days_limit': 3,
        })
        # First leave of two days.
        self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'work_entry_type_id': leave_type.id,
            'request_date_from': date(2025, 12, 4),
            'request_date_to': date(2025, 12, 5),
        })
        # Second leave, consecutive (following the weekend), of two days (will be blocked)
        with self.assertRaises(UserError):
            self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'work_entry_type_id': leave_type.id,
            'request_date_from': date(2025, 12, 8),
            'request_date_to': date(2025, 12, 9),
        })
        self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'work_entry_type_id': leave_type.id,
            'request_date_from': date(2025, 12, 8),
            'request_date_to': date(2025, 12, 8),
        })

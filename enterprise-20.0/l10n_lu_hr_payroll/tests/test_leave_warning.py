# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from odoo.tests import tagged
from .common import TestLuPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestLeaveWarning(TestLuPayrollCommon):

    def test_no_warning_for_short_sick_leave(self):
        """ A sick leave that stays under the 77 calendar-day paid threshold should not raise any warning. """
        leave = self.env['hr.leave'].with_context(leave_fast_create=True).create({
            'employee_id': self.employee_david.id,
            'work_entry_type_id': self.env.ref('hr_work_entry.lu_work_entry_type_sick_leave').id,
            'request_date_from': date(2026, 1, 1),
            'request_date_to': date(2026, 1, 5),
        })
        self.assertFalse(any('This time off will be split into' in val['message'] for _, val in leave.issues.items()) if leave.issues else False)

    def test_warning_for_split_sick_leave(self):
        """ A sick leave crossing the 77 calendar-day threshold should warn that it will be split between
        013.00 (paid by employer) and SL_CNS (paid by CNS) once validated.
        Use leave_fast_create to inspect the warning before the automatic validation splits the leave. """
        leave = self.env['hr.leave'].with_context(leave_fast_create=True).create({
            'employee_id': self.employee_david.id,
            'work_entry_type_id': self.env.ref('hr_work_entry.lu_work_entry_type_sick_leave').id,
            'request_date_from': date(2026, 1, 1),
            'request_date_to': date(2026, 4, 3),
        })
        self.assertTrue(any('This time off will be split into' in val['message'] for _, val in leave.issues.items()))

        # Once validated, the single leave should effectively be split into two leaves matching the warning.
        leave._action_validate()
        all_leaves = self.env['hr.leave'].search(
            [('employee_id', '=', self.employee_david.id)]
        ).sorted('request_date_from')
        self.assertEqual(len(all_leaves), 2)
        self.assertEqual(all_leaves[0].work_entry_type_id.code, '013.00')
        self.assertEqual(all_leaves[1].work_entry_type_id.code, 'SL_CNS')

    def test_no_warning_for_non_sick_leave(self):
        """ The warning only applies to 013.00 (sick leave) work entry types. """
        other_work_entry_type = self.env['hr.work.entry.type'].create({
            'name': 'Other Leave',
            'code': 'OTHER',
            'requires_allocation': False,
        })
        leave = self.env['hr.leave'].with_context(leave_fast_create=True).create({
            'employee_id': self.employee_david.id,
            'work_entry_type_id': other_work_entry_type.id,
            'request_date_from': date(2026, 1, 1),
            'request_date_to': date(2026, 4, 3),
        })
        self.assertFalse(any('This time off will be split into' in val['message'] for _, val in leave.issues.items()) if leave.issues else False)

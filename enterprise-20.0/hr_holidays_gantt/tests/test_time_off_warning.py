# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime
from odoo.tests import tagged

from odoo.addons.hr_holidays.tests.common import TestHrHolidaysCommon


@tagged('at_install', '-post_install')  # LEGACY at_install
class TestHolidaysWarning(TestHrHolidaysCommon):

    def test_check_group_leaves(self):

        # Make sure we have the rights to create, validate and delete the leaves, leave types and allocations
        HrWorkEntryType = self.env['hr.work.entry.type'].with_user(self.user_hrmanager_id)

        self.holidays_type_1 = HrWorkEntryType.create({
            'name': 'NotLimitedHR',
            'code': 'NotLimitedHR',
            'requires_allocation': False,
            'leave_validation_type': 'hr',
            'unit_of_measure': 'day',
            'count_as': 'absence',
        })
        time_off_validated_1 = self.env['resource.calendar.leaves'].create({
            'name': 'Global Time Off',
            'date_from': datetime(2023, 11, 6, 0, 0, 0),
            'date_to': datetime(2023, 11, 8, 0, 0, 0),
        })
        time_off_validated_2 = self.env['resource.calendar.leaves'].create({
            'name': 'Global Time Off',
            'date_from': datetime(2023, 11, 10, 0, 0, 0),
            'date_to': datetime(2023, 11, 10, 23, 59, 59),
        })
        time_off_request = self.env['hr.leave'].create({
            'name': 'Holiday Request',
            'employee_id': self.employee_emp_id,
            'work_entry_type_id': self.holidays_type_1.id,
            'request_date_from': datetime(2023, 11, 9, 0, 0, 0),
            'request_date_to': datetime(2023, 11, 9, 23, 59, 59),
        })
        # the leaves arguments of _group_leaves function are always sorted first by type, then by chronology
        periods = self.env['hr.leave']._group_leaves([time_off_validated_1, time_off_validated_2, time_off_request],
                                                     self.employee_emp, datetime(2023, 11, 6, 0, 0, 0),
                                                     datetime(2023, 11, 10, 23, 59, 59))
        self.assertEqual(len(periods), 3, "3 periods should be found in the interval")

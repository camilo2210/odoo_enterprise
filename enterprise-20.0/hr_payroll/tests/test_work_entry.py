# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, date
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta

from odoo.tests.common import tagged
from odoo.addons.hr_payroll.tests.common import TestPayslipBase


@tagged('work_entry')
@tagged('at_install', '-post_install')  # LEGACY at_install
class TestWorkEntry(TestPayslipBase):

    @classmethod
    def setUpClass(cls):
        super(TestWorkEntry, cls).setUpClass()
        cls.tz = ZoneInfo(cls.richard_emp.tz)
        cls.start = datetime(2015, 11, 1, 1, 0, 0)
        cls.end = datetime(2015, 11, 30, 23, 59, 59)
        cls.resource_calendar_id = cls.env['resource.calendar'].create({'name': 'Zboub'})
        cls.richard_emp.version_id.write({
            'date_version': cls.start.date() - relativedelta(days=5),
            'contract_date_start': cls.start.date() - relativedelta(days=5),
            'contract_date_end': False,
            'name': 'dodo',
            'resource_calendar_id': cls.resource_calendar_id.id,
            'wage': 1000,
            'structure_type_id': cls.structure_type.id,
        })

    def test_time_normal_work_entry(self):
        # Normal attendances (global to all employees)
        work_entries_vals = self.richard_emp.version_id.generate_work_entries(self.start.date(), self.end.date())
        hours = self.richard_emp.version_id.get_work_hours(self.start.date(), self.end.date(), work_entries_vals)
        sum_hours = sum(v for k, v in hours.items() if k[0].code == "002.00")

        self.assertEqual(sum_hours, 168.0)

    def test_time_extra_work_entry(self):
        start = datetime(2015, 11, 1, 10, 0, 0)
        end = datetime(2015, 11, 1, 17, 0, 0)
        self.env['hr.leave'].create({
            'name': '1',
            'employee_id': self.richard_emp.id,
            'work_entry_type_id': self.work_entry_type.id,
            'date_from': start,
            'date_to': end,
            'request_date_from': start,
            'request_date_to': end,
            'request_hour_from': 10,
            'request_hour_to': 17,
            'number_of_days': 1,
        })

        work_entries_vals = self.richard_emp.version_id.generate_work_entries(self.start.date(), self.end.date())
        hours = self.richard_emp.version_id.get_work_hours(self.start.date(), self.end.date(), work_entries_vals)
        sum_hours = sum(v for k, v in hours.items() if k[0].id in self.work_entry_type.ids)

        self.assertEqual(sum_hours, 7.0)

    def test_edge_timezone_work_entry(self):
        hk_resource_calendar_id = self.env['resource.calendar'].create({
            'name': 'HK Calendar',
            'hours_per_day': 8,
            'attendance_ids': [(5, 0, 0),
                (0, 0, {'dayofweek': '0', 'hour_from': 7, 'hour_to': 12}),
                (0, 0, {'dayofweek': '0', 'hour_from': 13, 'hour_to': 16}),
                (0, 0, {'dayofweek': '1', 'hour_from': 7, 'hour_to': 12}),
                (0, 0, {'dayofweek': '1', 'hour_from': 13, 'hour_to': 16}),
                (0, 0, {'dayofweek': '2', 'hour_from': 7, 'hour_to': 12}),
                (0, 0, {'dayofweek': '2', 'hour_from': 13, 'hour_to': 16}),
                (0, 0, {'dayofweek': '3', 'hour_from': 7, 'hour_to': 12}),
                (0, 0, {'dayofweek': '3', 'hour_from': 13, 'hour_to': 16}),
                (0, 0, {'dayofweek': '4', 'hour_from': 7, 'hour_to': 12}),
                (0, 0, {'dayofweek': '4', 'hour_from': 13, 'hour_to': 16})
            ]
        })
        hk_employee = self.env['hr.employee'].create({
            'name': 'HK Employee',
            'tz': 'Asia/Hong_Kong',
            'date_version': date(2023, 8, 1),
            'contract_date_start': date(2023, 8, 1),
            'resource_calendar_id': hk_resource_calendar_id.id,
            'wage': 1000,
            'structure_type_id': self.structure_type.id,
        })
        self.env.company.resource_calendar_id = hk_resource_calendar_id
        work_entries_vals = hk_employee.version_id.generate_work_entries(date(2023, 8, 1), date(2023, 8, 31))
        hours = hk_employee.version_id.get_work_hours(date(2023, 8, 1), date(2023, 8, 31), work_entries_vals)
        sum_hours = sum(v for k, v in hours.items() if k[0].id in self.env.ref('hr_work_entry.us_work_entry_type_attendance').ids)
        self.assertAlmostEqual(sum_hours, 184.0, places=2)

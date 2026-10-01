# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import datetime, date

from odoo.addons.hr_payroll.tests.common import TestPayslipBase
from odoo.tests.common import tagged


@tagged('at_install', '-post_install')  # LEGACY at_install
class Test2WeeksCalendar(TestPayslipBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Week 1: 16 Hours - Week 2: 32 Hours
        cls.calendar_2_weeks = cls.env['resource.calendar'].create({
            'name': 'Week 1: 16 Hours - Week 2: 32 Hours',
            'hours_per_day': 8,
            'days_per_week': 3,
            'hours_per_week': 24,
            'calendar_type': 'variable',
            'attendance_ids': [
                (0, 0, {'date': date(1, 1, 1), 'hour_from': 8, 'hour_to': 16, 'recurrency': True, 'recurrency_interval': 2, 'recurrency_type': 'weeks'}),
                (0, 0, {'date': date(1, 1, 2), 'hour_from': 9, 'hour_to': 17, 'recurrency': True, 'recurrency_interval': 2, 'recurrency_type': 'weeks'}),
                (0, 0, {'date': date(1, 1, 8), 'hour_from': 8, 'hour_to': 16, 'recurrency': True, 'recurrency_interval': 2, 'recurrency_type': 'weeks'}),
                (0, 0, {'date': date(1, 1, 9), 'hour_from': 7, 'hour_to': 15, 'recurrency': True, 'recurrency_interval': 2, 'recurrency_type': 'weeks'}),
                (0, 0, {'date': date(1, 1, 10), 'hour_from': 8, 'hour_to': 16, 'recurrency': True, 'recurrency_interval': 2, 'recurrency_type': 'weeks'}),
                (0, 0, {'date': date(1, 1, 11), 'hour_from': 10, 'hour_to': 18, 'recurrency': True, 'recurrency_interval': 2, 'recurrency_type': 'weeks'}),
            ]
        })

        cls.jules_emp = cls.env['hr.employee'].create({
            'name': 'Jules',
            'sex': 'male',
            'birthday': '1984-05-01',
            'country_id': cls.env.ref('base.us').id,
            'resource_calendar_id': cls.calendar_2_weeks.id,
        })

        # Contract for Jules
        cls.jules_emp.version_id.sudo().write({
            'contract_date_start': datetime.strptime('2015-01-01', '%Y-%m-%d'),
            'date_version': datetime.strptime('2015-01-01', '%Y-%m-%d'),
            'name': 'Contract for Jules',
            'resource_calendar_id': cls.calendar_2_weeks.id,
            'wage': 5000.33,
            'employee_id': cls.jules_emp.id,
            'structure_type_id': cls.developer_pay_structure.type_id.id,
        })
        cls.contract_jules = cls.jules_emp.version_id

    def test_contract_2_weeks(self):
        # Create a payslip for a month with a contract with 2 weeks period.
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.jules_emp.id,
            'date_from': datetime.strptime('2015-11-01', '%Y-%m-%d'),
            'date_to': datetime.strptime('2015-11-30', '%Y-%m-%d'),
        })
        self.assertEqual(payslip.worked_days_line_ids.number_of_hours, 104, "It should be 104 hours of work this month for this contract")
        self.assertEqual(payslip.worked_days_line_ids.number_of_days, 13, "It should be 13 days of work this month for this contract")

    def test_contract_2_weeks_holiday(self):
        # Leave during small week (just 2 days of work)
        leave = self.env['resource.calendar.leaves'].create({
            'name': 'leave name',
            'date_from': datetime.strptime('2015-11-08 07:00:00', '%Y-%m-%d %H:%M:%S'),
            'date_to': datetime.strptime('2015-11-14 18:00:00', '%Y-%m-%d %H:%M:%S'),
            'resource_id': self.jules_emp.resource_id.id,
            'calendar_id': self.calendar_2_weeks.id,
            'work_entry_type_id': self.work_entry_type_leave.id,
            'count_as': 'absence',
        })
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.jules_emp.id,
            'date_from': datetime.strptime('2015-11-01', '%Y-%m-%d'),
            'date_to': datetime.strptime('2015-11-30', '%Y-%m-%d'),
        })
        work = payslip.worked_days_line_ids.filtered(lambda line: line.code == '002.00')
        leave = payslip.worked_days_line_ids.filtered(lambda line: line.code == 'LEAVETEST100')
        self.assertEqual(work.number_of_hours, 88, "It should be 88 hours of work this month for this contract")
        self.assertEqual(leave.number_of_hours, 16, "It should be 16 hours of leave this month for this contract")
        self.assertEqual(work.number_of_days, 11, "It should be 11 days of work this month for this contract")
        self.assertEqual(leave.number_of_days, 2, "It should be 2 days of leave this month for this contract")

    def test_contract_2_big_weeks_holiday(self):
        # Leave during big week (4 days of work)
        leave = self.env['resource.calendar.leaves'].create({
            'name': 'leave name',
            'date_from': datetime.strptime('2015-11-15 07:00:00', '%Y-%m-%d %H:%M:%S'),
            'date_to': datetime.strptime('2015-11-21 18:00:00', '%Y-%m-%d %H:%M:%S'),
            'resource_id': self.jules_emp.resource_id.id,
            'calendar_id': self.calendar_2_weeks.id,
            'work_entry_type_id': self.work_entry_type_leave.id,
            'count_as': 'absence',
        })
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.jules_emp.id,
            'date_from': datetime.strptime('2015-11-01', '%Y-%m-%d'),
            'date_to': datetime.strptime('2015-11-30', '%Y-%m-%d'),
        })
        work = payslip.worked_days_line_ids.filtered(lambda line: line.code == '002.00')
        leave = payslip.worked_days_line_ids.filtered(lambda line: line.code == 'LEAVETEST100')
        self.assertEqual(work.number_of_hours, 72, "It should be 72 hours of work this month for this contract")
        self.assertEqual(leave.number_of_hours, 32, "It should be 32 hours of leave this month for this contract")
        self.assertEqual(work.number_of_days, 9, "It should be 9 days of work this month for this contract")
        self.assertEqual(leave.number_of_days, 4, "It should be 4 days of leave this month for this contract")

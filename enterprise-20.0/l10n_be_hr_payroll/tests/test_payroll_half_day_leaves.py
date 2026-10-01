# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, datetime

from odoo.tests import tagged
from odoo.fields import Command

from .common import TestPayrollCommon


@tagged('half_day_split')
@tagged('post_install_l10n', 'post_install', '-at_install')
class TestHalfDayLeaves(TestPayrollCommon):
    def setUp(self):
        super().setUp()
        self.test_calendar = self.env['resource.calendar'].create({
            'name': 'Test Calendar',
            'hours_per_day': 7.6,
            'hours_per_week': 38,
            'full_time_required_hours': 38,
            'attendance_ids': [(0, 0,
                    {'dayofweek': str(day), 'hour_from': 0, 'hour_to': 0, 'duration_hours': 7.6}) for day in range(0, 5)],
        })
        self.employee = self.env['hr.employee'].create({
            'name': 'Employee',
            'resource_calendar_id': self.test_calendar.id,
            'date_start': date(2020, 1, 1),
            'contract_date_start': date(2020, 1, 1),
        })
        self.work_entry_type = self.env['hr.work.entry.type'].create({
            'name': 'Test Leave',
            'code': 'LEAVE999',
            'requires_allocation': False,
            'unit_of_measure': 'day',
            'request_unit': 'half_day',
            'count_as': 'absence',
            'leave_validation_type': 'no_validation',
            'amount_rate': 100.0,
        })

    def test_half_day_leaves(self):
        leaves = self.env['hr.leave'].create([{
            'name': 'Leave 1',
            'employee_id': self.employee.id,
            'work_entry_type_id': self.work_entry_type.id,
            'request_date_from': date(2026, 5, 4),
            'request_date_to': date(2026, 5, 4),
            'request_date_from_period': 'am',
            'request_date_to_period': 'pm',
        },
        {
            'name': 'Leave 2',
            'employee_id': self.employee.id,
            'work_entry_type_id': self.work_entry_type.id,
            'request_date_from': date(2026, 5, 5),
            'request_date_to': date(2026, 5, 5),
            'request_date_from_period': 'pm',
            'request_date_to_period': 'pm',
        },
        {
            'name': 'Leave 3',
            'employee_id': self.employee.id,
            'work_entry_type_id': self.work_entry_type.id,
            'request_date_from': date(2026, 5, 6),
            'request_date_to': date(2026, 5, 6),
            'request_date_from_period': 'am',
            'request_date_to_period': 'am',
        },
        ])
        leaves.action_approve()
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'date_from': date(2026, 5, 1),
            'date_to': date(2026, 5, 31),
        })
        payslip.compute_sheet()
        off_days = payslip.worked_days_line_ids.filtered(lambda l: l.work_entry_type_id == self.work_entry_type)
        num_off_days = sum(off_days.mapped('number_of_days'))
        expected_num_off_days = sum(leaves.mapped('number_of_days'))
        self.assertEqual(num_off_days, expected_num_off_days, "Half Days are not correctly split in worked days lines")

    def test_multiple_hours_based_time_offs_on_same_half_day(self):
        """
        On the same day, an employee has:
            -A hours-based pto from 9h to 10h;
            -A half-day pto from 13h to 17h;
            -Attendance of duration 7h36 - 1h - 4h = 2.8h
        In that case, as we have 3 different time types during the same day, we only keep the one counting as working
        time and with the highest sequence to show with a day on the payslip lines. Therefore, we keep 2.8h of attendance.
        There are 21 working days in August 2026, so the number of days on the payslip should be 21.
        We have 20 days of worked days and a half-day pto. Even if 2.8h of attendance is less than half a day, because
        we need to have 21 days on the payslip, this attendance will be counted as half-day.
        """
        hours_time_off = self.env['hr.work.entry.type'].create({
            'name': 'hours based time off',
            'code': 'HPTO',
            'count_as': 'absence',
            'requires_allocation': False,
            'unit_of_measure': 'hour',
            'request_unit': 'hour'
        })
        leaves = self.env['hr.leave'].create([{
            'name': 'Leave 1',
            'employee_id': self.employee.id,
            'work_entry_type_id': hours_time_off.id,
            'request_date_from': date(2026, 8, 4),
            'request_date_to': date(2026, 8, 4),
            'request_hour_from': 9,
            'request_hour_to': 10,
            'request_duration': 'specific',
        },
        {
            'name': 'Leave 2',
            'employee_id': self.employee.id,
            'work_entry_type_id': self.work_entry_type.id,
            'request_date_from': datetime(2026, 8, 4, 13, 0, 0),
            'request_date_to': datetime(2026, 8, 4, 17, 0, 0),
            'request_date_from_period': 'pm',
            'request_date_to_period': 'pm',
        }])
        leaves.action_approve()
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'name': 'Payslip May',
            'date_from': date(2026, 8, 1),
            'date_to': date(2026, 8, 31),
        })
        self.assertEqual(sum(payslip.worked_days_line_ids.mapped('number_of_days')), 21.0)
        self.assertAlmostEqual(sum(payslip.worked_days_line_ids.mapped('number_of_hours')), 21.0 * self.employee.resource_calendar_id.hours_per_day)
        hpto_wdl = payslip.worked_days_line_ids.filtered(lambda wdl: wdl.work_entry_type_id.code == 'HPTO')
        self.assertEqual(hpto_wdl.number_of_days, 0)  # Hours-based time off
        self.assertEqual(hpto_wdl.number_of_hours, 1)
        leave_wdl = payslip.worked_days_line_ids.filtered(lambda wdl: wdl.work_entry_type_id == self.work_entry_type)
        self.assertEqual(leave_wdl.number_of_days, 0.5)  # Half-day leave
        self.assertEqual(leave_wdl.number_of_hours, 3.8)
        att_wdl = payslip.worked_days_line_ids.filtered(lambda wdl: wdl.work_entry_type_id.code == '002.00')
        self.assertEqual(att_wdl.number_of_days, 20.0 + 0.5)  # Attendance
        self.assertAlmostEqual(att_wdl.number_of_hours, (20.0 * 7.6) + 2.8)

    def test_irregular_hours_off(self):
        """
        On the same day, an employee has:
            -6 hours of attendance
            -1.8 hours of time off
        Because attendance prevails on the day, this day is considered as full for the attendance, and only the hours
        of the time off are taken into account.
        """
        hours_time_off = self.env['hr.work.entry.type'].create({
            'name': 'hours based time off',
            'code': 'HPTO',
            'count_as': 'absence',
            'requires_allocation': False,
            'unit_of_measure': 'hour',
            'request_unit': 'hour'
        })
        leaves = self.env['hr.leave'].create({
            'name': 'Leave 1',
            'employee_id': self.employee.id,
            'work_entry_type_id': hours_time_off.id,
            'request_date_from': date(2026, 8, 4),
            'request_date_to': date(2026, 8, 4),
            'request_hour_from': 9,
            'request_hour_to': 10.6,
            'request_duration': 'specific',
        })
        leaves.action_approve()
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'name': 'Payslip May',
            'date_from': date(2026, 8, 1),
            'date_to': date(2026, 8, 31),
        })
        self.assertEqual(sum(payslip.worked_days_line_ids.mapped('number_of_days')), 21.0)
        self.assertAlmostEqual(sum(payslip.worked_days_line_ids.mapped('number_of_hours')), 21.0 * self.employee.resource_calendar_id.hours_per_day)
        self.assertEqual(payslip.worked_days_line_ids[0].number_of_days, 0.0)  # Hours-based time off
        self.assertEqual(payslip.worked_days_line_ids[0].number_of_hours, 1.6)
        self.assertEqual(payslip.worked_days_line_ids[1].number_of_days, 21.0)  # Attendance
        self.assertAlmostEqual(payslip.worked_days_line_ids[1].number_of_hours, 158.0)

    def test_multiple_hours_based_working_types_on_same_day(self):
        """
        On the same day, an employee has:
            -5 hours of time off type 1
            -1 hour of time off type 2
            -1.6 hours of attendance
        Time off type is longer than half a day but smaller than a full day. We also have attendance hours on the same
        day. As Attendance hours prevail, we consider that the duration of attendances is half a day. Same for time off
        type 1.
        """
        hours_time_off_1, hours_time_off_2 = self.env['hr.work.entry.type'].create([{
            'name': 'hours based time off',
            'code': 'HPTO',
            'count_as': 'absence',
            'requires_allocation': False,
            'unit_of_measure': 'hour',
            'request_unit': 'hour'
        }, {
            'name': 'hours based time off 2',
            'code': 'HPTO2',
            'count_as': 'absence',
            'requires_allocation': False,
            'unit_of_measure': 'hour',
            'request_unit': 'hour'
        }])
        leaves = self.env['hr.leave'].create([{
            'name': 'Leave 1',
            'employee_id': self.employee.id,
            'work_entry_type_id': hours_time_off_1.id,
            'request_date_from': date(2026, 8, 4),
            'request_date_to': date(2026, 8, 4),
            'request_hour_from': 9,
            'request_hour_to': 14,
            'request_duration': 'specific',
        },
        {
            'name': 'Leave 2',
            'employee_id': self.employee.id,
            'work_entry_type_id': hours_time_off_2.id,
            'request_date_from': date(2026, 8, 4),
            'request_date_to': date(2026, 8, 4),
            'request_hour_from': 14,
            'request_hour_to': 15,
            'request_duration': 'specific',
        }])
        leaves.action_approve()
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'name': 'Payslip May',
            'date_from': date(2026, 8, 1),
            'date_to': date(2026, 8, 31),
        })
        self.assertEqual(sum(payslip.worked_days_line_ids.mapped('number_of_days')), 21.0)
        self.assertAlmostEqual(sum(payslip.worked_days_line_ids.mapped('number_of_hours')), 21.0 * self.employee.resource_calendar_id.hours_per_day)
        hpto2_wdl = payslip.worked_days_line_ids.filtered(lambda wdl: wdl.work_entry_type_id.code == 'HPTO2')
        self.assertEqual(hpto2_wdl.number_of_days, 0.0)  # Hours-based time off 2
        self.assertEqual(hpto2_wdl.number_of_hours, 1)
        hpto1_wdl = payslip.worked_days_line_ids.filtered(lambda wdl: wdl.work_entry_type_id.code == 'HPTO')
        self.assertEqual(hpto1_wdl.number_of_days, 0.5)  # Hours-based time off 1
        self.assertAlmostEqual(hpto1_wdl.number_of_hours, 5)
        att_wdl = payslip.worked_days_line_ids.filtered(lambda wdl: wdl.work_entry_type_id.code == '002.00')
        self.assertEqual(att_wdl.number_of_days, 20.0 + 0.5)  # Half-day attendance
        self.assertAlmostEqual(att_wdl.number_of_hours, (20 * 7.6) + 1.6)

    def test_multiple_hours_based_time_offs_on_same_half_day_irregular_schedule(self):
        """
        An employee has a 8 8 8 8 6 schedule. -> Total = 38 hours per week
        On Wednesday 2d September, an employee has
            -A hours-based extra legal time off from 10h to 11h30;
            -A half-day sick time off;
            -Attendance of duration 8 - 1h30 - 4h = 2h30.
        On Thursday 3rd September, this employee has
            -A hours-based PTO from 10 to 12;
            -A half-day sick time off.
        Total on payslip:
            - Extra legal time off: 0 days, 1h30
            - Paid time off: 0 days, 2h
            - Attendance: 0.5 days, 2h. Accounts for September 2rd morning. This time off type prevails on the PTO
            taken the same half-day, as it counts as worked time.
            - Attendance: O.5 days, 2h30. Accounts for September 3rd morning.
            - Sick time off: 2 half-days, 8 h
            - Attendance: 152h
        Total:
            - 22 days, 168 hours.
        """
        attendance_ids = []
        for weekday in ['0', '1', '2', '3']:
            attendance_ids += [
                Command.create({'dayofweek': weekday, 'duration_hours': 8, 'day_period': 'full_day'})
            ]
        attendance_ids += [Command.create({'dayofweek': '4', 'duration_hours': 6, 'day_period': 'full_day'})]
        calendar = self.env['resource.calendar'].create({
            'name': 'Duration based calendar',
            'attendance_ids': attendance_ids,
            'calendar_type': 'fixed'
        })
        self.employee.write({'resource_calendar_id': calendar.id})
        extra_legal, sick, paid = self.env['hr.work.entry.type'].create([{
            'name': 'hours based extra legal time off',
            'code': 'XTO',
            'count_as': 'absence',
            'requires_allocation': False,
            'unit_of_measure': 'hour',
            'request_unit': 'hour'
        }, {
            'name': 'Sick time off',
            'code': 'STO',
            'count_as': 'absence',
            'requires_allocation': False,
            'unit_of_measure': 'hour',
            'request_unit': 'half_day'
        }, {
            'name': 'Paid time off',
            'code': 'PTO',
            'count_as': 'absence',
            'requires_allocation': False,
            'unit_of_measure': 'hour',
            'request_unit': 'hour'
        }])
        leaves = self.env['hr.leave'].create([{
            'name': 'extra legal 1',
            'employee_id': self.employee.id,
            'work_entry_type_id': extra_legal.id,
            'request_date_from': date(2026, 9, 2),
            'request_date_to': date(2026, 9, 2),
            'request_hour_from': 10,
            'request_hour_to': 11.5,
            'request_duration': 'specific',
        }, {
            'name': 'sick leave 1',
            'employee_id': self.employee.id,
            'work_entry_type_id': sick.id,
            'request_date_from': datetime(2026, 9, 2, 12, 0, 0),
            'request_date_to': datetime(2026, 9, 2, 16, 0, 0),
            'request_date_from_period': 'pm',
            'request_date_to_period': 'pm',
        }, {
            'name': 'Paid 1',
            'employee_id': self.employee.id,
            'work_entry_type_id': paid.id,
            'request_date_from': date(2026, 9, 3),
            'request_date_to': date(2026, 9, 3),
            'request_hour_from': 10,
            'request_hour_to': 12,
            'request_duration': 'specific',
        }, {
            'name': 'sick leave 2',
            'employee_id': self.employee.id,
            'work_entry_type_id': sick.id,
            'request_date_from': datetime(2026, 9, 3, 12, 0, 0),
            'request_date_to': datetime(2026, 9, 3, 16, 0, 0),
            'request_date_from_period': 'pm',
            'request_date_to_period': 'pm',
        }])
        leaves.action_approve()
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'name': 'Payslip May',
            'date_from': date(2026, 9, 1),
            'date_to': date(2026, 9, 30),
        })
        self.assertEqual(sum(payslip.worked_days_line_ids.mapped('number_of_days')), 22.0)
        self.assertAlmostEqual(sum(payslip.worked_days_line_ids.mapped('number_of_hours')), 168)
        xto_wdl = payslip.worked_days_line_ids.filtered(lambda wdl: wdl.work_entry_type_id.code == 'XTO')
        self.assertEqual(xto_wdl.number_of_days, 0)  # Hours-based extra legal time off
        self.assertEqual(xto_wdl.number_of_hours, 1.5)
        paid_wdl = payslip.worked_days_line_ids.filtered(lambda wdl: wdl.work_entry_type_id.code == 'PTO')
        self.assertEqual(paid_wdl.number_of_days, 0.0)  # Paid time off
        self.assertEqual(paid_wdl.number_of_hours, 2.0)
        sick_wdl = payslip.worked_days_line_ids.filtered(lambda wdl: wdl.work_entry_type_id.code == 'STO')
        self.assertEqual(sick_wdl.number_of_days, 1.0)  # Sick time off
        self.assertEqual(sick_wdl.number_of_hours, 8.0)
        att_wdl = payslip.worked_days_line_ids.filtered(lambda wdl: wdl.work_entry_type_id.code == '002.00')
        self.assertEqual(att_wdl.number_of_days, 20.0 + 1.0)  # Attendances
        self.assertAlmostEqual(att_wdl.number_of_hours, 152 + 4.5)

    def test_attendance_full_day_2h_training_2h_timeoff(self):
        """
        In the same day:
            - PTO of 2 hours
            - Training of 2 hours
            - Attendance of 3.6 hours
        Attendance prevails and gets the whole day, as training type is a working type.
        """
        train, hpto = self.env['hr.work.entry.type'].create([{
            'name': 'hours based training',
            'code': 'TRAI',
            'count_as': 'absence',
            'requires_allocation': False,
            'unit_of_measure': 'hour',
            'request_unit': 'hour'
        }, {
            'name': 'hours based time off',
            'code': 'HPTO',
            'count_as': 'absence',
            'requires_allocation': False,
            'unit_of_measure': 'hour',
            'request_unit': 'hour'
        }])
        leaves = self.env['hr.leave'].create([{
            'name': 'Leave 1',
            'employee_id': self.employee.id,
            'work_entry_type_id': train.id,
            'request_date_from': date(2026, 8, 4),
            'request_date_to': date(2026, 8, 4),
            'request_hour_from': 9,
            'request_hour_to': 11,
            'request_duration': 'specific',
        },
        {
            'name': 'Leave ',
            'employee_id': self.employee.id,
            'work_entry_type_id': hpto.id,
            'request_date_from': date(2026, 8, 4),
            'request_date_to': date(2026, 8, 4),
            'request_hour_from': 11,
            'request_hour_to': 13,
            'request_duration': 'specific',
        }])
        leaves.action_approve()
        leaves[0].work_entry_type_id.write({'count_as': 'working_time'})
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'name': 'Payslip May',
            'date_from': date(2026, 8, 1),
            'date_to': date(2026, 8, 31),
        })
        self.assertEqual(sum(payslip.worked_days_line_ids.mapped('number_of_days')), 21.0)
        self.assertEqual(payslip.worked_days_line_ids[0].number_of_days, 0)  # Hours-based time off
        self.assertEqual(payslip.worked_days_line_ids[0].number_of_hours, 2.0)
        self.assertEqual(payslip.worked_days_line_ids[1].number_of_days, 0.0)  # training
        self.assertEqual(payslip.worked_days_line_ids[1].number_of_hours, 2.0)
        self.assertEqual(payslip.worked_days_line_ids[2].number_of_days, 21.0)  # Half-day Attendance
        self.assertAlmostEqual(payslip.worked_days_line_ids[2].number_of_hours, (21 * 7.6) - 4)

    def test_attendance_half_day_5h_training_half_day(self):
        """
        In the same day:
            - Training of 5 hours
            - Attendance of 2.6 hours
        Training duration is more than half a day but less than a day. Because the remaining is an Attendance and
        Attendance prevails, attendance gets half a day, and so does Training.
        """
        train = self.env['hr.work.entry.type'].create({
            'name': 'hours based training',
            'code': 'TRAI',
            'count_as': 'absence',
            'requires_allocation': False,
            'unit_of_measure': 'hour',
            'request_unit': 'hour'
        })
        leaves = self.env['hr.leave'].create({
            'name': 'Leave 1',
            'employee_id': self.employee.id,
            'work_entry_type_id': train.id,
            'request_date_from': date(2026, 8, 4),
            'request_date_to': date(2026, 8, 4),
            'request_hour_from': 9,
            'request_hour_to': 14,
            'request_duration': 'specific',
        })
        leaves.action_approve()
        leaves[0].work_entry_type_id.write({'count_as': 'working_time'})
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'name': 'Payslip May',
            'date_from': date(2026, 8, 1),
            'date_to': date(2026, 8, 31),
        })
        self.assertEqual(sum(payslip.worked_days_line_ids.mapped('number_of_days')), 21.0)
        att_wdl = payslip.worked_days_line_ids.filtered(lambda wdl: wdl.work_entry_type_id.code == '002.00')
        self.assertEqual(att_wdl.number_of_days, 20.0 + 0.5)  # Attendance
        self.assertAlmostEqual(att_wdl.number_of_hours, (20.0 * 7.6) + 2.6)
        training_wdl = payslip.worked_days_line_ids.filtered(lambda wdl: wdl.work_entry_type_id.code == 'TRAI')
        self.assertEqual(training_wdl.number_of_days, 0.5)  # Training
        self.assertAlmostEqual(training_wdl.number_of_hours, 5.0)

    def test_attendance_full_day_training_time_off(self):
        """
        In the same day:
            - Training of 1 hour
            - Time off of 2 hours
            - extra time off of 2 hours
            - attendance of 2.6 hours
        Because attendance prevails, attendance gets a full day.
        """
        train, hpto, xto = self.env['hr.work.entry.type'].create([{
            'name': 'hours based training',
            'code': 'TRAI',
            'count_as': 'absence',
            'requires_allocation': False,
            'unit_of_measure': 'hour',
            'request_unit': 'hour'
        }, {
            'name': 'hours based time off',
            'code': 'HPTO',
            'count_as': 'absence',
            'requires_allocation': False,
            'unit_of_measure': 'hour',
            'request_unit': 'hour'
        }, {
            'name': 'extra legal time off',
            'code': 'XTO',
            'count_as': 'absence',
            'requires_allocation': False,
            'unit_of_measure': 'hour',
            'request_unit': 'hour'
        }])
        leaves = self.env['hr.leave'].create([{
            'name': 'Leave 1',
            'employee_id': self.employee.id,
            'work_entry_type_id': train.id,
            'request_date_from': date(2026, 8, 4),
            'request_date_to': date(2026, 8, 4),
            'request_hour_from': 9,
            'request_hour_to': 10,
            'request_duration': 'specific',
        }, {
            'name': 'Leave ',
            'employee_id': self.employee.id,
            'work_entry_type_id': hpto.id,
            'request_date_from': date(2026, 8, 4),
            'request_date_to': date(2026, 8, 4),
            'request_hour_from': 10,
            'request_hour_to': 12,
            'request_duration': 'specific',
        }, {
            'name': 'Leave ',
            'employee_id': self.employee.id,
            'work_entry_type_id': xto.id,
            'request_date_from': date(2026, 8, 4),
            'request_date_to': date(2026, 8, 4),
            'request_hour_from': 12,
            'request_hour_to': 14,
            'request_duration': 'specific',
        }])
        leaves.action_approve()
        leaves[0].work_entry_type_id.write({'count_as': 'working_time'})
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'name': 'Payslip May',
            'date_from': date(2026, 8, 1),
            'date_to': date(2026, 8, 31),
        })
        self.assertEqual(sum(payslip.worked_days_line_ids.mapped('number_of_days')), 21.0)
        self.assertEqual(payslip.worked_days_line_ids[0].number_of_days, 0.0)  # training
        self.assertEqual(payslip.worked_days_line_ids[0].number_of_hours, 1.0)
        self.assertEqual(payslip.worked_days_line_ids[1].number_of_days, 0.0)  # hours based time off
        self.assertEqual(payslip.worked_days_line_ids[1].number_of_hours, 2.0)
        self.assertEqual(payslip.worked_days_line_ids[2].number_of_days, 0.0)  # extra legal time off
        self.assertEqual(payslip.worked_days_line_ids[2].number_of_hours, 2.0)
        self.assertEqual(payslip.worked_days_line_ids[3].number_of_days, 21.0)  # attendance
        self.assertAlmostEqual(payslip.worked_days_line_ids[3].number_of_hours, (21 * 7.6) - 5.0)

    def test_no_attendance_training_half_day_multiple_time_offs(self):
        """
        In the same day of a 40 hours work schedule:
            - Training of 2 hours
            - Time off of 2 hours
            - extra time off of 4 hours
        Extra time off gets half a day. Because training is a working type, it prevails on time off, and it gets the
        remaining half-day.
        """
        self.employee.write({'resource_calendar_id': self.resource_calendar_40.id})
        train, hpto, xto = self.env['hr.work.entry.type'].create([{
            'name': 'hours based training',
            'code': 'TRAI',
            'count_as': 'absence',
            'requires_allocation': False,
            'unit_of_measure': 'hour',
            'request_unit': 'hour'
        }, {
            'name': 'hours based time off',
            'code': 'HPTO',
            'count_as': 'absence',
            'requires_allocation': False,
            'unit_of_measure': 'hour',
            'request_unit': 'hour'
        }, {
            'name': 'extra legal time off',
            'code': 'XTO',
            'count_as': 'absence',
            'requires_allocation': False,
            'unit_of_measure': 'hour',
            'request_unit': 'hour'
        }])
        leaves = self.env['hr.leave'].create([{
            'name': 'Leave 1',
            'employee_id': self.employee.id,
            'work_entry_type_id': train.id,
            'request_date_from': date(2026, 8, 4),
            'request_date_to': date(2026, 8, 4),
            'request_hour_from': 8,
            'request_hour_to': 10,
            'request_duration': 'specific',
        }, {
            'name': 'Leave ',
            'employee_id': self.employee.id,
            'work_entry_type_id': hpto.id,
            'request_date_from': date(2026, 8, 4),
            'request_date_to': date(2026, 8, 4),
            'request_hour_from': 10,
            'request_hour_to': 12,
            'request_duration': 'specific',
        }, {
            'name': 'Leave ',
            'employee_id': self.employee.id,
            'work_entry_type_id': xto.id,
            'request_date_from': date(2026, 8, 4),
            'request_date_to': date(2026, 8, 4),
            'request_hour_from': 13,
            'request_hour_to': 17,
            'request_duration': 'specific',
        }])
        leaves.action_approve()
        leaves[0].work_entry_type_id.write({'count_as': 'working_time'})
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'name': 'Payslip May',
            'date_from': date(2026, 8, 1),
            'date_to': date(2026, 8, 31),
        })
        self.assertEqual(sum(payslip.worked_days_line_ids.mapped('number_of_days')), 21.0)
        self.assertEqual(payslip.worked_days_line_ids[0].number_of_days, 0.0)  # hours-based time off
        self.assertEqual(payslip.worked_days_line_ids[0].number_of_hours, 2.0)
        self.assertEqual(payslip.worked_days_line_ids[1].number_of_days, 0.5)  # hours based training
        self.assertEqual(payslip.worked_days_line_ids[1].number_of_hours, 2.0)
        self.assertEqual(payslip.worked_days_line_ids[2].number_of_days, 0.5)  # extra legal time off
        self.assertEqual(payslip.worked_days_line_ids[2].number_of_hours, 4.0)
        self.assertEqual(payslip.worked_days_line_ids[3].number_of_days, 20.0)  # attendance
        self.assertAlmostEqual(payslip.worked_days_line_ids[3].number_of_hours, 20 * 8)

    def test_no_attendance_training_half_day_time_off_half_day(self):
        """
        In the same day:
            - Training of 3 hours
            - Time off of 5 hours
        Time off duration is more than half a day but less than a day. Because the remaining is a training type and
        training is a working type, it prevails: training gets half a day, and so does time off.
        """
        self.employee.write({'resource_calendar_id': self.resource_calendar_40.id})
        train, hpto = self.env['hr.work.entry.type'].create([{
            'name': 'hours based training',
            'code': 'TRAI',
            'count_as': 'absence',
            'requires_allocation': False,
            'unit_of_measure': 'hour',
            'request_unit': 'hour'
        }, {
            'name': 'hours based time off',
            'code': 'HPTO',
            'count_as': 'absence',
            'requires_allocation': False,
            'unit_of_measure': 'hour',
            'request_unit': 'hour'
        }])
        leaves = self.env['hr.leave'].create([{
            'name': 'Leave 1',
            'employee_id': self.employee.id,
            'work_entry_type_id': train.id,
            'request_date_from': date(2026, 8, 4),
            'request_date_to': date(2026, 8, 4),
            'request_hour_from': 8.0,
            'request_hour_to': 11.0,
            'request_duration': 'specific',
        }, {
            'name': 'Leave ',
            'employee_id': self.employee.id,
            'work_entry_type_id': hpto.id,
            'request_date_from': date(2026, 8, 4),
            'request_date_to': date(2026, 8, 4),
            'request_hour_from': 11.0,
            'request_hour_to': 17.0,
            'request_duration': 'specific',
        }])
        leaves.action_approve()
        leaves[0].work_entry_type_id.write({'count_as': 'working_time'})
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'name': 'Payslip May',
            'date_from': date(2026, 8, 1),
            'date_to': date(2026, 8, 31),
        })
        self.assertEqual(sum(payslip.worked_days_line_ids.mapped('number_of_days')), 21.0)
        self.assertEqual(payslip.worked_days_line_ids[0].number_of_days, 0.5)  # training
        self.assertEqual(payslip.worked_days_line_ids[0].number_of_hours, 3.0)
        self.assertEqual(payslip.worked_days_line_ids[1].number_of_days, 0.5)  # hours based time off
        self.assertEqual(payslip.worked_days_line_ids[1].number_of_hours, 5.0)
        self.assertEqual(payslip.worked_days_line_ids[2].number_of_days, 20.0)  # attendance
        self.assertAlmostEqual(payslip.worked_days_line_ids[2].number_of_hours, 20 * 8)

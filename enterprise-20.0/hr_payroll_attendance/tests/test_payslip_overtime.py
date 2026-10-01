# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.hr_holidays_attendance.tests.common import HrWorkEntryAttendanceCommon

from datetime import datetime, date

from odoo import Command
from odoo.tests import tagged


@tagged('-at_install', 'post_install', 'payslip_overtime')
class TestPayslipOvertime(HrWorkEntryAttendanceCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.overtime_type = cls.env.ref('hr_work_entry.generic_work_entry_type_overtime')

        cls.struct_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Test Structure Type',
            'wage_type': 'hourly',
        })
        cls.struct = cls.env['hr.payroll.structure'].create({
            'name': 'Test Structure - Worker',
            'type_id': cls.struct_type.id,
        })
        cls.payslip = cls.env['hr.payslip'].create({
            'name': 'Test Payslip',
            'employee_id': cls.employee.id,
            'struct_id': cls.struct.id,
            'date_from': '2022-01-01',
            'date_to': '2022-01-31',
        })

        cls.env['hr.time.rule'].search([]).write({'active': False})
        cls.time_rule = cls.env['hr.time.rule'].create({
            'name': 'Test Overtime Rule',
            'calendar_source': 'employee',
            'quantity_period': 'day',
            'work_entry_type_id': cls.overtime_type.id,
            'condition_work_entry_type_ids': [cls.env.company.attendance_work_entry_type_id.id],
        })

        cls.version.structure_type_id = cls.struct_type
        cls.version.hourly_wage = 100

    def test_overtime_outside_period(self):
        """Attendances on the day before and day after the payslip period produce no overtime line.

        The work entry date is set in the employee's timezone (UTC here).  Boundary
        attendances (Dec 31 and Feb 1) must not bleed into the January payslip even
        when the company uses a timezone that shifts midnight.
        """
        # Right before the payslip period
        self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2021, 12, 31, 7, 0, 0),
            'check_out': datetime(2021, 12, 31, 20, 0, 0),
        })
        # Right after the payslip period
        self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2022, 2, 1, 7, 0, 0),
            'check_out': datetime(2022, 2, 1, 20, 0, 0),
        })
        # Since contract resource_calendar_id's default to the company's,
        # we can just change the company's resource_calendar_id's timezone.
        self.env.company.tz = "Asia/Manila"
        self.payslip._compute_worked_days_line_ids()
        self.assertFalse(self.payslip.worked_days_line_ids.filtered(lambda w: w.code == '040.00'))
        self.env.company.tz = "Indian/Maldives"
        self.payslip._compute_worked_days_line_ids()
        self.assertFalse(self.payslip.worked_days_line_ids.filtered(lambda w: w.code == '040.00'))
        self.env.company.tz = "Europe/Brussels"
        self.payslip._compute_worked_days_line_ids()
        self.assertFalse(self.payslip.worked_days_line_ids.filtered(lambda w: w.code == '040.00'))

    def test_with_overtime(self):
        """Attendance of 20h on an 8h day produces 12h overtime in the payslip."""
        self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2022, 1, 3, 0, 0, 0),
            'check_out': datetime(2022, 1, 3, 20, 0, 0),
        })
        self.payslip._compute_worked_days_line_ids()
        self.assertEqual(self.payslip.worked_days_line_ids.filtered(lambda w: w.code == '040.00').number_of_hours, 12)

    def test_with_overtime_reduced_by_break_duration(self):
        self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2022, 1, 3, 0, 0, 0),
            'check_out': datetime(2022, 1, 3, 10, 0, 0),
            'break_duration': 2.0,
        })
        self.payslip._compute_worked_days_line_ids()
        self.assertFalse(self.payslip.worked_days_line_ids.filtered(lambda w: w.code == '040.00'))

    def test_with_negative_overtime(self):
        """Working only 3h on an 8h day produces no overtime line (deficit, not excess)."""
        self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2022, 1, 3, 9, 0, 0),
            'check_out': datetime(2022, 1, 3, 12, 0, 0),
        })
        self.payslip._compute_worked_days_line_ids()
        self.assertFalse(self.payslip.worked_days_line_ids.filtered(lambda w: w.code == '040.00'))

    def test_with_overtime_calendar_contract(self):
        """Calendar-based employee with 20h attendance on an 8h day: 12h overtime in payslip.

        _sync_work_time_leave runs for all employees regardless of attendance_based, so
        the time rule fires and the output leave flows into the payslip the same way.
        """
        self.version.attendance_based = False
        self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2022, 1, 3, 0, 0, 0),
            'check_out': datetime(2022, 1, 3, 20, 0, 0),
        })
        self.payslip._compute_worked_days_line_ids()
        ot_line = self.payslip.worked_days_line_ids.filtered(lambda w: w.code == '040.00')
        self.assertEqual(ot_line.number_of_hours, 12)

    def test_overtime_duration_precision_no_leak_to_attendance(self):
        calendar_8h = self.env['resource.calendar'].create({
            'name': 'Classic 40h/week',
            'attendance_ids': [
                Command.create({
                    'dayofweek': str(i),
                    'hour_from': 9.0,
                    'hour_to': 17.0,
                    'day_period': 'morning',
                })
                for i in range(5)
            ],
        })
        self.version.resource_calendar_id = calendar_8h
        self.version.hourly_wage = 3600

        overtime_seconds = 5
        scheduled_hours = 8.0
        check_in = datetime(2022, 1, 3, 9, 0, 0)
        check_out = datetime(2022, 1, 3, 17, 0, overtime_seconds)
        self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': check_in,
            'check_out': check_out,
        })
        self.payslip._compute_worked_days_line_ids()
        self.payslip.compute_sheet()

        attendance_amount = sum(
            self.payslip.worked_days_line_ids
            .filtered(lambda w: w.code == '002.00')
            .mapped('amount'),
            0.0,
        )
        overtime_amount = sum(
            self.payslip.worked_days_line_ids
            .filtered(lambda w: w.code == '040.00')
            .mapped('amount'),
            0.0,
        )

        # hourly_wage=3600 with amount_rate=1.0: 1 monetary unit = 1 second of work
        expected_attendance_amount = scheduled_hours * self.version.hourly_wage
        expected_overtime_amount = overtime_seconds / 3600 * self.version.hourly_wage

        self.assertAlmostEqual(attendance_amount, expected_attendance_amount, places=2)
        self.assertAlmostEqual(overtime_amount, expected_overtime_amount, places=2)

    def test_refused_overtime_excluded_from_payslip(self):
        """Refusing an overtime output attendance removes it from the payslip worked days.
        """
        self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2022, 1, 3, 0, 0, 0),
            'check_out': datetime(2022, 1, 3, 20, 0, 0),
        })

        # Baseline: validated output attendance IS in the payslip.
        self.payslip._compute_worked_days_line_ids()
        ot_before = self.payslip.worked_days_line_ids.filtered(lambda w: w.code == '040.00')
        self.assertTrue(ot_before, "Validated overtime output attendance should appear in payslip")

        # Refuse the output attendance (time rule output is hr.attendance).
        overtime_attendance = self.env['hr.attendance'].search([
            ('employee_id', '=', self.employee.id),
            ('time_rule_id', '!=', False),
        ], limit=1)
        self.assertTrue(overtime_attendance, "Time rule should have generated an output attendance")
        overtime_attendance.action_refuse()

        # After refusal, the overtime line must disappear.
        self.payslip._compute_worked_days_line_ids()
        ot_after = self.payslip.worked_days_line_ids.filtered(lambda w: w.code == '040.00')
        self.assertFalse(ot_after, "Refused overtime output attendance must not appear in payslip")

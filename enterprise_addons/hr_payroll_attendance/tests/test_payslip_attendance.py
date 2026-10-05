# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, datetime

from odoo.tests import tagged

from odoo.addons.hr_holidays_attendance.tests.common import HrWorkEntryAttendanceCommon


@tagged('-at_install', 'post_install')
class TestPayslipAttendance(HrWorkEntryAttendanceCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
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
            'date_from': '2024-01-01',
            'date_to': '2024-01-30',
        })

    def test_get_attendance_from_payslip(self):
        attendance_A, attendance_B, *_ = self.env['hr.attendance'].create([
            {
                'employee_id': self.employee.id,
                'check_in': datetime(2024, 1, 1, 8, 0, 0),
                'check_out': datetime(2024, 1, 1, 16, 0, 0),
            },
            {
                'employee_id': self.employee.id,
                'check_in': datetime(2024, 1, 20, 8, 0, 0),
                'check_out': datetime(2024, 1, 20, 16, 0, 0),
            },
            {
                'employee_id': self.employee.id,
                'check_in': datetime(2024, 2, 1, 8, 0, 0),
                'check_out': datetime(2024, 2, 1, 16, 0, 0),
            },
            {
                'employee_id': self.employee.id,
                'check_in': datetime(2024, 2, 20, 8, 0, 0),
                'check_out': datetime(2024, 2, 20, 16, 0, 0),
            },
        ])
        attendance_by_payslip = self.payslip._get_attendance_by_payslip()
        self.assertEqual(attendance_by_payslip[self.payslip], attendance_A + attendance_B)

    def test_get_attendance_from_payslip_with_timezone(self):
        attendance_A, attendance_B, = self.env['hr.attendance'].create([
            {
                'employee_id': self.employee.id,
                'check_in': datetime(2024, 1, 1, 7, 0, 0),
                'check_out': datetime(2024, 1, 1, 15, 0, 0),
            },
            {
                'employee_id': self.employee.id,
                'check_in': datetime(2024, 1, 30, 23, 30, 0),  # 2024-01-31 00-30-00 in UTC+1
                'check_out': datetime(2024, 1, 31, 7, 30, 0),
            },
        ])

        # Without using `_get_attendance_by_payslip`
        domain = [
            ('employee_id', '=', self.employee.id),
            ('check_in', '<=', self.payslip.date_to),
            ('check_out', '>=', self.payslip.date_from)
        ]
        attendances = self.env['hr.attendance'].with_context(tz="Europe/Brussels").search(domain)
        self.assertEqual(attendances, attendance_A)
        self.assertNotIn(attendance_B, attendances)
        # With using `_get_attendance_by_payslip`:
        attendance_by_payslip = self.payslip.with_context(tz="Europe/Brussels")._get_attendance_by_payslip()
        self.assertEqual(attendance_by_payslip[self.payslip], attendance_A)

    def test_compute_payslip_no_worked_hours(self):
        employee = self.env['hr.employee'].create({
            'name': 'John',
            'wage': 5000,
            'date_version': date(2024, 10, 1),
            'contract_date_start': date(2024, 10, 1),
            'contract_date_end': date(2024, 10, 31),
            'attendance_based': True,
            'structure_type_id': self.struct_type.id,
        })
        contract = employee.version_id

        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': contract.id,
            'struct_id': self.struct.id,
            'date_from': date(2024, 10, 1),
            'date_to': date(2024, 10, 31)
        })

        payslip.compute_sheet()
        basic_salary_line = payslip.line_ids.filtered_domain([('code', '=', 'BASIC')])
        self.assertAlmostEqual(basic_salary_line.amount, 0.0, 2, 'Basic salary = 0 worked hours * hourly wage = 0')

    def test_attendance_open_single_payslip(self):
        self.payslip.state = 'validated'
        draft_payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'struct_id': self.struct.id,
            'date_from': '2024-01-01',
            'date_to': '2024-01-30',
        })
        attendance = self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2024, 1, 20, 8, 0, 0),
            'check_out': datetime(2024, 1, 20, 16, 0, 0),
        })

        self.assertEqual(attendance.payslip_id, self.payslip)
        self.assertNotEqual(attendance.payslip_id, draft_payslip)
        action = attendance.action_open_payslip()
        self.assertEqual(action['res_id'], self.payslip.id)
        self.assertEqual(action['view_mode'], 'form')

    def test_attendance_payslip_uses_timezone_date(self):
        self.payslip.state = 'validated'
        attendance = self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2024, 1, 30, 23, 30, 0),
            'check_out': datetime(2024, 1, 31, 7, 30, 0),
        })
        self.assertEqual(attendance.payslip_id, self.payslip)
        self.employee.tz = 'Europe/Brussels'
        attendance.invalidate_recordset(['payslip_id'])
        self.assertFalse(attendance.payslip_id)

    def test_generate_payrun_attendance_with_overtime(self):
        """A payrun must generate and compute payslips for attendance-based employees with overtime hours."""
        overtime_type = self.env.ref('hr_work_entry.generic_work_entry_type_overtime')
        self.env['hr.time.rule'].create({
            'name': 'Test Overtime Rule',
            'calendar_source': 'employee',
            'quantity_period': 'day',
            'work_entry_type_id': overtime_type.id,
            'condition_work_entry_type_ids': [self.env.company.attendance_work_entry_type_id.id],
        })

        self.employee.version_id.write({
            'structure_type_id': self.struct_type,
            'hourly_wage': 100,
        })

        # 20h worked on a scheduled 8h day -> 12h overtime
        self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2024, 1, 3, 0, 0, 0),  # Wednesday
            'check_out': datetime(2024, 1, 3, 20, 0, 0),
        })

        action = self.env['hr.payslip.run'].action_start_payrun_with_warnings({
            'date_start': '2024-01-01',
            'date_end': '2024-01-30',
            'structure_id': self.struct.id,
            'company_id': self.env.company.id,
        })
        self.assertNotEqual(
            action.get('tag'), 'hr_payroll.payrun_start_warning',
            f"Starting the payrun raised unexpected warnings: {action.get('params')}",
        )

        payrun = self.env['hr.payslip.run'].search([
            ('date_start', '=', '2024-01-01'),
            ('date_end', '=', '2024-01-30'),
            ('structure_id', '=', self.struct.id),
        ])
        self.assertEqual(len(payrun), 1, 'The payrun should have been created')
        self.assertEqual(len(payrun.slip_ids), 1, 'Payrun should have generated one payslip for the attendance-based employee')
        payslip = payrun.slip_ids
        self.assertEqual(payslip.state, 'draft')
        self.assertFalse(payslip.error_count, 'Payslip should not have blocking errors')
        self.assertEqual(payrun.state, '01_ready', 'Payrun should move past draft once its payslip is generated')

        overtime_line = payslip.worked_days_line_ids.filtered(lambda w: w.code == '040.00')
        self.assertTrue(overtime_line, 'Payslip should include an overtime worked days line')
        self.assertEqual(overtime_line.number_of_hours, 12)

        basic_line = payslip.line_ids.filtered_domain([('code', '=', 'BASIC')])
        self.assertTrue(basic_line, 'Payslip should have computed salary lines')
        self.assertGreater(basic_line.amount, 0, 'Basic salary should be computed from worked hours')

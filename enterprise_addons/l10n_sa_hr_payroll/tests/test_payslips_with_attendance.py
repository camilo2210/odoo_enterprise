# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, datetime
from unittest import SkipTest

from odoo.tests.common import tagged

from .common import TestSACommon


@tagged('post_install', 'post_install_l10n', '-at_install', 'payslips_validation')
class TestPayslipsWithAttendance(TestSACommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if cls.env["ir.module.module"]._get("hr_payroll_attendance").state != "installed":
            raise SkipTest("The test was skipped because the 'hr_payroll_attendance' module isn’t installed; therefore, attendance-based entries are unavailable.")
        cls.saudi_employee.version_id.attendance_based = True

    def test_saudi_payslip_attendance(self):
        self.saudi_employee.version_id.contract_date_end = '2026-4-27'
        paid_leave_allocation = self.env['hr.leave.allocation'].create({
            'employee_id': self.saudi_employee.id,
            'date_from': date(2026, 4, 1),
            'work_entry_type_id': self.env.ref('hr_work_entry.sa_work_entry_type_legal_leave').id,
            'number_of_days': 3,
            'state': 'confirm',
        })
        paid_leave_allocation.action_approve()
        self.env['hr.leave'].create([{
                'name': 'Unpaid Leave',
                'employee_id': self.saudi_employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.sa_work_entry_type_unpaid_leave').id,
                'request_date_from': date(2026, 4, 1),
                'request_date_to': date(2026, 4, 2),
        }, {
                'name': 'Paid Leave',
                'employee_id': self.saudi_employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.sa_work_entry_type_legal_leave').id,
                'request_date_from': date(2026, 4, 3),
                'request_date_to': date(2026, 4, 7),
        }, {
                'name': 'Sick Leave',
                'employee_id': self.saudi_employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.sa_work_entry_type_sick_leave').id,
                'request_date_from': date(2026, 4, 8),
                'request_date_to': date(2026, 4, 10),
        }])
        self.env['hr.attendance'].create([{  # noqa: OLS03001
            'employee_id': self.saudi_employee.id,
            'check_in': datetime(2026, 4, day, 8, 0, 0),
            'check_out': datetime(2026, 4, day, 16, 0, 0),
        } for day in range(11, 28) if date(2026, 4, day).weekday() not in (5, 6)])  # exclude weekends

        payslip = self._generate_payslip(date(2026, 4, 1), date(2026, 4, 30), employee_id=self.saudi_employee.id,
            version_id=self.saudi_employee.version_id.id,
            struct_id=self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure').id)
        payslip_results = {'BASIC': 9272.72, 'HOUALLOW': 772.73, 'TRAALLOW': 154.55, 'OTALLOW': 386.36, 'GOSI_COMP': -1527.5, 'GOSI_EMP': -1267.5, 'ALPPOUT': 1868.18, 'EOSP': 441.1, 'ANNUALP': 1089.77, 'GROSS': 10586.36, 'MEDICAL': 400.0, 'IQAMA': 500.0, 'WORKPER': 300.0, 'NET': 9318.86, 'NETCOST': 13313.86}
        self._validate_payslip(payslip, payslip_results)

    def test_saudi_payslip_attendance_full(self):
        self.env['hr.attendance'].create([{  # noqa: OLS03001
            'employee_id': self.saudi_employee.id,
            'check_in': datetime(2026, 4, day, 8, 0, 0),
            'check_out': datetime(2026, 4, day, 16, 0, 0),
        } for day in range(1, 31) if date(2026, 4, day).weekday() not in (5, 6)])  # exclude weekends

        payslip = self._generate_payslip(date(2026, 4, 1), date(2026, 4, 30), employee_id=self.saudi_employee.id,
            version_id=self.saudi_employee.version_id.id,
            struct_id=self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure').id)
        payslip_results = {'BASIC': 12000.0, 'HOUALLOW': 1000.0, 'TRAALLOW': 200.0, 'OTALLOW': 500.0, 'GOSI_COMP': -1527.5, 'GOSI_EMP': -1267.5, 'EOSP': 570.83, 'ANNUALP': 1089.77, 'GROSS': 13700.0, 'IQAMA': 500.0, 'MEDICAL': 400.0, 'WORKPER': 300.0, 'NET': 12432.5, 'NETCOST': 16427.5}
        self._validate_payslip(payslip, payslip_results)

    def test_payslip_attendance_overtime(self):
        self.env['hr.attendance'].create([{  # noqa: OLS03001
            'employee_id': self.saudi_employee.id,
            'check_in': datetime(2026, 4, day, 8, 0, 0),
            'check_out': datetime(2026, 4, day, 16, 0, 0),
        } for day in range(1, 31) if date(2026, 4, day).weekday() not in (5, 6)])  # exclude weekends
        self.env['hr.attendance'].create({  # noqa: OLS03001
            'employee_id': self.saudi_employee.id,
            'check_in': datetime(2026, 4, 1, 17, 0, 0),
            'check_out': datetime(2026, 4, 1, 21, 0, 0),
        })  # overtime
        payslip = self._generate_payslip(date(2026, 4, 1), date(2026, 4, 30), employee_id=self.saudi_employee.id,
            version_id=self.saudi_employee.version_id.id,
            struct_id=self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure').id)
        payslip.compute_sheet()
        payslip_results = {'BASIC': 12000.0, 'HOUALLOW': 1000.0, 'TRAALLOW': 200.0, 'OTALLOW': 500.0, 'GOSI_COMP': -1527.5, 'GOSI_EMP': -1267.5, 'OT': 467.05, 'EOSP': 570.83, 'ANNUALP': 1089.77, 'GROSS': 14167.05, 'IQAMA': 500.0, 'MEDICAL': 400.0, 'WORKPER': 300.0, 'NET': 12899.55, 'NETCOST': 16894.55}
        self._validate_payslip(payslip, payslip_results)

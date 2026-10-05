# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.tests.common import tagged

from .common import TestSACommon


@tagged('post_install', 'post_install_l10n', '-at_install', 'payslips_validation')
class TestHourlyWage(TestSACommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.saudi_employee.version_id.write({
            'wage_type': 'hourly',
            'hourly_wage': 50,
            'l10n_sa_housing_allowance': 2.5,
            'l10n_sa_transportation_allowance': 1.5,
            'l10n_sa_other_allowances': 1,
        })

    def test_saudi_payslip_hourly_wage(self):
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

        payslip = self._generate_payslip(date(2026, 4, 1), date(2026, 4, 30), employee_id=self.saudi_employee.id,
            version_id=self.saudi_employee.version_id.id,
            struct_id=self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure').id)
        payslip_results = {'BASIC': 6800.0, 'HOUALLOW': 340.0, 'TRAALLOW': 204.0, 'OTALLOW': 136.0, 'GOSI_COMP': -1085.7, 'GOSI_EMP': -900.9, 'ALPPOUT': 1320.0, 'EOSP': 311.67, 'ANNUALP': 770.0, 'GROSS': 7480.0, 'MEDICAL': 400.0, 'IQAMA': 500.0, 'WORKPER': 300.0, 'NET': 6579.1, 'NETCOST': 9765.7}
        self._validate_payslip(payslip, payslip_results)

    def test_saudi_payslip_hourly_wage_full(self):
        payslip = self._generate_payslip(date(2026, 4, 1), date(2026, 4, 30), employee_id=self.saudi_employee.id,
            version_id=self.saudi_employee.version_id.id,
            struct_id=self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure').id)
        payslip_results = {'BASIC': 8800.0, 'HOUALLOW': 440.0, 'TRAALLOW': 264.0, 'OTALLOW': 176.0, 'GOSI_COMP': -1085.7, 'GOSI_EMP': -900.9, 'EOSP': 403.33, 'ANNUALP': 770.0, 'GROSS': 9680.0, 'MEDICAL': 400.0, 'IQAMA': 500.0, 'WORKPER': 300.0, 'NET': 8779.1, 'NETCOST': 11965.7}
        self._validate_payslip(payslip, payslip_results)

    def test_payslip_hourly_wage_overtime(self):
        ot_work_entry_type = self.env.ref('hr_work_entry.sa_work_entry_type_overtime')
        ot_work_entry_type.requires_allocation = False
        self.env['hr.leave'].create({
            'name': 'OT',
            'employee_id': self.saudi_employee.id,
            'request_date_from': date(2026, 4, 1),
            'request_date_to': date(2026, 4, 1),
            'request_hour_from': 18,
            'request_hour_to': 22,
            'number_of_hours': 4,
            'work_entry_type_id': ot_work_entry_type.id,
        })
        payslip = self._generate_payslip(date(2026, 4, 1), date(2026, 4, 30), employee_id=self.saudi_employee.id,
            version_id=self.saudi_employee.version_id.id,
            struct_id=self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure').id)
        payslip.compute_sheet()
        payslip_results = {'BASIC': 8800.0, 'HOUALLOW': 440.0, 'TRAALLOW': 264.0, 'OTALLOW': 176.0, 'GOSI_COMP': -1085.7, 'GOSI_EMP': -900.9, 'OT': 220.0, 'EOSP': 403.33, 'ANNUALP': 770.0, 'GROSS': 9900.0, 'IQAMA': 500.0, 'MEDICAL': 400.0, 'WORKPER': 300.0, 'NET': 8999.1, 'NETCOST': 12185.7}
        self._validate_payslip(payslip, payslip_results)

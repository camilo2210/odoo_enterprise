# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, datetime

from odoo.tests.common import tagged

from .common import TestSACommon


@tagged('post_install', 'post_install_l10n', '-at_install', 'payslips_validation')
class TestMultiVersionPayslip(TestSACommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.first_version = cls.saudi_employee.version_id
        cls.second_version = cls.saudi_employee.create_version({
            'date_version': date(2026, 8, 15),
            'wage': 15000,
            'l10n_sa_housing_allowance': 1500,
            'l10n_sa_transportation_allowance': 300,
            'l10n_sa_other_allowances': 700,
        })

    def test_multi_version_monthly_schedule(self):
        payslip = self._generate_payslip(date(2026, 8, 1), date(2026, 8, 31), employee_id=self.saudi_employee.id,
            version_id=self.first_version.id,
            struct_id=self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure').id)
        payslip_results = {'BASIC': 13571.43, 'HOUALLOW': 1261.9, 'TRAALLOW': 252.38, 'OTALLOW': 604.76, 'GOSI_COMP': -1938.75, 'GOSI_EMP': -1608.75, 'EOSP': 729.17, 'ANNUALP': 1307.54, 'GROSS': 15690.48, 'MEDICAL': 400.0, 'IQAMA': 500.0, 'WORKPER': 300.0, 'NET': 14081.73, 'NETCOST': 18829.23}
        self._validate_payslip(payslip, payslip_results)

    def test_multi_version_30_monthly_schedule(self):
        self.saudi_employee.version_ids.write({
            'schedule_pay': '30_monthly',
            'resource_calendar_id': self.sa_full_week_calendar.id
        })
        payslip = self._generate_payslip(date(2026, 8, 1), date(2026, 8, 31), employee_id=self.saudi_employee.id,
            version_id=self.first_version.id,
            struct_id=self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure').id)
        payslip_results = {'BASIC': 14100.0, 'HOUALLOW': 1316.67, 'TRAALLOW': 263.33, 'OTALLOW': 630.0, 'GOSI_COMP': -1938.75, 'GOSI_EMP': -1608.75, 'EOSP': 729.17, 'ANNUALP': 951.42, 'GROSS': 16310.0, 'MEDICAL': 400.0, 'IQAMA': 500.0, 'WORKPER': 300.0, 'NET': 14701.25, 'NETCOST': 19448.75}
        self._validate_payslip(payslip, payslip_results)

    def test_multi_version_calendar_days_schedule(self):
        self.saudi_employee.version_ids.write({
            'resource_calendar_id': self.sa_full_week_calendar.id
        })
        payslip = self._generate_payslip(date(2026, 8, 1), date(2026, 8, 31), employee_id=self.saudi_employee.id,
            version_id=self.first_version.id,
            struct_id=self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure').id)
        payslip_results = {'BASIC': 13645.16, 'HOUALLOW': 1274.19, 'TRAALLOW': 254.84, 'OTALLOW': 609.68, 'GOSI_COMP': -1938.75, 'GOSI_EMP': -1608.75, 'EOSP': 729.17, 'ANNUALP': 891.02, 'GROSS': 15783.87, 'MEDICAL': 400.0, 'IQAMA': 500.0, 'WORKPER': 300.0, 'NET': 14175.12, 'NETCOST': 18922.62}
        self._validate_payslip(payslip, payslip_results)

    def use_hourly_wage(self):
        self.first_version.write({
            'wage_type': 'hourly',
            'hourly_wage': 50,
            'l10n_sa_housing_allowance': 2.5,
            'l10n_sa_transportation_allowance': 1.5,
            'l10n_sa_other_allowances': 1,
        })
        self.second_version.write({
            'wage_type': 'hourly',
            'hourly_wage': 70,
            'l10n_sa_housing_allowance': 4,
            'l10n_sa_transportation_allowance': 2,
            'l10n_sa_other_allowances': 2,
        })

    def test_multi_version_hourly_wage(self):
        self.use_hourly_wage()
        payslip = self._generate_payslip(date(2026, 8, 1), date(2026, 8, 31), employee_id=self.saudi_employee.id,
            version_id=self.first_version.id,
            struct_id=self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure').id)
        payslip_results = {'BASIC': 10160.0, 'HOUALLOW': 552.0, 'TRAALLOW': 296.0, 'OTALLOW': 256.0, 'GOSI_COMP': -1460.76, 'GOSI_EMP': -1212.12, 'EOSP': 546.0, 'ANNUALP': 938.67, 'GROSS': 11264.0, 'MEDICAL': 400.0, 'IQAMA': 500.0, 'WORKPER': 300.0, 'NET': 10051.88, 'NETCOST': 13924.76}
        self._validate_payslip(payslip, payslip_results)

    def test_multi_version_hourly_wage_with_30_monthly_schedule(self):
        self.use_hourly_wage()
        self.saudi_employee.version_ids.write({
            'schedule_pay': '30_monthly',
            'resource_calendar_id': self.sa_full_week_calendar.id
        })
        payslip = self._generate_payslip(date(2026, 8, 1), date(2026, 8, 31), employee_id=self.saudi_employee.id,
            version_id=self.first_version.id,
            struct_id=self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure').id)
        payslip_results = {'BASIC': 15120.0, 'HOUALLOW': 824.0, 'TRAALLOW': 440.0, 'OTALLOW': 384.0, 'GOSI_COMP': -2086.8, 'GOSI_EMP': -1731.6, 'EOSP': 780.0, 'ANNUALP': 978.13, 'GROSS': 16768.0, 'MEDICAL': 400.0, 'IQAMA': 500.0, 'WORKPER': 300.0, 'NET': 15036.4, 'NETCOST': 20054.8}
        self._validate_payslip(payslip, payslip_results)

    def test_multi_version_attendance(self):
        if self.env["ir.module.module"]._get("hr_payroll_attendance").state != "installed":
            self.skipTest("The test was skipped because the 'hr_payroll_attendance' module isn’t installed; therefore, attendance-based entries are unavailable.")
        self.env['hr.attendance'].create([{  # noqa: OLS03001
            'employee_id': self.saudi_employee.id,
            'check_in': datetime(2026, 8, day, 8, 0, 0),
            'check_out': datetime(2026, 8, day, 16, 0, 0),
        } for day in range(1, 32) if date(2026, 8, day).weekday() not in (5, 6)])  # exclude weekends
        payslip = self._generate_payslip(date(2026, 8, 1), date(2026, 8, 31), employee_id=self.saudi_employee.id,
            version_id=self.first_version.id,
            struct_id=self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure').id)
        payslip_results = {'BASIC': 13571.43, 'HOUALLOW': 1261.9, 'TRAALLOW': 252.38, 'OTALLOW': 604.76, 'GOSI_COMP': -1938.75, 'GOSI_EMP': -1608.75, 'EOSP': 729.17, 'ANNUALP': 1307.54, 'GROSS': 15690.48, 'MEDICAL': 400.0, 'IQAMA': 500.0, 'WORKPER': 300.0, 'NET': 14081.73, 'NETCOST': 18829.23}
        self._validate_payslip(payslip, payslip_results)

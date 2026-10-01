# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.tests.common import freeze_time, tagged
from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon


@tagged('post_install', 'post_install_l10n', '-at_install', 'payslips_validation')
@freeze_time('2024-01-01')
class TestPayslipValidation(TestPayslipValidationCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestPayslipValidationCommon.setup_country('lu')
    def setUpClass(cls):
        super().setUpClass()
        resource_calendar = cls.env['resource.calendar'].create({
            'name': 'LUX Calendar',
            'company_id': cls.env.company.id,
            'full_time_required_hours': 40,
        })
        cls._setup_common(
            country=cls.env.ref('base.lu'),
            structure=cls.env.ref('l10n_lu_hr_payroll.hr_payroll_structure_lux_employee_salary'),
            structure_type=cls.env.ref('l10n_lu_hr_payroll.structure_type_employee_lux'),
            tz="Europe/Brussels",
            version_fields={
                'wage': 4000,
                'l10n_lu_meal_voucher_amount': 50.4,
                'contract_date_start': date(2024, 1, 1),
                'date_version': date(2024, 1, 1),
            },
            employee_fields={
                'l10n_lu_tax_credit_cis': True,
                'l10n_lu_tax_id_number': '123',
            },
            resource_calendar=resource_calendar,
        )

    def test_basic_payslip(self):
        self.version.wage = 4250
        self.version.l10n_lu_meal_voucher_amount = 0
        self.employee.l10n_lu_tax_credit_cis = False
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 4250.0, 'GROSS': 4250.0, 'HEALTH_FUND': 119.0, 'CASH_SICKNESS_FUND': 10.63, 'RETIREMENT_FUND': 340.0, 'DEPENDENCY_INSURANCE': 50.5, 'TOTAL_CONTRIBUTIONS': 520.13, 'WAGE_SUPPLEMENT_70_ALW': 0.0, 'OVERTIME_ALW': 0.0, 'OVERTIME_SUPPLEMENT_40_ALW': 0.0, 'TOTAL_ALLOWANCES': 0.0, 'TAXABLE_AMOUNT': 3780.38, 'TAXES': 534.6, 'CISSM': 0.0, 'NET_TEMP': 3195.27, 'NET': 3195.27}
        self._validate_payslip(payslip, payslip_results)

    def test_basic_payslip_with_benefits(self):
        self.version.write({
            'wage': 7500,
            'l10n_lu_meal_voucher_amount': 2.80,
            'l10n_lu_alw_vehicle': 300,
            'l10n_lu_bik_vehicle': 500,
            'l10n_lu_bik_vehicle_vat_included': False,
        })
        self.employee.write({
            'l10n_lu_deduction_ac_ae_daily': 7.26,
            'l10n_lu_deduction_fd_daily': 8.58,
            'l10n_lu_tax_credit_cis': True,
        })

        self.version.wage = 7500
        self.version.l10n_lu_meal_voucher_amount = 2.80
        payslip = self._generate_payslip(date(2024, 10, 1), date(2024, 10, 31))
        input_wage_supplement_70 = self.env.ref(
            'l10n_lu_hr_payroll.l10n_lu_employees_wage_supplement_70')
        input_overtime = self.env.ref(
            'l10n_lu_hr_payroll.l10n_lu_employees_overtime')
        input_wage_supplement_40 = self.env.ref(
            'l10n_lu_hr_payroll.l10n_lu_employees_overtime_supplement_40')
        input_wage_supplement_150 = self.env.ref(
            'l10n_lu_hr_payroll.l10n_lu_employees_overtime_supplement_150')
        input_wage_supplement_200 = self.env.ref(
            'l10n_lu_hr_payroll.l10n_lu_employees_overtime_supplement_200')

        for code, value in {
            input_wage_supplement_70.code: 10,
            input_overtime.code: 10,
            input_wage_supplement_40.code: 10,
            input_wage_supplement_150.code: 10,
            input_wage_supplement_200.code: 10,
        }.items():
            payslip._set_input_value(code, value)
        payslip.compute_sheet()
        payslip_results = {'BASIC': 7500.0, 'VEHICLE_ALLOWANCE': 300.0, 'BIK_VEHICLE': 500.0, 'WAGE_SUPPLEMENT_70': 303.47, 'OVERTIME': 433.53, 'OVERTIME_SUPPLEMENT_150': 650.29, 'OVERTIME_SUPPLEMENT_200': 867.05, 'OVERTIME_SUPPLEMENT_40': 173.41, 'GROSS': 10727.75, 'CASH_SICKNESS_FUND': 20.26, 'DEPENDENCY_INSURANCE': 117.52, 'HEALTH_FUND': 253.04, 'RETIREMENT_FUND': 688.28, 'TOTAL_CONTRIBUTIONS': 1079.09, 'AC_AE': 181.5, 'FD': 214.5, 'OVERTIME_ALW': 421.39, 'OVERTIME_SUPPLEMENT_40_ALW': 173.41, 'WAGE_SUPPLEMENT_70_ALW': 303.47, 'TOTAL_ALLOWANCES': 1294.27, 'TAXABLE_AMOUNT': 8471.91, 'TAXES': 2474.6, 'CIS': 0.0, 'CISSM': 0.0, 'CIS_CI_CO2': 0.0, 'NET_TEMP': 7174.05, 'BIK_VEHICLE_NET': 500.0, 'MEAL_VOUCHERS': 50.4, 'NET': 6623.65}
        self._validate_payslip(payslip, payslip_results)

    def test_basic_payslip_incomplete_month(self):
        self.version.wage = 4250
        self.version.l10n_lu_meal_voucher_amount = 0
        self.employee.write({
            'l10n_lu_deduction_ac_ae_daily': 7.26,
            'l10n_lu_deduction_fd_daily': 8.58,
            'l10n_lu_tax_credit_cis': True,
        })
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 15))
        payslip_results = {'BASIC': 2032.61, 'GROSS': 2032.61, 'HEALTH_FUND': 56.91, 'CASH_SICKNESS_FUND': 5.08, 'RETIREMENT_FUND': 162.61, 'DEPENDENCY_INSURANCE': 23.88, 'TOTAL_CONTRIBUTIONS': 248.48, 'FD': 103.28, 'AC_AE': 87.39, 'WAGE_SUPPLEMENT_70_ALW': 0.0, 'OVERTIME_ALW': 0.0, 'OVERTIME_SUPPLEMENT_40_ALW': 0.0, 'TOTAL_ALLOWANCES': 190.67, 'TAXABLE_AMOUNT': 1617.34, 'TAXES': 168.8, 'CIS': -21.51, 'CIS_CI_CO2': -6.02, 'CISSM': 0.0, 'NET_TEMP': 1642.86, 'NET': 1642.86}
        self._validate_payslip(payslip, payslip_results)

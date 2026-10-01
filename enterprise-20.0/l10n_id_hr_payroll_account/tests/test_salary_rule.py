# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, datetime
from odoo.tests import tagged
from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon

PERIOD = {
    1: (1, 31),
    2: (1, 28),
    3: (1, 31),
    4: (1, 30),
    5: (1, 31),
    6: (1, 30),
    7: (1, 31),
    8: (1, 31),
    9: (1, 30),
    10: (1, 31),
    11: (1, 30),
    12: (1, 31),
}


@tagged('post_install', 'post_install_l10n', '-at_install', 'payslips_validation')
class TestPayslipValidation(TestPayslipValidationCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestPayslipValidationCommon.setup_country('id')
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_common(
            country=cls.env.ref('base.id'),
            structure=cls.env.ref('l10n_id_hr_payroll.hr_payroll_structure_id_employee_salary'),
            structure_type=cls.env.ref('l10n_id_hr_payroll.structure_type_employee_id'),
            version_fields={
                'employee_type_id': cls.env.ref('l10n_id_hr_payroll.l10n_id_employee_type_permanent').id,
                'wage': 1e7,
                'l10n_id_bpjs_jkk': 0.0024,  # 0.24%
            },
            resource_calendar=cls.env.ref('l10n_id_hr_payroll.resource_calendar_standard'),
        )

    def test_pph_tk0(self):
        """ Basic payslip with TK/0 (1)"""
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        self.assertEqual(len(payslip.input_line_ids), 3)
        self.assertEqual(len(payslip.worked_days_line_ids), 1)

        attendance_data = payslip._get_worked_days_line_values(['002.00'], ['amount', 'number_of_days', 'number_of_hours'], True)['002.00']['sum']
        self.assertAlmostEqual(attendance_data['amount'], 10000000, places=2)
        self.assertAlmostEqual(attendance_data['number_of_days'], 23)
        self.assertAlmostEqual(attendance_data['number_of_hours'], 184)
        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_JKK_JKM': 1.0, 'IN_BPJS_KES': 1.0, 'BASIC': 10000000.0, 'BASE': 10000000.0, 'BPJS_JKK': 24000.0, 'BPJS_JKM': 30000.0, 'BPJS_Kesehatan': 400000.0, 'GROSS_TOTAL': 10454000.0, 'GROSS': 10454000.0, 'JHT': -200000.0, 'BPJS_KESEHATAN_DED': -100000.0, 'JP': -100000.0, 'PPH21': -261350.0, 'NET': 9338650.0}
        self._validate_payslip(payslip, payslip_results)

    def test_pph_tk2(self):
        """ Basic payslip with TK/2 (2)"""
        self.version.wage = 13e6
        self.employee.l10n_id_kode_ptkp = 'tk2'

        payslip = self._generate_payslip(date(2024, 6, 1), date(2024, 6, 30))

        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_JKK_JKM': 1.0, 'IN_BPJS_KES': 1.0, 'BASIC': 13000000.0, 'BASE': 13000000.0, 'BPJS_JKK': 31200.0, 'BPJS_JKM': 39000.0, 'BPJS_Kesehatan': 480000.0, 'GROSS_TOTAL': 13550200.0, 'GROSS': 13550200.0, 'JHT': -260000.0, 'BPJS_KESEHATAN_DED': -120000.0, 'JP': -100423.0, 'PPH21': -542008.0, 'NET': 11977569.0}
        self._validate_payslip(payslip, payslip_results)

    def test_with_unpaid_leave(self):
        """ Unpaid leave of 7 days (3) """
        self.version.wage = 6e6

        unpaid_leaves_to_create = [
            (datetime(2024, 6, 6), datetime(2024, 6, 6)),
            (datetime(2024, 6, 7), datetime(2024, 6, 7)),
            (datetime(2024, 6, 10), datetime(2024, 6, 10)),
            (datetime(2024, 6, 11), datetime(2024, 6, 11)),
            (datetime(2024, 6, 12), datetime(2024, 6, 12)),
            (datetime(2024, 6, 13), datetime(2024, 6, 13)),
            (datetime(2024, 6, 14), datetime(2024, 6, 14)),
        ]

        for date_from, date_to in unpaid_leaves_to_create:
            self._generate_leave(self.employee, date_from, date_to, self.env.ref('hr_work_entry.id_work_entry_type_unpaid_leave'))

        payslip = self._generate_payslip(date(2024, 6, 1), date(2024, 6, 30))

        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_JKK_JKM': 1.0, 'IN_BPJS_KES': 1.0, 'BASIC': 3900000.0, 'BASE': 3900000.0, 'BPJS_JKK': 9360.0, 'BPJS_JKM': 11700.0, 'BPJS_Kesehatan': 156000.0, 'GROSS_TOTAL': 4077060.0, 'GROSS': 4077060.0, 'JHT': -78000.0, 'BPJS_KESEHATAN_DED': -39000.0, 'JP': -39000.0, 'PPH21': 0.0, 'NET': 3744000.0}
        self._validate_payslip(payslip, payslip_results)

    def test_with_allowance(self):
        """ 50k/day meal allowance, 50k/day transport allowance, 20m wage"""
        self.version.wage = 2e7

        payslip = self._generate_payslip(
            date(2024, 6, 1),
            date(2024, 6, 30),
        )
        for code, value in {
            self.env.ref('l10n_id_hr_payroll.l10n_id_include_jkk_jkm_salary_rule').code: True,
            self.env.ref('l10n_id_hr_payroll.l10n_id_include_bpjs_kesehatan_salary_rule').code: True,
            self.env.ref('l10n_id_hr_payroll.salary_rule_id_transport_allowance').code: 1000000,
            self.env.ref('l10n_id_hr_payroll.salary_rule_id_meal_allowance').code: 1000000,
        }.items():
            payslip._set_input_value(code, value)
        payslip.compute_sheet()

        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_BPJS_KES': 1.0, 'IN_JKK_JKM': 1.0, 'BASIC': 20000000.0, 'MEAL': 1000000.0, 'TRANSPORT_ALW': 1000000.0, 'BASE': 22000000.0, 'BPJS_JKK': 48000.0, 'BPJS_JKM': 60000.0, 'BPJS_Kesehatan': 480000.0, 'GROSS_TOTAL': 22588000.0, 'GROSS': 22588000.0, 'JHT': -400000.0, 'BPJS_KESEHATAN_DED': -120000.0, 'JP': -100423.0, 'PPH21': -2032920.0, 'NET': 19346657.0}
        self._validate_payslip(payslip, payslip_results)

    def test_with_fixed_allowance(self):
        """ 2m fixed allowance, 20m wage"""
        self.version.wage = 2e7
        self.employee.l10n_id_fixed_allowance = 2e6

        payslip = self._generate_payslip(
            date(2024, 6, 1),
            date(2024, 6, 30),
        )

        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_JKK_JKM': 1.0, 'IN_BPJS_KES': 1.0, 'BASIC': 20000000.0, 'FIXED_ALW': 2000000.0, 'BASE': 22000000.0, 'BPJS_JKK': 52800.0, 'BPJS_JKM': 66000.0, 'BPJS_Kesehatan': 480000.0, 'GROSS_TOTAL': 22598800.0, 'GROSS': 22598800.0, 'JHT': -440000.0, 'BPJS_KESEHATAN_DED': -120000.0, 'JP': -100423.0, 'PPH21': -2033892.0, 'NET': 19305685.0}
        self._validate_payslip(payslip, payslip_results)

    def test_with_reimbursement(self):
        """ 5m wage weith 500k reimbursement """
        self.version.wage = 5e6

        payslip = self._generate_payslip(
            date(2024, 6, 1),
            date(2024, 6, 30),
        )
        for code, value in {
            self.env.ref('l10n_id_hr_payroll.l10n_id_include_jkk_jkm_salary_rule').code: True,
            self.env.ref('l10n_id_hr_payroll.l10n_id_include_bpjs_kesehatan_salary_rule').code: True,
            self.env.ref('l10n_id_hr_payroll.l10n_id_hr_payroll_structure_id_employee_salary_reimbursement_salary_rule').code: 5e5,
        }.items():
            payslip._set_input_value(code, value)
        payslip.compute_sheet()

        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_BPJS_KES': 1.0, 'IN_JKK_JKM': 1.0, 'BASIC': 5000000.0, 'BASE': 5000000.0, 'BPJS_JKK': 12000.0, 'BPJS_JKM': 15000.0, 'BPJS_Kesehatan': 200000.0, 'GROSS_TOTAL': 5727000.0, 'GROSS': 5227000.0, 'JHT': -100000.0, 'BPJS_KESEHATAN_DED': -50000.0, 'JP': -50000.0, 'PPH21': 0.0, 'REIMBURSEMENT': 500000.0, 'NET': 5300000.0}
        self._validate_payslip(payslip, payslip_results)

    def test_low_income_with_meal_alw(self):
        """ Wage of 2m with 50k/day meal allowance """
        self.version.wage = 2e6

        payslip = self._generate_payslip(
            date(2024, 6, 1),
            date(2024, 6, 30),
        )
        for code, value in {
            self.env.ref('l10n_id_hr_payroll.l10n_id_include_jkk_jkm_salary_rule').code: True,
            self.env.ref('l10n_id_hr_payroll.l10n_id_include_bpjs_kesehatan_salary_rule').code: True,
            self.env.ref('l10n_id_hr_payroll.salary_rule_id_meal_allowance').code: 1000000,
        }.items():
            payslip._set_input_value(code, value)
        payslip.compute_sheet()

        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_BPJS_KES': 1.0, 'IN_JKK_JKM': 1.0, 'BASIC': 2000000.0, 'MEAL': 1000000.0, 'BASE': 3000000.0, 'BPJS_JKK': 4800.0, 'BPJS_JKM': 6000.0, 'BPJS_Kesehatan': 80000.0, 'GROSS_TOTAL': 3090800.0, 'GROSS': 3090800.0, 'JHT': -40000.0, 'BPJS_KESEHATAN_DED': -20000.0, 'JP': -20000.0, 'PPH21': 0.0, 'NET': 2920000.0}
        self._validate_payslip(payslip, payslip_results)

    def test_with_insurance_and_meal_alw(self):
        """ 1m wage with 300k/day meal allowance and 500k/month insurance allowance (8)"""

        self.version.wage = 1e6

        payslip = self._generate_payslip(
            date(2024, 6, 1),
            date(2024, 6, 30),
        )
        for code, value in {
            self.env.ref('l10n_id_hr_payroll.l10n_id_include_jkk_jkm_salary_rule').code: True,
            self.env.ref('l10n_id_hr_payroll.l10n_id_include_bpjs_kesehatan_salary_rule').code: True,
            self.env.ref('l10n_id_hr_payroll.salary_rule_id_meal_allowance').code: 6e6,
            self.env.ref('l10n_id_hr_payroll.salary_rule_id_insurance').code: 5e5,
        }.items():
            payslip._set_input_value(code, value)
        payslip.compute_sheet()

        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_BPJS_KES': 1.0, 'IN_JKK_JKM': 1.0, 'BASIC': 1000000.0, 'INSURANCE': 500000.0, 'MEAL': 6000000.0, 'BASE': 7500000.0, 'BPJS_JKK': 2400.0, 'BPJS_JKM': 3000.0, 'BPJS_Kesehatan': 40000.0, 'GROSS_TOTAL': 7545400.0, 'GROSS': 7545400.0, 'JHT': -20000.0, 'BPJS_KESEHATAN_DED': -10000.0, 'JP': -10000.0, 'PPH21': -113181.0, 'NET': 6846819.0}
        self._validate_payslip(payslip, payslip_results)

    def test_no_jkk_jkm(self):
        """ Exclude JKK, JKM (9) """
        self.version.wage = 5e6

        payslip = self._generate_payslip(
            date(2024, 6, 1),
            date(2024, 6, 30),
        )
        for code, value in {
            self.env.ref('l10n_id_hr_payroll.l10n_id_include_jkk_jkm_salary_rule').code: False,
            self.env.ref('l10n_id_hr_payroll.l10n_id_include_bpjs_kesehatan_salary_rule').code: True,
            self.env.ref('l10n_id_hr_payroll.salary_rule_id_laptop').code: 3e5,
        }.items():
            payslip._set_input_value(code, value)
        payslip.compute_sheet()

        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_BPJS_KES': 1.0, 'BASIC': 5000000.0, 'LAPTOP': 300000.0, 'BASE': 5300000.0, 'BPJS_Kesehatan': 200000.0, 'GROSS_TOTAL': 5500000.0, 'GROSS': 5500000.0, 'BPJS_KESEHATAN_DED': -50000.0, 'PPH21': -13750.0, 'NET': 5236250.0}
        self._validate_payslip(payslip, payslip_results)

    def test_no_bpjs_kesehatan(self):
        """ Test payslip without BPJS kesehatan (10) """
        self.version.wage = 5e6

        payslip = self._generate_payslip(
            date(2024, 6, 1),
            date(2024, 6, 30),
        )

        for code, value in {
            self.env.ref('l10n_id_hr_payroll.l10n_id_include_jkk_jkm_salary_rule').code: True,
            self.env.ref('l10n_id_hr_payroll.l10n_id_include_bpjs_kesehatan_salary_rule').code: False,
            self.env.ref('l10n_id_hr_payroll.salary_rule_id_laptop').code: 3e5,
        }.items():
            payslip._set_input_value(code, value)
        payslip.compute_sheet()

        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_JKK_JKM': 1.0, 'BASIC': 5000000.0, 'LAPTOP': 300000.0, 'BASE': 5300000.0, 'BPJS_JKK': 12000.0, 'BPJS_JKM': 15000.0, 'GROSS_TOTAL': 5327000.0, 'GROSS': 5327000.0, 'JHT': -100000.0, 'JP': -50000.0, 'PPH21': 0.0, 'NET': 5150000.0}
        self._validate_payslip(payslip, payslip_results)

    def test_no_allowance_ded(self):
        """ Test allowance and deduction being removed from payslip (12)"""
        payslip = self._generate_payslip(
            date(2024, 6, 1),
            date(2024, 6, 30),
        )

        for code, value in {
            self.env.ref('l10n_id_hr_payroll.l10n_id_include_jkk_jkm_salary_rule').code: False,
            self.env.ref('l10n_id_hr_payroll.l10n_id_include_bpjs_kesehatan_salary_rule').code: False,
            self.env.ref('l10n_id_hr_payroll.salary_rule_id_laptop').code: 3e5,
        }.items():
            payslip._set_input_value(code, value)
        payslip.compute_sheet()

        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'BASIC': 10000000.0, 'LAPTOP': 300000.0, 'BASE': 10300000.0, 'GROSS_TOTAL': 10300000.0, 'GROSS': 10300000.0, 'PPH21': -231750.0, 'NET': 10068250.0}
        self._validate_payslip(payslip, payslip_results)

    def test_allowance_thr(self):
        """ Test 20m salary with THR on April """
        self.version.wage = 2e7

        payslip = self._generate_payslip(
            date(2024, 4, 1),
            date(2024, 4, 30),
        )
        for code, value in {
            self.env.ref('l10n_id_hr_payroll.l10n_id_include_jkk_jkm_salary_rule').code: True,
            self.env.ref('l10n_id_hr_payroll.l10n_id_include_bpjs_kesehatan_salary_rule').code: True,
            self.env.ref('l10n_id_hr_payroll.salary_rule_id_thr').code: 1e7,
        }.items():
            payslip._set_input_value(code, value)
        payslip.compute_sheet()

        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_BPJS_KES': 1.0, 'IN_JKK_JKM': 1.0, 'BASIC': 20000000.0, 'THR': 10000000.0, 'BASE': 30000000.0, 'BPJS_JKK': 48000.0, 'BPJS_JKM': 60000.0, 'BPJS_Kesehatan': 480000.0, 'GROSS_TOTAL': 30588000.0, 'GROSS': 30588000.0, 'JHT': -400000.0, 'BPJS_KESEHATAN_DED': -120000.0, 'JP': -100423.0, 'PPH21': -3976440.0, 'NET': 25403137.0}
        self._validate_payslip(payslip, payslip_results)

    # =============================
    # END OF YEAR/CONTRACT PAYMENTS
    # =============================
    def test_end_of_year_payment_not_validated(self):
        """ Test if slip is not validated yet, then yearly gross=gross of that year only with no accumulation """
        self.version.wage = 1e7

        for i in range(1, 13):
            drange = PERIOD[i]
            slip = self._generate_payslip(
                date(2024, i, drange[0]),
                date(2024, i, drange[1])
            )

            if i == 12:
                payslip = slip

        lines_to_compare = payslip._get_line_values(['GROSS'])
        self.assertAlmostEqual(lines_to_compare['GROSS'][payslip.id]['total'], 10454e3)

    def test_end_of_year_payment(self):
        """ Generate payslip from january to dec then focus on the end of year (15) """
        self.version.wage = 2e7

        for i in range(1, 13):
            drange = PERIOD[i]
            slip = self._generate_payslip(
                date(2024, i, drange[0]),
                date(2024, i, drange[1]),
            )
            slip.action_payslip_done()

            if i == 12:
                payslip = slip

        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_JKK_JKM': 1.0, 'IN_BPJS_KES': 1.0, 'BASIC': 20000000.0, 'BASE': 20000000.0, 'BPJS_JKK': 48000.0, 'BPJS_JKM': 60000.0, 'BPJS_Kesehatan': 480000.0, 'GROSS_TOTAL': 20588000.0, 'GROSS': 20588000.0, 'JHT': -400000.0, 'BPJS_KESEHATAN_DED': -120000.0, 'JP': -100423.0, 'JABATAN': 6000000.0, 'JHT_JP': -6005076.0, 'PTKP': 54000000.0, 'PKP': 181050000.0, 'PPH21': -775380.0, 'NET': 18604197.0}
        self._validate_payslip(payslip, payslip_results)

    def test_end_of_year_payment_2(self):
        """ use 10m wage check only end of year (16)"""
        for i in range(1, 13):
            drange = PERIOD[i]
            slip = self._generate_payslip(
                date(2024, i, drange[0]),
                date(2024, i, drange[1]),
            )
            slip.action_payslip_done()

            if i == 12:
                payslip = slip

        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_JKK_JKM': 1.0, 'IN_BPJS_KES': 1.0, 'BASIC': 10000000.0, 'BASE': 10000000.0, 'BPJS_JKK': 24000.0, 'BPJS_JKM': 30000.0, 'BPJS_Kesehatan': 400000.0, 'GROSS_TOTAL': 10454000.0, 'GROSS': 10454000.0, 'JHT': -200000.0, 'BPJS_KESEHATAN_DED': -100000.0, 'JP': -100000.0, 'JABATAN': 6000000.0, 'JHT_JP': -3600000.0, 'PTKP': 54000000.0, 'PKP': 61848000.0, 'PPH21': -402350.0, 'NET': 9197650.0}
        self._validate_payslip(payslip, payslip_results)

    def test_end_of_contract(self):
        """ Contract lasts until end of August (17) """
        self.version.contract_date_end = date(2024, 8, 31)

        for i in range(1, 9):
            drange = PERIOD[i]
            slip = self._generate_payslip(
                date(2024, i, drange[0]),
                date(2024, i, drange[1]),
            )
            slip.action_payslip_done()

            if i == 8:
                payslip = slip

        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_JKK_JKM': 1.0, 'IN_BPJS_KES': 1.0, 'BASIC': 10000000.0, 'BASE': 10000000.0, 'BPJS_JKK': 24000.0, 'BPJS_JKM': 30000.0, 'BPJS_Kesehatan': 400000.0, 'GROSS_TOTAL': 10454000.0, 'GROSS': 10454000.0, 'JHT': -200000.0, 'BPJS_KESEHATAN_DED': -100000.0, 'JP': -100000.0, 'JABATAN': 4000000.0, 'JHT_JP': -2400000.0, 'PTKP': 54000000.0, 'PKP': 23232000.0, 'PPH21': 667850.0, 'NET': 10267850.0}
        self._validate_payslip(payslip, payslip_results)

    def test_end_of_contract_2(self):
        """ 15 Jan - 31 Dec + get the December's payslip (19) """
        self.version.contract_date_start = date(2024, 1, 15)

        for i in range(1, 13):
            drange = PERIOD[i]
            slip = self._generate_payslip(
                date(2024, i, drange[0]),
                date(2024, i, drange[1]),
            )
            slip.action_payslip_done()

            if i == 12:
                payslip = slip

        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_JKK_JKM': 1.0, 'IN_BPJS_KES': 1.0, 'BASIC': 10000000.0, 'BASE': 10000000.0, 'BPJS_JKK': 24000.0, 'BPJS_JKM': 30000.0, 'BPJS_Kesehatan': 400000.0, 'GROSS_TOTAL': 10454000.0, 'GROSS': 10454000.0, 'JHT': -200000.0, 'BPJS_KESEHATAN_DED': -100000.0, 'JP': -100000.0, 'JABATAN': 5784134.78, 'JHT_JP': -3469565.22, 'PTKP': 54000000.0, 'PKP': 57649000.0, 'PPH21': -234885.0, 'NET': 9365115.0}
        self._validate_payslip(payslip, payslip_results)

    def test_end_of_contract_3(self):
        """15 Jan - end of year, payroll cycle at 15th"""
        self.version.contract_date_start = date(2024, 1, 15)

        for i in range(1, 12):
            slip = self._generate_payslip(
                date(2024, i, 15),
                date(2024, i + 1, 14)
            )
            slip.action_payslip_done()

            if i == 11:
                payslip = slip

        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_JKK_JKM': 1.0, 'IN_BPJS_KES': 1.0, 'BASIC': 10000000.0, 'BASE': 10000000.0, 'BPJS_JKK': 24000.0, 'BPJS_JKM': 30000.0, 'BPJS_Kesehatan': 400000.0, 'GROSS_TOTAL': 10454000.0, 'GROSS': 10454000.0, 'JHT': -200000.0, 'BPJS_KESEHATAN_DED': -100000.0, 'JP': -100000.0, 'JABATAN': 5500000.0, 'JHT_JP': -3300000.0, 'PTKP': 54000000.0, 'PKP': 52194000.0, 'PPH21': 32935.0, 'NET': 9632935.0}
        self._validate_payslip(payslip, payslip_results)

    def test_end_of_year_with_allowance(self):
        """ End of year testing with transport allowance (21) """
        self.version.contract_date_start = date(2024, 10, 1)
        self.version.wage = 2e7
        for i in range(10, 12):
            drange = PERIOD[i]
            slip = self._generate_payslip(
                date(2024, i, drange[0]),
                date(2024, i, drange[1]),
            )
            for code, value in {
                self.env.ref('l10n_id_hr_payroll.l10n_id_include_jkk_jkm_salary_rule').code: True,
                self.env.ref('l10n_id_hr_payroll.l10n_id_include_bpjs_kesehatan_salary_rule').code: True,
                self.env.ref('l10n_id_hr_payroll.salary_rule_id_transport_allowance').code: 2e6,
            }.items():
                slip._set_input_value(code, value)
            slip.compute_sheet()
            slip.action_payslip_done()

        payslip = self._generate_payslip(
            date(2024, 12, 1),
            date(2024, 12, 31),
        )
        for code, value in {
            self.env.ref('l10n_id_hr_payroll.l10n_id_include_jkk_jkm_salary_rule').code: True,
            self.env.ref('l10n_id_hr_payroll.l10n_id_include_bpjs_kesehatan_salary_rule').code: True,
            self.env.ref('l10n_id_hr_payroll.salary_rule_id_transport_allowance').code: 2e6,
        }.items():
            payslip._set_input_value(code, value)
        payslip.compute_sheet()
        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_BPJS_KES': 1.0, 'IN_JKK_JKM': 1.0, 'BASIC': 20000000.0, 'TRANSPORT_ALW': 2000000.0, 'BASE': 22000000.0, 'BPJS_JKK': 48000.0, 'BPJS_JKM': 60000.0, 'BPJS_Kesehatan': 480000.0, 'GROSS_TOTAL': 22588000.0, 'GROSS': 22588000.0, 'JHT': -400000.0, 'BPJS_KESEHATAN_DED': -120000.0, 'JP': -100423.0, 'JABATAN': 1500000.0, 'JHT_JP': -1501269.0, 'PTKP': 54000000.0, 'PKP': 10762000.0, 'PPH21': 3527740.0, 'NET': 24907317.0}
        self._validate_payslip(payslip, payslip_results)

    def test_new_joiner(self):
        """ New joiner starting in 15 January, payslip for January (22)"""
        self.version.wage = 2e7
        self.version.contract_date_start = date(2024, 1, 15)

        payslip = self._generate_payslip(
            date(2024, 1, 1),
            date(2024, 1, 31),
        )
        for code, value in {
            self.env.ref('l10n_id_hr_payroll.l10n_id_include_jkk_jkm_salary_rule').code: True,
            self.env.ref('l10n_id_hr_payroll.l10n_id_include_bpjs_kesehatan_salary_rule').code: 0,
        }.items():
            payslip._set_input_value(code, value)
        payslip.compute_sheet()

        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_JKK_JKM': 1.0, 'BASIC': 11304347.83, 'BASE': 11304347.83, 'BPJS_JKK': 27130.43, 'BPJS_JKM': 33913.04, 'GROSS_TOTAL': 11365391.31, 'GROSS': 11365391.31, 'JHT': -226086.96, 'JP': -100423.0, 'PPH21': -397788.0, 'NET': 10580049.87}
        self._validate_payslip(payslip, payslip_results)

    # =====================================
    # OTHERS: testing specific components by components for end of year payments
    # =============================================
    def test_pkp_ptkp_show_up(self):
        """ Only appear when end of contract and end of year. Also consider only the `date_to` field
        of the payslip"""

        # November 1-30 and December 1-31. November should not show while December should
        nov_payslip = self._generate_payslip(
            date(2024, 11, 1),
            date(2024, 11, 30)
        )
        dec_payslip = self._generate_payslip(
            date(2024, 12, 1),
            date(2024, 12, 31)
        )

        self.assertEqual(nov_payslip.l10n_id_include_pkp_ptkp, False)
        self.assertEqual(dec_payslip.l10n_id_include_pkp_ptkp, True)

        # November 15-Dec 14 should be True while December 15-Jan 14 should be False
        nov_payslip_2 = self._generate_payslip(
            date(2024, 11, 15),
            date(2024, 12, 14)
        )
        dec_payslip_2 = self._generate_payslip(
            date(2024, 12, 15),
            date(2025, 1, 14)
        )
        self.assertEqual(nov_payslip_2.l10n_id_include_pkp_ptkp, True)
        self.assertEqual(dec_payslip_2.l10n_id_include_pkp_ptkp, False)

    def test_end_of_year_jabatan(self):
        """" Test to make sure biaya jabatan at the end of year is correct"""
        # payroll cycle every 14th, employee starts from october
        payslip1 = self._generate_payslip(date(2024, 10, 15), date(2024, 11, 14))
        payslip1.action_payslip_done()
        payslip2 = self._generate_payslip(date(2024, 11, 15), date(2024, 12, 14))

        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_JKK_JKM': 1.0, 'IN_BPJS_KES': 1.0, 'BASIC': 10000000.0, 'BASE': 10000000.0, 'BPJS_JKK': 24000.0, 'BPJS_JKM': 30000.0, 'BPJS_Kesehatan': 400000.0, 'GROSS_TOTAL': 10454000.0, 'GROSS': 10454000.0, 'JHT': -200000.0, 'BPJS_KESEHATAN_DED': -100000.0, 'JP': -100000.0, 'JABATAN': 1000000.0, 'JHT_JP': -600000.0, 'PTKP': 54000000.0, 'PKP': 0.0, 'PPH21': 261350.0, 'NET': 9861350.0}
        self._validate_payslip(payslip2, payslip_results)

    def test_pkp_above_zero(self):
        """ Test that PKP is non-negative and when PKP is 0, then return all paid PPH21 amount """
        # joins november, pph21 of december is supposed to be -(pph21 of nov)
        self.version.contract_date_start = date(2024, 11, 1)

        nov_pslip = self._generate_payslip(
            date(2024, 11, 1),
            date(2024, 11, 3)
        )
        nov_pslip.action_payslip_done()

        dec_pslip = self._generate_payslip(
            date(2024, 12, 1),
            date(2024, 12, 31)
        )

        nov_payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_JKK_JKM': 1.0, 'IN_BPJS_KES': 1.0, 'BASIC': 10000000.0, 'BASE': 10000000.0, 'BPJS_JKK': 24000.0, 'BPJS_JKM': 30000.0, 'BPJS_Kesehatan': 400000.0, 'GROSS_TOTAL': 10454000.0, 'GROSS': 10454000.0, 'JHT': -200000.0, 'BPJS_KESEHATAN_DED': -100000.0, 'JP': -100000.0, 'PPH21': -261350.0, 'NET': 9338650.0}
        self._validate_payslip(nov_pslip, nov_payslip_results)

        dec_payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_JKK_JKM': 1.0, 'IN_BPJS_KES': 1.0, 'BASIC': 10000000.0, 'BASE': 10000000.0, 'BPJS_JKK': 24000.0, 'BPJS_JKM': 30000.0, 'BPJS_Kesehatan': 400000.0, 'GROSS_TOTAL': 10454000.0, 'GROSS': 10454000.0, 'JHT': -200000.0, 'BPJS_KESEHATAN_DED': -100000.0, 'JP': -100000.0, 'JABATAN': 1000000.0, 'JHT_JP': -600000.0, 'PTKP': 54000000.0, 'PKP': 0.0, 'PPH21': 261350.0, 'NET': 9861350.0}
        self._validate_payslip(dec_pslip, dec_payslip_results)

        self.assertEqual(dec_payslip_results['PKP'], 0)
        self.assertEqual(dec_payslip_results['PPH21'], -nov_payslip_results['PPH21'])

    def test_pph_tk0_gross_up(self):
        """ Basic payslip with TK/0 (1)"""
        self.version.l10n_id_payroll_type = 'gross_up'
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        self.assertEqual(len(payslip.input_line_ids), 3)
        self.assertEqual(len(payslip.worked_days_line_ids), 1)

        attendance_data = payslip._get_worked_days_line_values(['002.00'], ['amount', 'number_of_days', 'number_of_hours'], True)['002.00']['sum']
        self.assertAlmostEqual(attendance_data['amount'], 10000000, places=2)
        self.assertAlmostEqual(attendance_data['number_of_days'], 23)
        self.assertAlmostEqual(attendance_data['number_of_hours'], 184)
        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_JKK_JKM': 1.0, 'IN_BPJS_KES': 1.0, 'BASIC': 10000000.0, 'BPJS_JKK': 24000.0, 'BPJS_JKM': 30000.0, 'BPJS_Kesehatan': 400000.0, 'JHT_COMP': 370000.0, 'JP_COMP': 200000.0, 'BASE_GROSS_UP': 10454000.0, 'TAXALW': 323319.0, 'GROSS_TOTAL': 11347319.0, 'GROSS': 10777319.0, 'JHT': -200000.0, 'BPJS_KESEHATAN_DED': -100000.0, 'JP': -100000.0, 'PPH21': -323319.0, 'NET': 9600000.0}
        self._validate_payslip(payslip, payslip_results)

    def test_pph_tk2_gross_up(self):
        """ Basic payslip with TK/2 (2)"""
        self.version.l10n_id_payroll_type = 'gross_up'
        self.version.wage = 13e6
        self.employee.l10n_id_kode_ptkp = 'tk2'

        payslip = self._generate_payslip(date(2025, 6, 1), date(2025, 6, 30))

        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_JKK_JKM': 1.0, 'IN_BPJS_KES': 1.0, 'BASIC': 13000000.0, 'BPJS_JKK': 31200.0, 'BPJS_JKM': 39000.0, 'BPJS_Kesehatan': 480000.0, 'JHT_COMP': 481000.0, 'JP_COMP': 210948.0, 'BASE_GROSS_UP': 13550200.0, 'TAXALW': 713168.0, 'GROSS_TOTAL': 14955316.0, 'GROSS': 14263368.0, 'JHT': -260000.0, 'BPJS_KESEHATAN_DED': -120000.0, 'JP': -105474.0, 'PPH21': -713168.0, 'NET': 12514526.0}
        self._validate_payslip(payslip, payslip_results)

    def test_with_unpaid_leave_gross_up(self):
        """ Unpaid leave of 7 days (3) """
        self.version.l10n_id_payroll_type = 'gross_up'
        self.version.wage = 6e6

        unpaid_leaves_to_create = [
            (datetime(2025, 6, 5), datetime(2025, 6, 5)),
            (datetime(2025, 6, 6), datetime(2025, 6, 6)),
            (datetime(2025, 6, 9), datetime(2025, 6, 9)),
            (datetime(2025, 6, 10), datetime(2025, 6, 10)),
            (datetime(2025, 6, 11), datetime(2025, 6, 11)),
            (datetime(2025, 6, 12), datetime(2025, 6, 12)),
            (datetime(2025, 6, 13), datetime(2025, 6, 13)),
        ]

        for date_from, date_to in unpaid_leaves_to_create:
            self._generate_leave(self.employee, date_from, date_to, self.env.ref('hr_work_entry.id_work_entry_type_unpaid_leave'))

        payslip = self._generate_payslip(date(2025, 6, 1), date(2025, 6, 30))

        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_JKK_JKM': 1.0, 'IN_BPJS_KES': 1.0, 'BASIC': 4000000.0, 'BPJS_JKK': 9600.0, 'BPJS_JKM': 12000.0, 'BPJS_Kesehatan': 160000.0, 'JHT_COMP': 148000.0, 'JP_COMP': 80000.0, 'BASE_GROSS_UP': 4181600.0, 'TAXALW': 0.0, 'GROSS_TOTAL': 4409600.0, 'GROSS': 4181600.0, 'JHT': -80000.0, 'BPJS_KESEHATAN_DED': -40000.0, 'JP': -40000.0, 'PPH21': 0.0, 'NET': 3840000.0}
        self._validate_payslip(payslip, payslip_results)

    def test_with_allowance_gross_up(self):
        """ 50k/day meal allowance, 50k/day transport allowance, 20m wage"""
        self.version.l10n_id_payroll_type = 'gross_up'
        self.version.wage = 2e7

        payslip = self._generate_payslip(
            date(2025, 6, 1),
            date(2025, 6, 30)
        )
        for code, value in {
            self.env.ref('l10n_id_hr_payroll.l10n_id_include_jkk_jkm_salary_rule').code: True,
            self.env.ref('l10n_id_hr_payroll.l10n_id_include_bpjs_kesehatan_salary_rule').code: True,
            self.env.ref('l10n_id_hr_payroll.salary_rule_id_transport_allowance').code: 1000000,
            self.env.ref('l10n_id_hr_payroll.salary_rule_id_meal_allowance').code: 1000000,
        }.items():
            payslip._set_input_value(code, value)
        payslip.compute_sheet()

        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_BPJS_KES': 1.0, 'IN_JKK_JKM': 1.0, 'BASIC': 20000000.0, 'MEAL': 1000000.0, 'TRANSPORT_ALW': 1000000.0, 'BPJS_JKK': 48000.0, 'BPJS_JKM': 60000.0, 'BPJS_Kesehatan': 480000.0, 'JHT_COMP': 740000.0, 'JP_COMP': 210948.0, 'BASE_GROSS_UP': 22588000.0, 'TAXALW': 2509777.0, 'GROSS_TOTAL': 26048725.0, 'GROSS': 25097777.0, 'JHT': -400000.0, 'BPJS_KESEHATAN_DED': -120000.0, 'JP': -105474.0, 'PPH21': -2509777.0, 'NET': 21374526.0}
        self._validate_payslip(payslip, payslip_results)

    def test_with_fixed_allowance_gross_up(self):
        """ 2m fixed allowance, 20m wage"""
        self.version.l10n_id_payroll_type = 'gross_up'
        self.version.wage = 2e7
        self.employee.l10n_id_fixed_allowance = 2e6

        payslip = self._generate_payslip(
            date(2025, 6, 1),
            date(2025, 6, 30)
        )

        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_JKK_JKM': 1.0, 'IN_BPJS_KES': 1.0, 'BASIC': 20000000.0, 'FIXED_ALW': 2000000.0, 'BPJS_JKK': 52800.0, 'BPJS_JKM': 66000.0, 'BPJS_Kesehatan': 480000.0, 'JHT_COMP': 814000.0, 'JP_COMP': 210948.0, 'BASE_GROSS_UP': 22598800.0, 'TAXALW': 2510977.0, 'GROSS_TOTAL': 26134725.0, 'GROSS': 25109777.0, 'JHT': -440000.0, 'BPJS_KESEHATAN_DED': -120000.0, 'JP': -105474.0, 'PPH21': -2510977.0, 'NET': 21334526.0}
        self._validate_payslip(payslip, payslip_results)

    def test_with_reimbursement_gross_up(self):
        """ 5m wage with 500k reimbursement """
        self.version.l10n_id_payroll_type = 'gross_up'
        self.version.wage = 5e6

        payslip = self._generate_payslip(
            date(2025, 6, 1),
            date(2025, 6, 30)
        )
        for code, value in {
            self.env.ref('l10n_id_hr_payroll.l10n_id_include_jkk_jkm_salary_rule').code: True,
            self.env.ref('l10n_id_hr_payroll.l10n_id_include_bpjs_kesehatan_salary_rule').code: True,
            self.env.ref('l10n_id_hr_payroll.l10n_id_hr_payroll_structure_id_employee_salary_reimbursement_salary_rule').code: 5e5,
        }.items():
            payslip._set_input_value(code, value)
        payslip.compute_sheet()

        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_BPJS_KES': 1.0, 'IN_JKK_JKM': 1.0, 'BASIC': 5000000.0, 'BPJS_JKK': 12000.0, 'BPJS_JKM': 15000.0, 'BPJS_Kesehatan': 200000.0, 'JHT_COMP': 185000.0, 'JP_COMP': 100000.0, 'BASE_GROSS_UP': 5227000.0, 'TAXALW': 0.0, 'GROSS_TOTAL': 6012000.0, 'GROSS': 5227000.0, 'JHT': -100000.0, 'BPJS_KESEHATAN_DED': -50000.0, 'JP': -50000.0, 'PPH21': 0.0, 'REIMBURSEMENT': 500000.0, 'NET': 5300000.0}
        self._validate_payslip(payslip, payslip_results)

    def test_low_income_with_meal_alw_gross_up(self):
        """ Wage of 2m with 50k/day meal allowance """
        self.version.l10n_id_payroll_type = 'gross_up'
        self.version.wage = 2e6

        payslip = self._generate_payslip(
            date(2025, 6, 1),
            date(2025, 6, 30)
        )
        for code, value in {
            self.env.ref('l10n_id_hr_payroll.l10n_id_include_jkk_jkm_salary_rule').code: True,
            self.env.ref('l10n_id_hr_payroll.l10n_id_include_bpjs_kesehatan_salary_rule').code: True,
            self.env.ref('l10n_id_hr_payroll.salary_rule_id_meal_allowance').code: 1000000,
        }.items():
            payslip._set_input_value(code, value)
        payslip.compute_sheet()

        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_BPJS_KES': 1.0, 'IN_JKK_JKM': 1.0, 'BASIC': 2000000.0, 'MEAL': 1000000.0, 'BPJS_JKK': 4800.0, 'BPJS_JKM': 6000.0, 'BPJS_Kesehatan': 80000.0, 'JHT_COMP': 74000.0, 'JP_COMP': 40000.0, 'BASE_GROSS_UP': 3090800.0, 'TAXALW': 0.0, 'GROSS_TOTAL': 3204800.0, 'GROSS': 3090800.0, 'JHT': -40000.0, 'BPJS_KESEHATAN_DED': -20000.0, 'JP': -20000.0, 'PPH21': 0.0, 'NET': 2920000.0}
        self._validate_payslip(payslip, payslip_results)

    def test_with_insurance_and_meal_alw_gross_up(self):
        """ 1m wage with 300k/day meal allowance and 500k/month insurance allowance (8)"""
        self.version.l10n_id_payroll_type = 'gross_up'
        self.version.wage = 1e6

        payslip = self._generate_payslip(
            date(2025, 6, 1),
            date(2025, 6, 30)
        )
        for code, value in {
            self.env.ref('l10n_id_hr_payroll.l10n_id_include_jkk_jkm_salary_rule').code: True,
            self.env.ref('l10n_id_hr_payroll.l10n_id_include_bpjs_kesehatan_salary_rule').code: True,
            self.env.ref('l10n_id_hr_payroll.salary_rule_id_meal_allowance').code: 6e6,
            self.env.ref('l10n_id_hr_payroll.salary_rule_id_insurance').code: 5e5,
        }.items():
            payslip._set_input_value(code, value)
        payslip.compute_sheet()

        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_BPJS_KES': 1.0, 'IN_JKK_JKM': 1.0, 'BASIC': 1000000.0, 'INSURANCE': 500000.0, 'MEAL': 6000000.0, 'BPJS_JKK': 2400.0, 'BPJS_JKM': 3000.0, 'BPJS_Kesehatan': 40000.0, 'JHT_COMP': 37000.0, 'JP_COMP': 20000.0, 'BASE_GROSS_UP': 7545400.0, 'TAXALW': 114904.0, 'GROSS_TOTAL': 7717304.0, 'GROSS': 7660304.0, 'JHT': -20000.0, 'BPJS_KESEHATAN_DED': -10000.0, 'JP': -10000.0, 'PPH21': -114904.0, 'NET': 6960000.0}
        self._validate_payslip(payslip, payslip_results)

    def test_no_jkk_jkm_gross_up(self):
        """ Exclude JKK, JKM (9) """
        self.version.l10n_id_payroll_type = 'gross_up'
        self.version.wage = 5e6

        payslip = self._generate_payslip(
            date(2025, 6, 1),
            date(2025, 6, 30)
        )
        for code, value in {
            self.env.ref('l10n_id_hr_payroll.l10n_id_include_jkk_jkm_salary_rule').code: False,
            self.env.ref('l10n_id_hr_payroll.l10n_id_include_bpjs_kesehatan_salary_rule').code: True,
            self.env.ref('l10n_id_hr_payroll.salary_rule_id_laptop').code: 3e5,
        }.items():
            payslip._set_input_value(code, value)
        payslip.compute_sheet()

        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_BPJS_KES': 1.0, 'BASIC': 5000000.0, 'LAPTOP': 300000.0, 'BPJS_Kesehatan': 200000.0, 'BASE_GROSS_UP': 5500000.0, 'TAXALW': 13784.0, 'GROSS_TOTAL': 5513784.0, 'GROSS': 5513784.0, 'BPJS_KESEHATAN_DED': -50000.0, 'PPH21': -13784.0, 'NET': 5250000.0}
        self._validate_payslip(payslip, payslip_results)

    def test_no_bpjs_kesehatan_gross_up(self):
        """ Test payslip without BPJS kesehatan (10) """
        self.version.l10n_id_payroll_type = 'gross_up'
        self.version.wage = 5e6

        payslip = self._generate_payslip(
            date(2025, 6, 1),
            date(2025, 6, 30)
        )

        for code, value in {
            self.env.ref('l10n_id_hr_payroll.l10n_id_include_jkk_jkm_salary_rule').code: True,
            self.env.ref('l10n_id_hr_payroll.l10n_id_include_bpjs_kesehatan_salary_rule').code: False,
            self.env.ref('l10n_id_hr_payroll.salary_rule_id_laptop').code: 3e5,
        }.items():
            payslip._set_input_value(code, value)
        payslip.compute_sheet()

        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_JKK_JKM': 1.0, 'BASIC': 5000000.0, 'LAPTOP': 300000.0, 'BPJS_JKK': 12000.0, 'BPJS_JKM': 15000.0, 'JHT_COMP': 185000.0, 'JP_COMP': 100000.0, 'BASE_GROSS_UP': 5327000.0, 'TAXALW': 0.0, 'GROSS_TOTAL': 5612000.0, 'GROSS': 5327000.0, 'JHT': -100000.0, 'JP': -50000.0, 'PPH21': 0.0, 'NET': 5150000.0}
        self._validate_payslip(payslip, payslip_results)

    def test_no_allowance_ded_gross_up(self):
        """ Test allowance and deduction being removed from payslip (12)"""
        self.version.l10n_id_payroll_type = 'gross_up'
        payslip = self._generate_payslip(
            date(2025, 6, 1),
            date(2025, 6, 30)
        )

        for code, value in {
            self.env.ref('l10n_id_hr_payroll.l10n_id_include_jkk_jkm_salary_rule').code: False,
            self.env.ref('l10n_id_hr_payroll.l10n_id_include_bpjs_kesehatan_salary_rule').code: False,
            self.env.ref('l10n_id_hr_payroll.salary_rule_id_laptop').code: 3e5,
        }.items():
            payslip._set_input_value(code, value)
        payslip.compute_sheet()

        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'BASIC': 10000000.0, 'LAPTOP': 300000.0, 'BASE_GROSS_UP': 10300000.0, 'TAXALW': 264102.0, 'GROSS_TOTAL': 10564102.0, 'GROSS': 10564102.0, 'PPH21': -264102.0, 'NET': 10300000.0}
        self._validate_payslip(payslip, payslip_results)

    def test_allowance_thr_gross_up(self):
        """ Test 20m salary with THR on April """
        self.version.l10n_id_payroll_type = 'gross_up'
        self.version.wage = 2e7

        payslip = self._generate_payslip(
            date(2025, 4, 1),
            date(2025, 4, 30)
        )
        for code, value in {
            self.env.ref('l10n_id_hr_payroll.l10n_id_include_jkk_jkm_salary_rule').code: True,
            self.env.ref('l10n_id_hr_payroll.l10n_id_include_bpjs_kesehatan_salary_rule').code: True,
            self.env.ref('l10n_id_hr_payroll.salary_rule_id_thr').code: 1e7,
        }.items():
            payslip._set_input_value(code, value)
        payslip.compute_sheet()

        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_BPJS_KES': 1.0, 'IN_JKK_JKM': 1.0, 'BASIC': 20000000.0, 'THR': 10000000.0, 'BPJS_JKK': 48000.0, 'BPJS_JKM': 60000.0, 'BPJS_Kesehatan': 480000.0, 'JHT_COMP': 740000.0, 'JP_COMP': 210948.0, 'BASE_GROSS_UP': 30588000.0, 'TAXALW': 5397882.0, 'GROSS_TOTAL': 36936830.0, 'GROSS': 35985882.0, 'JHT': -400000.0, 'BPJS_KESEHATAN_DED': -120000.0, 'JP': -105474.0, 'PPH21': -5397882.0, 'NET': 29374526.0}
        self._validate_payslip(payslip, payslip_results)

    def test_end_of_year_payment_not_validated_gross_up(self):
        """ Test if slip is not validated yet, then yearly gross=gross of that year only with no accumulation """
        self.version.l10n_id_payroll_type = 'gross_up'
        self.version.wage = 1e7

        for i in range(1, 13):
            drange = PERIOD[i]
            slip = self._generate_payslip(
                date(2025, i, drange[0]),
                date(2025, i, drange[1])
            )

            if i == 12:
                payslip = slip

        lines_to_compare = payslip._get_line_values(['GROSS'])
        self.assertAlmostEqual(lines_to_compare['GROSS'][payslip.id]['total'], 10454e3)

    def test_end_of_year_payment_gross_up(self):
        """ Generate payslip from january to dec then focus on the end of year (15) """
        self.version.l10n_id_payroll_type = 'gross_up'
        self.version.wage = 2e7

        for i in range(1, 13):
            drange = PERIOD[i]
            slip = self._generate_payslip(
                date(2025, i, drange[0]),
                date(2025, i, drange[1])
            )
            slip.action_payslip_done()

            if i == 12:
                payslip = slip

        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_JKK_JKM': 1.0, 'IN_BPJS_KES': 1.0, 'BASIC': 20000000.0, 'BPJS_JKK': 48000.0, 'BPJS_JKM': 60000.0, 'BPJS_Kesehatan': 480000.0, 'JHT_COMP': 740000.0, 'JP_COMP': 210948.0, 'BASE_GROSS_UP': 20588000.0, 'TAXALW': 2484375.0, 'GROSS_TOTAL': 24023323.0, 'GROSS': 23072375.0, 'JHT': -400000.0, 'BPJS_KESEHATAN_DED': -120000.0, 'JP': -105474.0, 'JABATAN': 6000000.0, 'JHT_JP': -6055586.0, 'PTKP': 54000000.0, 'PKP': 205882000.0, 'PPH21': -2484375.0, 'NET': 19374526.0}
        self._validate_payslip(payslip, payslip_results)

    def test_end_of_year_payment_2_gross_up(self):
        """ use 10m wage check only end of year (16)"""
        self.version.l10n_id_payroll_type = 'gross_up'
        for i in range(1, 13):
            drange = PERIOD[i]
            slip = self._generate_payslip(
                date(2025, i, drange[0]),
                date(2025, i, drange[1])
            )
            slip.action_payslip_done()

            if i == 12:
                payslip = slip

        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_JKK_JKM': 1.0, 'IN_BPJS_KES': 1.0, 'BASIC': 10000000.0, 'BPJS_JKK': 24000.0, 'BPJS_JKM': 30000.0, 'BPJS_Kesehatan': 400000.0, 'JHT_COMP': 370000.0, 'JP_COMP': 200000.0, 'BASE_GROSS_UP': 10454000.0, 'TAXALW': 298941.0, 'GROSS_TOTAL': 11322941.0, 'GROSS': 10752941.0, 'JHT': -200000.0, 'BPJS_KESEHATAN_DED': -100000.0, 'JP': -100000.0, 'JABATAN': 6000000.0, 'JHT_JP': -3600000.0, 'PTKP': 54000000.0, 'PKP': 65703000.0, 'PPH21': -298941.0, 'NET': 9600000.0}
        self._validate_payslip(payslip, payslip_results)

    def test_end_of_contract_gross_up(self):
        """ Contract lasts until end of August (17) """
        self.version.l10n_id_payroll_type = 'gross_up'
        self.version.contract_date_end = date(2025, 8, 31)

        for i in range(1, 9):
            drange = PERIOD[i]
            slip = self._generate_payslip(
                date(2025, i, drange[0]),
                date(2025, i, drange[1])
            )
            slip.action_payslip_done()

            if i == 8:
                payslip = slip

        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_JKK_JKM': 1.0, 'IN_BPJS_KES': 1.0, 'BASIC': 10000000.0, 'BPJS_JKK': 24000.0, 'BPJS_JKM': 30000.0, 'BPJS_Kesehatan': 400000.0, 'JHT_COMP': 370000.0, 'JP_COMP': 200000.0, 'BASE_GROSS_UP': 10454000.0, 'TAXALW': -1038983.0, 'GROSS_TOTAL': 9985017.0, 'GROSS': 9415017.0, 'JHT': -200000.0, 'BPJS_KESEHATAN_DED': -100000.0, 'JP': -100000.0, 'JABATAN': 3970750.85, 'JHT_JP': -2400000.0, 'PTKP': 54000000.0, 'PKP': 24485000.0, 'PPH21': 1038983.0, 'NET': 9600000.0}
        self._validate_payslip(payslip, payslip_results)

    def test_end_of_contract_2_gross_up(self):
        """ 15 Jan - 31 Dec + get the December's payslip (19) """
        self.version.l10n_id_payroll_type = 'gross_up'
        self.version.contract_date_start = date(2025, 1, 15)

        for i in range(1, 13):
            drange = PERIOD[i]
            slip = self._generate_payslip(
                date(2025, i, drange[0]),
                date(2025, i, drange[1])
            )
            slip.action_payslip_done()

            if i == 12:
                payslip = slip

        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_JKK_JKM': 1.0, 'IN_BPJS_KES': 1.0, 'BASIC': 10000000.0, 'BPJS_JKK': 24000.0, 'BPJS_JKM': 30000.0, 'BPJS_Kesehatan': 400000.0, 'JHT_COMP': 370000.0, 'JP_COMP': 200000.0, 'BASE_GROSS_UP': 10454000.0, 'TAXALW': -154588.0, 'GROSS_TOTAL': 10869412.0, 'GROSS': 10299412.0, 'JHT': -200000.0, 'BPJS_KESEHATAN_DED': -100000.0, 'JP': -100000.0, 'JABATAN': 5785562.58, 'JHT_JP': -3469565.22, 'PTKP': 54000000.0, 'PKP': 60761000.0, 'PPH21': 154588.0, 'NET': 9600000.0}
        self._validate_payslip(payslip, payslip_results)

    def test_end_of_contract_3_gross_up(self):
        """15 Jan - end of year, payroll cycle at 15th"""
        self.version.l10n_id_payroll_type = 'gross_up'
        self.version.contract_date_start = date(2025, 1, 15)

        for i in range(1, 12):
            slip = self._generate_payslip(
                date(2025, i, 15),
                date(2025, i + 1, 14)
            )
            slip.action_payslip_done()

            if i == 11:
                payslip = slip

        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_JKK_JKM': 1.0, 'IN_BPJS_KES': 1.0, 'BASIC': 10000000.0, 'BPJS_JKK': 24000.0, 'BPJS_JKM': 30000.0, 'BPJS_Kesehatan': 400000.0, 'JHT_COMP': 370000.0, 'JP_COMP': 200000.0, 'BASE_GROSS_UP': 10454000.0, 'TAXALW': -464591.0, 'GROSS_TOTAL': 10559409.0, 'GROSS': 9989409.0, 'JHT': -200000.0, 'BPJS_KESEHATAN_DED': -100000.0, 'JP': -100000.0, 'JABATAN': 5499470.45, 'JHT_JP': -3300000.0, 'PTKP': 54000000.0, 'PKP': 54941000.0, 'PPH21': 464591.0, 'NET': 9600000.0}
        self._validate_payslip(payslip, payslip_results)

    def test_end_of_year_with_allowance_gross_up(self):
        """ End of year testing with transport allowance (21) """
        self.version.l10n_id_payroll_type = 'gross_up'
        self.version.contract_date_start = date(2025, 10, 1)
        self.version.wage = 2e7
        for i in range(10, 12):
            drange = PERIOD[i]
            slip = self._generate_payslip(
                date(2025, i, drange[0]),
                date(2025, i, drange[1])
            )
            for code, value in {
                self.env.ref('l10n_id_hr_payroll.l10n_id_include_jkk_jkm_salary_rule').code: True,
                self.env.ref('l10n_id_hr_payroll.l10n_id_include_bpjs_kesehatan_salary_rule').code: True,
                self.env.ref('l10n_id_hr_payroll.salary_rule_id_transport_allowance').code: 2e6,
            }.items():
                slip._set_input_value(code, value)
            slip.compute_sheet()
            slip.action_payslip_done()

        payslip = self._generate_payslip(
            date(2025, 12, 1),
            date(2025, 12, 31)
        )
        for code, value in {
            self.env.ref('l10n_id_hr_payroll.l10n_id_include_jkk_jkm_salary_rule').code: True,
            self.env.ref('l10n_id_hr_payroll.l10n_id_include_bpjs_kesehatan_salary_rule').code: True,
            self.env.ref('l10n_id_hr_payroll.salary_rule_id_transport_allowance').code: 2e6,
        }.items():
            payslip._set_input_value(code, value)
        payslip.compute_sheet()
        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_BPJS_KES': 1.0, 'IN_JKK_JKM': 1.0, 'BASIC': 20000000.0, 'TRANSPORT_ALW': 2000000.0, 'BPJS_JKK': 48000.0, 'BPJS_JKM': 60000.0, 'BPJS_Kesehatan': 480000.0, 'JHT_COMP': 740000.0, 'JP_COMP': 210948.0, 'BASE_GROSS_UP': 22588000.0, 'TAXALW': -4453904.0, 'GROSS_TOTAL': 19085044.0, 'GROSS': 18134096.0, 'JHT': -400000.0, 'BPJS_KESEHATAN_DED': -120000.0, 'JP': -105474.0, 'JABATAN': 1500000.0, 'JHT_JP': -1516422.0, 'PTKP': 54000000.0, 'PKP': 11313000.0, 'PPH21': 4453904.0, 'NET': 21374526.0}
        self._validate_payslip(payslip, payslip_results)

    def test_new_joiner_gross_up(self):
        """ New joiner starting in 15 January, payslip for January (22)"""
        self.version.l10n_id_payroll_type = 'gross_up'
        self.version.wage = 2e7
        self.version.contract_date_start = date(2025, 1, 15)

        payslip = self._generate_payslip(
            date(2025, 1, 1),
            date(2025, 1, 31)
        )
        for code, value in {
            self.env.ref('l10n_id_hr_payroll.l10n_id_include_jkk_jkm_salary_rule').code: True,
            self.env.ref('l10n_id_hr_payroll.l10n_id_include_bpjs_kesehatan_salary_rule').code: False,
        }.items():
            payslip._set_input_value(code, value)
        payslip.compute_sheet()

        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_JKK_JKM': 1.0, 'BASIC': 11304347.83, 'BPJS_JKK': 27130.43, 'BPJS_JKM': 33913.04, 'JHT_COMP': 418260.87, 'JP_COMP': 200846.0, 'BASE_GROSS_UP': 11365391.31, 'TAXALW': 473557.0, 'GROSS_TOTAL': 12458055.18, 'GROSS': 11838948.31, 'JHT': -226086.96, 'JP': -100423.0, 'PPH21': -473557.0, 'NET': 10977837.87}
        self._validate_payslip(payslip, payslip_results)

    def test_pkp_ptkp_show_up_gross_up(self):
        """ Only appear when end of contract and end of year. Also consider only the `date_to` field
        of the payslip"""
        self.version.l10n_id_payroll_type = 'gross_up'
        nov_payslip = self._generate_payslip(
            date(2025, 11, 1),
            date(2025, 11, 30)
        )
        dec_payslip = self._generate_payslip(
            date(2025, 12, 1),
            date(2025, 12, 31)
        )

        self.assertEqual(nov_payslip.l10n_id_include_pkp_ptkp, False)
        self.assertEqual(dec_payslip.l10n_id_include_pkp_ptkp, True)

        # November 15-Dec 14 should be True while December 15-Jan 14 should be False
        nov_payslip_2 = self._generate_payslip(
            date(2025, 11, 15),
            date(2025, 12, 14)
        )
        dec_payslip_2 = self._generate_payslip(
            date(2025, 12, 15),
            date(2026, 1, 14)
        )
        self.assertEqual(nov_payslip_2.l10n_id_include_pkp_ptkp, True)
        self.assertEqual(dec_payslip_2.l10n_id_include_pkp_ptkp, False)

    def test_end_of_year_jabatan_gross_up(self):
        """" Test to make sure biaya jabatan at the end of year is correct"""
        self.version.l10n_id_payroll_type = 'gross_up'
        # payroll cycle every 14th, employee starts from october
        payslip1 = self._generate_payslip(date(2025, 10, 15), date(2025, 11, 14))
        payslip1.action_payslip_done()
        payslip2 = self._generate_payslip(date(2025, 11, 15), date(2025, 12, 14))

        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_JKK_JKM': 1.0, 'IN_BPJS_KES': 1.0, 'BASIC': 10000000.0, 'BPJS_JKK': 24000.0, 'BPJS_JKM': 30000.0, 'BPJS_Kesehatan': 400000.0, 'JHT_COMP': 370000.0, 'JP_COMP': 200000.0, 'BASE_GROSS_UP': 10454000.0, 'TAXALW': -323319.0, 'GROSS_TOTAL': 10700681.0, 'GROSS': 10130681.0, 'JHT': -200000.0, 'BPJS_KESEHATAN_DED': -100000.0, 'JP': -100000.0, 'JABATAN': 1000000.0, 'JHT_JP': -600000.0, 'PTKP': 54000000.0, 'PKP': 0.0, 'PPH21': 323319.0, 'NET': 9600000.0}
        self._validate_payslip(payslip2, payslip_results)

    def test_jabatan_permanent_employee_gross_up(self):
        """ Biaya jabatan (JABATAN) is only granted to permanent employees. Explicitly assign
        the permanent employee type and assert JABATAN is computed at the end of year. """
        self.version.l10n_id_payroll_type = 'gross_up'
        permanent_type = self.env.ref('l10n_id_hr_payroll.l10n_id_employee_type_permanent')
        self.version.employee_type_id = permanent_type

        # payroll cycle every 14th, employee starts from october
        payslip1 = self._generate_payslip(date(2025, 10, 15), date(2025, 11, 14))
        payslip1.action_payslip_done()
        payslip2 = self._generate_payslip(date(2025, 11, 15), date(2025, 12, 14))

        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_JKK_JKM': 1.0, 'IN_BPJS_KES': 1.0, 'BASIC': 10000000.0, 'BPJS_JKK': 24000.0, 'BPJS_JKM': 30000.0, 'BPJS_Kesehatan': 400000.0, 'JHT_COMP': 370000.0, 'JP_COMP': 200000.0, 'BASE_GROSS_UP': 10454000.0, 'TAXALW': -323319.0, 'GROSS_TOTAL': 10700681.0, 'GROSS': 10130681.0, 'JHT': -200000.0, 'BPJS_KESEHATAN_DED': -100000.0, 'JP': -100000.0, 'JABATAN': 1000000.0, 'JHT_JP': -600000.0, 'PTKP': 54000000.0, 'PKP': 0.0, 'PPH21': 323319.0, 'NET': 9600000.0}
        self._validate_payslip(payslip2, payslip_results)

    def test_pkp_above_zero_gross_up(self):
        """ Test that PKP is non-negative and when PKP is 0, then return all paid PPH21 amount """
        self.version.l10n_id_payroll_type = 'gross_up'
        # joins november, pph21 of december is supposed to be -(pph21 of nov)
        self.version.contract_date_start = date(2025, 11, 1)

        nov_pslip = self._generate_payslip(
            date(2025, 11, 1),
            date(2025, 11, 3)
        )
        nov_pslip.action_payslip_done()

        dec_pslip = self._generate_payslip(
            date(2025, 12, 1),
            date(2025, 12, 31)
        )

        nov_payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_JKK_JKM': 1.0, 'IN_BPJS_KES': 1.0, 'BASIC': 10000000.0, 'BPJS_JKK': 24000.0, 'BPJS_JKM': 30000.0, 'BPJS_Kesehatan': 400000.0, 'JHT_COMP': 370000.0, 'JP_COMP': 200000.0, 'BASE_GROSS_UP': 10454000.0, 'TAXALW': 323319.0, 'GROSS_TOTAL': 11347319.0, 'GROSS': 10777319.0, 'JHT': -200000.0, 'BPJS_KESEHATAN_DED': -100000.0, 'JP': -100000.0, 'PPH21': -323319.0, 'NET': 9600000.0}
        self._validate_payslip(nov_pslip, nov_payslip_results)

        dec_payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_JKK_JKM': 1.0, 'IN_BPJS_KES': 1.0, 'BASIC': 10000000.0, 'BPJS_JKK': 24000.0, 'BPJS_JKM': 30000.0, 'BPJS_Kesehatan': 400000.0, 'JHT_COMP': 370000.0, 'JP_COMP': 200000.0, 'BASE_GROSS_UP': 10454000.0, 'TAXALW': -323319.0, 'GROSS_TOTAL': 10700681.0, 'GROSS': 10130681.0, 'JHT': -200000.0, 'BPJS_KESEHATAN_DED': -100000.0, 'JP': -100000.0, 'JABATAN': 1000000.0, 'PTKP': 54000000.0, 'JHT_JP': -600000.0, 'PKP': 0.0, 'PPH21': 323319.0, 'NET': 9600000.0}
        self._validate_payslip(dec_pslip, dec_payslip_results)

        self.assertEqual(dec_payslip_results['PKP'], 0)
        self.assertEqual(dec_payslip_results['PPH21'], -nov_payslip_results['PPH21'])

    def test_with_overtime(self):
        """Test overtime calculation"""
        self.version.wage = 17_300_000

        ot1 = self.env.ref('hr_work_entry.l10n_id_work_entry_type_overtime_1')
        ot2 = self.env.ref('hr_work_entry.l10n_id_work_entry_type_overtime_2')

        # Wednesday 2026-06-03: 1h at 1.5x (hours 17->18) + 4h at 2.0x (hours 18->22)
        self.env['hr.leave'].create([{
            'name': 'OT 1.5x',
            'employee_id': self.employee.id,
            'request_date_from': date(2026, 6, 3),
            'request_date_to': date(2026, 6, 3),
            'request_hour_from': 17,
            'request_hour_to': 18,
            'number_of_hours': 1,
            'work_entry_type_id': ot1.id,
        }, {
            'name': 'OT 2.0x',
            'employee_id': self.employee.id,
            'request_date_from': date(2026, 6, 3),
            'request_date_to': date(2026, 6, 3),
            'request_hour_from': 18,
            'request_hour_to': 22,
            'number_of_hours': 4,
            'work_entry_type_id': ot2.id,
        }])

        payslip = self._generate_payslip(date(2026, 6, 1), date(2026, 6, 30))

        self._validate_worked_days(payslip, {
            'OVERTIMEID1': (0.125, 1.0, 150_000.0),
            'OVERTIMEID2': (0.5, 4.0, 800_000.0),
        }, skip_lines=True)

        payslip_results = {'IN_BPJS_ARREARS': 1.0, 'IN_JKK_JKM': 1.0, 'IN_BPJS_KES': 1.0, 'BASIC': 17300000.0, 'OT': 950000.0, 'BASE': 18250000.0, 'BPJS_JKK': 41520.0, 'BPJS_JKM': 51900.0, 'BPJS_Kesehatan': 480000.0, 'GROSS_TOTAL': 18823420.0, 'GROSS': 18823420.0, 'JHT': -346000.0, 'BPJS_KESEHATAN_DED': -120000.0, 'JP': -105474.0, 'PPH21': -1505873.0, 'NET': 16172653.0}
        self._validate_payslip(payslip, payslip_results)

    def test_overtime_from_time_rules(self):
        self.ensure_installed('hr_attendance')
        self.env.user.group_ids += self.env.ref('hr_attendance.group_hr_attendance_manager')

        self.version.wage = 17_300_000

        # Wednesday 2026-06-03: check-in 08:00, check-out 18:00 -> 10h
        # creating the attendance fires the time rule pipeline synchronously:
        # hours 8-9 -> OVERTIMEID1 (1.5x), hours 9-10 -> OVERTIMEID2 (2.0x)
        self.env['hr.attendance'].create({  # noqa: OLS03001
            'employee_id': self.employee.id,
            'check_in': datetime(2026, 6, 3, 8, 0),
            'check_out': datetime(2026, 6, 3, 18, 0),
        })

        payslip = self._generate_payslip(date(2026, 6, 1), date(2026, 6, 30))
        # 100,000/h x 1h x 1.5 = 150,000 ; 100,000/h x 1h x 2.0 = 200,000
        self._validate_worked_days(payslip, {
            'OVERTIMEID1': (0.125, 1.0, 150_000.0),
            'OVERTIMEID2': (0.125, 1.0, 200_000.0),
        }, skip_lines=True)
        self._validate_payslip(payslip, {'OT': 350_000.0}, skip_lines=True)

    # =============================
    # BPJS KESEHATAN BILLING CUT-OFF
    # =============================
    def test_bpjs_joined_before_cutoff(self):
        """BPJS Kesehatan is charged in the joining month when the employee joins before the cut-off date."""
        self.version.contract_date_start = date(2024, 6, 6)

        # June is prorated to 17 of 20 working days, so BASIC is 8,500,000.
        june = self._generate_payslip(date(2024, 6, 1), date(2024, 6, 30))
        self.assertFalse(june._l10n_id_is_bpjs_kesehatan_deferred())
        self._validate_payslip(june, {
            'BASIC': 8500000.0,
            'BPJS_Kesehatan': 340000.0,
            'BPJS_KESEHATAN_DED': -85000.0,
        }, skip_lines=True)
        june.action_payslip_done()

        # Nothing was deferred, so July has no BPJS arrears lines.
        july = self._generate_payslip(date(2024, 7, 1), date(2024, 7, 31))
        july_codes = july.line_ids.mapped('code')
        self.assertNotIn('BPJS_KESEHATAN_PREV', july_codes)
        self.assertNotIn('BPJS_KESEHATAN_DED_PREV', july_codes)

    def test_bpjs_joined_after_cutoff(self):
        """BPJS Kesehatan is deferred for late joiners and charged as arrears the next month."""
        self.version.contract_date_start = date(2024, 6, 20)

        # The employee is only registered with BPJS in July, so June has no BPJS lines.
        june = self._generate_payslip(date(2024, 6, 1), date(2024, 6, 30))
        self.assertTrue(june._l10n_id_is_bpjs_kesehatan_deferred())
        self.assertNotIn('BPJS_Kesehatan', june.line_ids.mapped('code'))
        self.assertNotIn('BPJS_KESEHATAN_DED', june.line_ids.mapped('code'))
        june.action_payslip_done()

        # June is prorated to 7 of 20 working days, so July adds arrears on 3,500,000
        # on top of its regular BPJS contributions.
        july = self._generate_payslip(date(2024, 7, 1), date(2024, 7, 31))
        self._validate_payslip(july, {
            'BPJS_Kesehatan': 400000.0,
            'BPJS_KESEHATAN_PREV': 140000.0,
            'BPJS_KESEHATAN_DED': -100000.0,
            'BPJS_KESEHATAN_DED_PREV': -35000.0,
        }, skip_lines=True)

    def test_bpjs_joined_after_cutoff_without_arrears(self):
        """Late joiners do not get BPJS arrears when the input is disabled."""
        self.version.contract_date_start = date(2024, 6, 20)

        # The employee is only registered with BPJS in July, so June has no BPJS lines.
        june = self._generate_payslip(date(2024, 6, 1), date(2024, 6, 30))
        self.assertTrue(june._l10n_id_is_bpjs_kesehatan_deferred())
        self.assertNotIn('BPJS_Kesehatan', june.line_ids.mapped('code'))
        self.assertNotIn('BPJS_KESEHATAN_DED', june.line_ids.mapped('code'))
        june.action_payslip_done()

        # Clearing "Include BPJS Arrears" keeps July's regular BPJS lines but removes arrears.
        july = self._generate_payslip(date(2024, 7, 1), date(2024, 7, 31))
        july._set_input_value(self.env.ref('l10n_id_hr_payroll.l10n_id_include_bpjs_arrears_salary_rule').code, False)
        july.compute_sheet()
        self._validate_payslip(july, {
            'BPJS_Kesehatan': 400000.0,
            'BPJS_KESEHATAN_DED': -100000.0,
        }, skip_lines=True)
        july_codes = july.line_ids.mapped('code')
        self.assertNotIn('BPJS_KESEHATAN_PREV', july_codes)
        self.assertNotIn('BPJS_KESEHATAN_DED_PREV', july_codes)

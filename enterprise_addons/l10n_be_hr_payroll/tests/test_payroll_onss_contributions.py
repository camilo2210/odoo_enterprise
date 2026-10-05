# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from dateutil.relativedelta import relativedelta

from odoo.addons.hr_payroll.tests.common import TestPayrollBase
from odoo.addons.l10n_be_hr_payroll.tests.common import TestBelgiumCommon
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install', 'onss_contributions')
class TestPayrollOnssContributions(TestPayrollBase, TestBelgiumCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.be_employee = cls.env.ref('l10n_be_hr_payroll.l10n_be_worker_code_00495')
        cls.be_worker = cls.env.ref('l10n_be_hr_payroll.l10n_be_worker_code_00015')
        cls.be_acs = cls.env.ref('l10n_be_hr_payroll.l10n_be_worker_code_00484')
        cls.be_employee_no_salary_moderation = cls.env.ref('l10n_be_hr_payroll.l10n_be_worker_code_00439')
        cls.be_worker_no_salary_moderation = cls.env.ref('l10n_be_hr_payroll.l10n_be_worker_code_00027')

        cls.category_employee = cls.env.ref('l10n_be_hr_payroll.l10n_be_employer_category_00010')
        cls.category_horeca = cls.env.ref('l10n_be_hr_payroll.l10n_be_employer_category_00017')
        cls.category_food_industry = cls.env.ref('l10n_be_hr_payroll.l10n_be_employer_category_00048')

        cls.cp_200 = cls.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200')
        cls.cp_302 = cls.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_302')

        cls.struct = cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary')
        cls.salary_rule = cls.env.ref('l10n_be_hr_payroll.cp200_employees_salary_gross_salary')

        cls.economic_unemployment = cls.env.ref('hr_work_entry.l10n_be_work_entry_type_economic_unemployment')

        cls.construction_sector = cls.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_124')

        cls.company = cls.env['res.company'].create([{
            'name': 'BE Company',
            'country_id': cls.env.ref('base.be').id,
        }])
        cls.payroll_config = cls.company.current_payroll_config_id
        cls.payroll_config.write({
            'l10n_be_employer_category_id': cls.category_employee.id,
        })

        cls.env.user.company_id = cls.company
        cls._setup_common(
            country=cls.env.ref('base.be'),
            structure=cls.struct,
            structure_type=cls.env.ref('hr.structure_type_employee_cp200'),
            version_fields={
                'name': 'Employee',
                'date_version': date(2025, 1, 1),
                'contract_date_start': date(2025, 1, 1),
                'contract_date_end': False,
                'wage': 1000,
                'l10n_be_flexi_monthly_wage': 1000,
                'l10n_be_worker_code_id': cls.be_employee.id,
                'l10n_be_joint_committee_id': cls.cp_200.id,
                'resource_calendar_id': cls.env.ref('l10n_be_hr_payroll.resource_calendar_std_38h').id,
            }
        )

        cls.quarter_payslips = cls.env['hr.payslip'].create([
            {
                'name': 'Payslip January',
                'date_from': '2026-01-01',
                'employee_id': cls.employee.id,
                'company_id': cls.company.id,
                'struct_id': cls.struct.id,
            },
            {
                'name': 'Payslip February',
                'date_from': '2026-02-01',
                'employee_id': cls.employee.id,
                'company_id': cls.company.id,
                'struct_id': cls.struct.id,
            },
            {
                'name': 'Payslip March',
                'date_from': '2026-03-01',
                'employee_id': cls.employee.id,
                'company_id': cls.company.id,
                'struct_id': cls.struct.id,
            },
        ])
        cls.payslip = cls.quarter_payslips[0]
        cls.extra_payslip = cls.env['hr.payslip'].create({
            'name': '2nd Payslip March',
            'date_from': '2026-03-01',
            'employee_id': cls.employee.id,
            'company_id': cls.company.id,
            'struct_id': cls.struct.id,
        })

    def get_total(self, payslip, rule_code):
        payslip.compute_sheet()
        return payslip._get_line_values([rule_code], compute_sum=True)[rule_code]['sum']['total']

    def check_total(self, payslip, rule_code, total):
        payslip.compute_sheet()
        self._validate_payslip(payslip, {rule_code: total}, True)

    def check_quarter_total(self, rule_code, totals, quarter_total):
        self.quarter_payslips.action_payslip_draft()
        q_total = 0.0
        for i in range(len(self.quarter_payslips)):
            if totals[i] is None:
                continue
            self.check_total(self.quarter_payslips[i], rule_code, totals[i])
            self.quarter_payslips[i].action_payslip_done()
            q_total += self.get_total(self.quarter_payslips[i], rule_code)
        self.assertAlmostEqual(q_total, quarter_total, 2)

    def check_condition(self, rule_code, expected):
        self.payslip.compute_sheet()
        self._validate_rule_computed(self.payslip, rule_code, expected)

    def check_condition_dimona_categories(self, rule_code, categories, expected):
        original_category = self.version.l10n_be_dimona_category
        self.version.contract_date_start = date(2026, 1, 1)
        self.version.contract_date_end = date(2026, 3, 31)
        for category in categories:
            self.version.l10n_be_dimona_category = category
            self.payslip.compute_sheet()
            self._validate_rule_computed(self.payslip, rule_code, expected)
        self.version.l10n_be_dimona_category = original_category

    def test_onss_employee_condition(self):
        """
        ONSS
        Social contribution
        """
        self.check_condition('ONSS', True)
        self.check_condition_dimona_categories('ONSS', ['dwd', 'o17', 's17', 't17', 'stg', 'tri', 'ivt'], False)

    def test_onss_employee_computation(self):
        """
        ONSS
        Social contribution
        """
        # Employee
        self.check_quarter_total('ONSS', [-130.7] * 3, 3000 * -13.07 / 100)

        # Worker (-0.01 because regularization is on the onss employer basic)
        self.version.l10n_be_worker_code_id = self.be_worker
        self.check_quarter_total('ONSS', [-141.16] * 3, 3000 * 1.08 * -13.07 / 100 - 0.01)

        # Student Employee
        self.version.l10n_be_worker_code_id = self.be_employee
        self.version.l10n_be_dimona_category = 'stu'
        self.check_quarter_total('ONSS', [-27.1] * 3, 3000 * -2.71 / 100)

        # Student Worker (-0.01 because regularization is on the onss employer basic)
        self.version.l10n_be_worker_code_id = self.be_worker
        self.version.l10n_be_dimona_category = 'stu'
        self.check_quarter_total('ONSS', [-29.27] * 3, 3000 * 1.08 * -2.71 / 100 - 0.01)

    def test_onss_basic_condition(self):
        """
        ONSSEMPLOYERBASIC
        Accounting: ONSS Basic (Employer)
        """
        self.check_condition('ONSSEMPLOYERBASIC', True)
        self.check_condition_dimona_categories('ONSSEMPLOYERBASIC', ['ivt', 'flx'], False)

    def test_onss_basic_computation(self):
        """
        ONSSEMPLOYERBASIC
        Accounting: ONSS Basic (Employer)
        """
        # Employee
        self.check_quarter_total('ONSSEMPLOYERBASIC', [250] * 3, 3000 * 25 / 100)

        # Worker (-0.01 because regularization is not done on the employee onss)
        self.version.l10n_be_worker_code_id = self.be_worker
        self.check_quarter_total('ONSSEMPLOYERBASIC', [270, 269.99, 270], 3000 * 1.08 * 25 / 100 - 0.01)

        # Student Employee
        self.version.l10n_be_worker_code_id = self.be_employee
        self.version.l10n_be_dimona_category = 'stu'
        self.check_quarter_total('ONSSEMPLOYERBASIC', [54.3] * 3, 3000 * 5.43 / 100)

        # Student Worker
        self.version.l10n_be_worker_code_id = self.be_worker
        self.version.l10n_be_dimona_category = 'stu'
        self.check_quarter_total('ONSSEMPLOYERBASIC', [58.64, 58.64, 58.65], 3000 * 1.08 * 5.43 / 100)

    def _validate_onss_employer_basic_deductions(self, totals):
        self.quarter_payslips.action_payslip_draft()
        for i in range(len(self.quarter_payslips)):
            if totals[i] is None:
                self.quarter_payslips[i].compute_sheet()
                self.assertNotIn('ONSSEMPLOYERBASICDEDUC', self.quarter_payslips[i].line_ids.mapped('code'))
            else:
                self.check_total(self.quarter_payslips[i], 'ONSSEMPLOYERBASICDEDUC', totals[i])
            self.quarter_payslips[i].action_payslip_done()

    def _setup_onss_employer_basic_deduction(self):
        self.version.wage = 50000
        self.quarter_payslips |= self.extra_payslip

    def test_onss_employer_basic_deduction(self):
        self._setup_onss_employer_basic_deduction()
        # cap_amount: 86700 -> 86700/4 = 21675, wage=50000, ONSSBASICEMPLOYER=50000/4=12500 per month
        # 1st month, no deduction because 21675 > 12500
        # 2nd month, -3325 deduction because of 25000-21675
        # 3rd month, we already reached to cap amount, 12500 should be deducted directly, no more contribution should be paid
        # Same for 4th month.
        totals = [None, -3325, -12500, -12500]
        self._validate_onss_employer_basic_deductions(totals)

        self.version.wage = 30000
        totals = [None, None, -825, -7500]
        self._validate_onss_employer_basic_deductions(totals)

        self.version.wage = 50000
        # cap_amount: 85000 since 2025-07-01
        for slip in self.quarter_payslips:
            slip.date_from = '2025-07-01'
        totals = [None, -3750, -12500, -12500]
        self._validate_onss_employer_basic_deductions(totals)

        # cap_amount: 88434 since 2026-07-01
        for slip in self.quarter_payslips:
            slip.date_from = '2026-07-01'
        totals = [None, -2891.5, -12500, -12500]
        self._validate_onss_employer_basic_deductions(totals)

    def test_onss_employer_basic_deduction_before_capping(self):
        self._setup_onss_employer_basic_deduction()
        # First cap amount starts in 2025-07-01, before that there is no deduction for capping
        for i in range(len(self.quarter_payslips)):
            self.quarter_payslips[i].date_from = '2025-01-01'
        totals = [None, None, None, None]
        self._validate_onss_employer_basic_deductions(totals)

    def test_onss_employer_basic_deduction_category_exception(self):
        self._setup_onss_employer_basic_deduction()
        # No deduction for flx and stu categories
        self.version.contract_date_start = date(2026, 1, 1)
        self.version.contract_date_end = date(2026, 3, 31)
        self.version.l10n_be_dimona_category = 'flx'
        totals = [None, None, None, None]
        self._validate_onss_employer_basic_deductions(totals)

        self.version.l10n_be_dimona_category = 'stu'
        self.version.contract_date_end = False
        totals = [None, None, None, None]
        self._validate_onss_employer_basic_deductions(totals)

        self.version.l10n_be_dimona_category = 's17'
        totals = [None, -16395, -19035, -19035]
        self._validate_onss_employer_basic_deductions(totals)

        for slip in self.quarter_payslips:
            slip.date_from = '2026-07-01'
        totals = [None, None, None, None]
        # There will be no deduction for s17 (sports) dimona category since 2026-07-01
        self._validate_onss_employer_basic_deductions(totals)

    def test_onss_253_condition(self):
        """
        ONSSEMPLOYER_253
        Accounting: ONSS Annual Vacations Contribution (Employer)
        """
        # This rule doesn't apply for employer category 10 and worker code 495
        self.assertFalse(self.payslip._should_apply_onss_contribution('253'))
        self.check_condition('ONSSEMPLOYER_253', False)

        self.payroll_config.l10n_be_employer_category_id = self.category_horeca
        self.version.l10n_be_worker_code_id = self.be_worker
        self.assertTrue(self.payslip._should_apply_onss_contribution('253'))
        self.check_condition('ONSSEMPLOYER_253', True)
        self.check_condition_dimona_categories('ONSSEMPLOYER_253', ['stu', 'ivt', 'flx'], False)

    def test_onss_253_computation(self):
        """
        ONSSEMPLOYER_253
        Accounting: ONSS Annual Vacations Contribution (Employer)
        """
        # Worker
        self.payroll_config.l10n_be_employer_category_id = self.category_horeca
        self.version.l10n_be_worker_code_id = self.be_worker
        self.payslip.compute_sheet()
        self.check_quarter_total('ONSSEMPLOYER_253', [60.16, 60.15, 60.16], 3000 * 1.08 * 5.57 / 100)

    def test_onss_255_condition(self):
        """
        ONSSEMPLOYER_255
        Accounting: ONSS Work Accident Contribution (Employer)
        """
        self.assertTrue(self.payslip._should_apply_onss_contribution('255'))
        self.check_condition('ONSSEMPLOYER_255', True)
        self.check_condition_dimona_categories('ONSSEMPLOYER_255', ['stu', 'ivt', 'flx'], False)

    def test_onss_255_computation(self):
        """
        ONSSEMPLOYER_255
        Accounting: ONSS Work Accident Contribution (Employer)
        """
        # Employee
        self.check_quarter_total('ONSSEMPLOYER_255', [0.2] * 3, 3000 * 0.02 / 100)

        # Worker
        self.version.l10n_be_worker_code_id = self.be_worker
        self.check_quarter_total('ONSSEMPLOYER_255', [0.22, 0.21, 0.22], 3000 * 1.08 * 0.02 / 100)

    def test_onss_256_condition(self):
        """
        ONSSEMPLOYER_256
        Accounting: ONSS Asbestos Contribution (Employer)
        """
        self.assertTrue(self.payslip._should_apply_onss_contribution('256'))
        self.check_condition('ONSSEMPLOYER_256', True)
        self.check_condition_dimona_categories('ONSSEMPLOYER_256', ['stu', 'ivt', 'flx'], False)

        self.payslip.date_from = date(2026, 7, 1)
        self.check_condition('ONSSEMPLOYER_256', False)

    def test_onss_256_computation(self):
        """
        ONSSEMPLOYER_256
        Accounting: ONSS Asbestos Contribution (Employer)
        """
        # Employee
        self.check_quarter_total('ONSSEMPLOYER_256', [0.1] * 3, 3000 * 0.01 / 100)

        # Worker
        self.version.l10n_be_worker_code_id = self.be_worker
        self.check_quarter_total('ONSSEMPLOYER_256', [0.11, 0.11, 0.1], 3000 * 1.08 * 0.01 / 100)

    def test_onss_260_condition(self):
        """
        ONSSEMPLOYER_260
        Accounting: ONSS Activation Contribution (Employer)
        """
        self.assertTrue(self.payslip._should_apply_onss_contribution('260'))
        self.check_condition('ONSSEMPLOYER_260', False)

        self.version.l10n_be_work_exemption = '2'
        self.check_condition('ONSSEMPLOYER_260', True)
        self.check_condition_dimona_categories('ONSSEMPLOYER_260', ['stu', 'ivt', 'flx'], False)

    def test_onss_260_computation(self):
        """
        ONSSEMPLOYER_260
        Accounting: ONSS Activation Contribution (Employer)
        """
        # == Employees with Activation >= 10% ==
        # Age < 60 years
        # Employee
        self.employee.birthday = date(2025 - 59, 1, 1)
        self.version.l10n_be_work_exemption = '2'
        self.check_quarter_total('ONSSEMPLOYER_260', [625] * 3, 3000 * 62.5 / 100)

        # Worker
        self.version.l10n_be_worker_code_id = self.be_worker
        self.check_quarter_total('ONSSEMPLOYER_260', [675] * 3, 3000 * 1.08 * 62.5 / 100)

        # 60 years <= Age < 62 years
        # Employee
        self.employee.birthday = date(2025 - 61, 1, 1)
        self.version.l10n_be_worker_code_id = self.be_employee
        self.check_quarter_total('ONSSEMPLOYER_260', [562.5] * 3, 3000 * 56.25 / 100)

        # Worker
        self.version.l10n_be_worker_code_id = self.be_worker
        self.check_quarter_total('ONSSEMPLOYER_260', [607.5] * 3, 3000 * 1.08 * 56.25 / 100)

        # 62 years <= Age
        # Employee
        self.employee.birthday = date(2025 - 63, 1, 1)
        self.version.l10n_be_worker_code_id = self.be_employee
        self.check_quarter_total('ONSSEMPLOYER_260', [500] * 3, 3000 * 50 / 100)

        # Worker
        self.version.l10n_be_worker_code_id = self.be_worker
        self.check_quarter_total('ONSSEMPLOYER_260', [540] * 3, 3000 * 1.08 * 50 / 100)

        # == Employees with Activation < 10% ==
        # Age < 60 years
        # Employee
        for i in range(10):
            self.env['hr.employee'].create({
                'name': f'Employee {i}',
                'company_id': self.company.id,
                'date_version': '2025-01-01',
                'contract_date_start': '2025-01-01',
            })
        self.employee.birthday = date(2025 - 59, 1, 1)
        self.version.l10n_be_worker_code_id = self.be_employee
        self.check_quarter_total('ONSSEMPLOYER_260', [500] * 3, 3000 * 50 / 100)

        # Worker
        self.version.l10n_be_worker_code_id = self.be_worker
        self.check_quarter_total('ONSSEMPLOYER_260', [540] * 3, 3000 * 1.08 * 50 / 100)

        # 60 years <= Age < 62 years
        # Employee
        self.employee.birthday = date(2025 - 61, 1, 1)
        self.version.l10n_be_worker_code_id = self.be_employee
        self.check_quarter_total('ONSSEMPLOYER_260', [450] * 3, 3000 * 45 / 100)

        # Worker
        self.version.l10n_be_worker_code_id = self.be_worker
        self.check_quarter_total('ONSSEMPLOYER_260', [486] * 3, 3000 * 1.08 * 45 / 100)

        # 62 years <= Age
        # Employee
        self.employee.birthday = date(2025 - 63, 1, 1)
        self.version.l10n_be_worker_code_id = self.be_employee
        self.check_quarter_total('ONSSEMPLOYER_260', [400] * 3, 3000 * 40 / 100)

        # Worker
        self.version.l10n_be_worker_code_id = self.be_worker
        self.check_quarter_total('ONSSEMPLOYER_260', [432] * 3, 3000 * 1.08 * 40 / 100)

    def test_onss_450_condition(self):
        """
        ONSSEMPLOYER_450
        Accounting: ONSS Flexi-Job (Employer)
        """
        self.check_condition('ONSSEMPLOYER_450', False)
        self.check_condition_dimona_categories('ONSSEMPLOYER_450', ['flx'], True)

    def test_onss_450_computation(self):
        """
        ONSSEMPLOYER_450
        Accounting: ONSS Flexi-Job (Employer)
        """
        # Employee
        # SALARY = BASIC + FLEXI_PECULE = 3000€ + 3000€ * 7.67 / 100 = 3000€ + 230.1€ = 3230.1€
        self.version.contract_date_start = date(2026, 1, 1)
        self.version.contract_date_end = date(2026, 3, 31)
        self.version.l10n_be_dimona_category = 'flx'
        self.check_quarter_total('ONSSEMPLOYER_450', [301.48, 301.47, 301.48], 3230.1 * 28 / 100)

        # Worker
        self.version.l10n_be_worker_code_id = self.be_worker
        self.check_quarter_total('ONSSEMPLOYER_450', [325.59, 325.6, 325.59], 3230.1 * 1.08 * 28 / 100)

    def test_onss_800_condition(self):
        """
        ONSSEMPLOYER_800
        Accounting: ONSS Economic Unemployment Contribution (Employer)
        """
        # This rule doesn't apply for employer category 10 and worker code 495
        self.assertFalse(self.payslip._should_apply_onss_contribution('800'))
        self.check_condition('ONSSEMPLOYER_800', False)

        self.payroll_config.l10n_be_employer_category_id = self.category_horeca
        self.version.l10n_be_worker_code_id = self.be_worker
        self.assertTrue(self.payslip._should_apply_onss_contribution('800'))
        self.check_condition('ONSSEMPLOYER_800', False)

        self._generate_leave(self.employee, '2026-01-01', '2026-01-02', self.economic_unemployment)
        self.check_condition('ONSSEMPLOYER_800', True)
        self.check_condition_dimona_categories('ONSSEMPLOYER_800', ['stu', 'ivt', 'flx'], False)

    def test_onss_800_computation(self):
        """
        ONSSEMPLOYER_800
        Accounting: ONSS Economic Unemployment Contribution (Employer)
        """
        # Worker
        self.payroll_config.l10n_be_employer_category_id = self.category_horeca
        self.version.l10n_be_worker_code_id = self.be_worker

        # 10 days total
        self._generate_leave(self.employee, '2026-01-01', '2026-01-14', self.economic_unemployment)
        self.check_total(self.payslip, 'ONSSEMPLOYER_800', 0)

        # 120 days last 3 quarters (01/04/2025 -> 31/12/2025)
        self._generate_leave(self.employee, '2025-07-17', '2025-12-31', self.economic_unemployment)
        for month in range(4, 13):
            date_from = date(2025, month, 1)
            date_to = date_from + relativedelta(day=31)
            self._generate_payslip(date_from, date_to).action_payslip_done()

        self.check_total(self.payslip, 'ONSSEMPLOYER_800', 200)
        self.payroll_config.l10n_be_in_difficulty = True
        self.check_total(self.payslip, 'ONSSEMPLOYER_800', 100)
        self.payroll_config.l10n_be_in_difficulty = False

        # 120 + 10 = 130 days total
        # => 20€ per day
        # quarter total = economic unemployment days in quarter * flat-rate per day
        # total = quarter total - already paid this quarter
        # => 10 * 20€ - 0€ = 200€
        self.check_total(self.quarter_payslips[0], 'ONSSEMPLOYER_800', 200)
        self.quarter_payslips[0].action_payslip_done()

        # 120 + 10 + 10 = 140 days total
        # => 40€ per day
        # quarter total = economic unemployment days in quarter * flat-rate per day
        # total = quarter total - already paid this quarter
        # => 20 * 40€ - 200€ = 800€ - 200€ = 600€
        self._generate_leave(self.employee, '2026-02-01', '2026-02-13', self.economic_unemployment)
        self.check_total(self.quarter_payslips[1], 'ONSSEMPLOYER_800', 600)
        self.quarter_payslips[1].action_payslip_done()

        # 120 + 10 + 10 + 10 = 150 days total
        # => 40€ per day
        # quarter total = economic unemployment days in quarter * flat-rate per day
        # total = quarter total - already paid this quarter
        # => 30 * 40€ - 800€ = 1200€ - 800€ = 400€
        self._generate_leave(self.employee, '2026-03-01', '2026-03-13', self.economic_unemployment)
        self.check_total(self.quarter_payslips[2], 'ONSSEMPLOYER_800', 400)

        # 30 days economic unemployment in this quarter
        # 150 days in the reference period so 40€ per day
        # quarter total = economic unemployment days in quarter * flat-rate per day
        # quarter total = 30 * 40€ = 1200€ = 200€ + 600€ + 400€
        quarter_total = 0
        for payslip in self.quarter_payslips:
            quarter_total += self.get_total(payslip, 'ONSSEMPLOYER_800')
        self.assertEqual(quarter_total, 30 * 40)

    def test_onss_809_condition(self):
        """
        ONSSEMPLOYER_809
        Accounting: ONSS Commercial Sector FFE (Employer)
        """
        self.assertTrue(self.payslip._should_apply_onss_contribution('809'))
        self.check_condition('ONSSEMPLOYER_809', True)
        self.check_condition_dimona_categories('ONSSEMPLOYER_809', ['stu', 'ivt', 'flx'], False)

    def test_onss_809_computation(self):
        """
        ONSSEMPLOYER_809
        Accounting: ONSS Commercial Sector FFE (Employer)
        """
        # Employee - Small Commercial Company
        self.payroll_config.onss_importance_code = '3'
        self.check_quarter_total('ONSSEMPLOYER_809', [3.4] * 3, 3000 * 0.34 / 100)

        # ACS - Small Commercial Company
        self.version.l10n_be_worker_code_id = self.be_acs
        self.check_quarter_total('ONSSEMPLOYER_809', [3.2] * 3, 3000 * 0.32 / 100)

        # Worker - Small Commercial Company
        self.version.l10n_be_worker_code_id = self.be_worker
        self.check_quarter_total('ONSSEMPLOYER_809', [3.67, 3.67, 3.68], 3000 * 1.08 * 0.34 / 100)

        # Employee No Salary Moderation - Small Commercial Company
        self.version.l10n_be_worker_code_id = self.be_employee_no_salary_moderation
        self.check_quarter_total('ONSSEMPLOYER_809', [3.2] * 3, 3000 * 0.32 / 100)

        # Worker No Salary Moderation - Small Commercial Company
        self.version.l10n_be_worker_code_id = self.be_worker_no_salary_moderation
        self.check_quarter_total('ONSSEMPLOYER_809', [3.46, 3.45, 3.46], 3000 * 1.08 * 0.32 / 100)

        # Employee - Large Commercial Company
        self.payroll_config.onss_importance_code = '4'
        self.version.l10n_be_worker_code_id = self.be_employee
        self.check_quarter_total('ONSSEMPLOYER_809', [3.9] * 3, 3000 * 0.39 / 100)

        # ACS - Large Commercial Company
        self.version.l10n_be_worker_code_id = self.be_acs
        self.check_quarter_total('ONSSEMPLOYER_809', [3.7] * 3, 3000 * 0.37 / 100)

        # Worker - Large Commercial Company
        self.version.l10n_be_worker_code_id = self.be_worker
        self.check_quarter_total('ONSSEMPLOYER_809', [4.21, 4.21, 4.22], 3000 * 1.08 * 0.39 / 100)

        # Employee No Salary Moderation - Large Commercial Company
        self.version.l10n_be_worker_code_id = self.be_employee_no_salary_moderation
        self.check_quarter_total('ONSSEMPLOYER_809', [3.7] * 3, 3000 * 0.37 / 100)

        # Worker No Salary Moderation - Large Commercial Company
        self.version.l10n_be_worker_code_id = self.be_worker_no_salary_moderation
        self.check_quarter_total('ONSSEMPLOYER_809', [4, 3.99, 4], 3000 * 1.08 * 0.37 / 100)

    def test_onss_810_condition(self):
        """
        ONSSEMPLOYER_810
        Accounting: ONSS Special FFE (Employer)
        """
        self.assertTrue(self.payslip._should_apply_onss_contribution('810'))
        self.check_condition('ONSSEMPLOYER_810', True)
        self.check_condition_dimona_categories('ONSSEMPLOYER_810', ['stu', 'ivt', 'flx'], False)

    def test_onss_810_computation(self):
        """
        ONSSEMPLOYER_810
        Accounting: ONSS Special FFE (Employer)
        """
        # Employee
        self.check_quarter_total('ONSSEMPLOYER_810', [1.0] * 3, 3000 * 0.1 / 100)

        # Worker
        self.version.l10n_be_worker_code_id = self.be_worker
        self.check_quarter_total('ONSSEMPLOYER_810', [1.08] * 3, 3000 * 1.08 * 0.1 / 100)

    def test_onss_811_condition(self):
        """
        ONSSEMPLOYER_811
        Accounting: ONSS Non-Commercial Sector FFE (Employer)
        """
        # This rule doesn't apply for commercial sector employer
        self.assertFalse(self.payslip._should_apply_onss_contribution('811'))
        self.check_condition('ONSSEMPLOYER_811', False)

        self.payroll_config.l10n_be_ffe_employer_type = 'B'
        self.assertTrue(self.payslip._should_apply_onss_contribution('811'))
        self.check_condition('ONSSEMPLOYER_811', True)
        self.check_condition_dimona_categories('ONSSEMPLOYER_811', ['stu', 'ivt', 'flx'], False)

    def test_onss_811_computation(self):
        """
        ONSSEMPLOYER_811
        Accounting: ONSS Non-Commercial Sector FFE (Employer)
        """
        # Employee - Non-Commercial Sector
        self.payroll_config.l10n_be_ffe_employer_type = 'B'
        self.check_quarter_total('ONSSEMPLOYER_811', [0.1] * 3, 3000 * 0.01 / 100)

        # Worker - Non-Commercial Sector
        self.version.l10n_be_worker_code_id = self.be_worker
        self.check_quarter_total('ONSSEMPLOYER_811', [0.11, 0.11, 0.1], 3000 * 1.08 * 0.01 / 100)

        # Employee No Salary Moderation - Non-Commercial Sector
        self.version.l10n_be_worker_code_id = self.be_employee_no_salary_moderation
        self.check_quarter_total('ONSSEMPLOYER_811', [0.1] * 3, 3000 * 0.01 / 100)

        # Worker No Salary Moderation - Non-Commercial Sector
        self.version.l10n_be_worker_code_id = self.be_worker_no_salary_moderation
        self.check_quarter_total('ONSSEMPLOYER_811', [0.11, 0.11, 0.1], 3000 * 1.08 * 0.01 / 100)

    def test_onss_820_condition(self):
        """
        ONSSEMPLOYER_820
        Accounting: ONSS Workers Existence Security Funds (Employer)
        """
        self.assertFalse(self.payslip._should_apply_onss_contribution('820'))

        self.payroll_config.l10n_be_employer_category_id = self.category_horeca
        self.version.l10n_be_worker_code_id = self.be_worker
        self.assertTrue(self.payslip._should_apply_onss_contribution('820'))
        self.check_condition('ONSSEMPLOYER_820', True)
        self.check_condition_dimona_categories('ONSSEMPLOYER_820', ['stu', 'ivt', 'flx'], False)

    def test_onss_820_computation(self):
        """
        ONSSEMPLOYER_820
        Accounting: ONSS Workers Existence Security Funds (Employer)
        """
        # Worker - Small Company
        self.payroll_config.onss_importance_code = '4'
        self.payroll_config.l10n_be_employer_category_id = self.category_horeca
        self.version.l10n_be_worker_code_id = self.be_worker
        self.check_quarter_total('ONSSEMPLOYER_820', [15.12] * 3, 3000 * 1.08 * 1.4 / 100)

        # Worker - Large Company
        self.payroll_config.onss_importance_code = '5'
        self.check_quarter_total('ONSSEMPLOYER_820', [15.66] * 3, 3000 * 1.08 * 1.45 / 100)

    def test_onss_825_condition(self):
        """
        ONSSEMPLOYER_825
        Accounting: ONSS Workers Retirement Funds (Employer)
        """
        self.assertFalse(self.payslip._should_apply_onss_contribution('825'))

        self.payroll_config.l10n_be_employer_category_id = self.category_horeca
        self.version.l10n_be_worker_code_id = self.be_worker
        self.assertTrue(self.payslip._should_apply_onss_contribution('825'))
        self.check_condition('ONSSEMPLOYER_825', False)

        for retirement_fund in ['0', '8']:
            self.payroll_config.l10n_be_worker_retirement_fund = retirement_fund
            self.check_condition('ONSSEMPLOYER_825', True)

        self.payroll_config.l10n_be_employer_category_id = self.category_food_industry
        for retirement_fund in ['1', '2']:
            self.payroll_config.l10n_be_worker_retirement_fund = retirement_fund
            self.check_condition('ONSSEMPLOYER_825', True)

        self.employee.birthday = date(2026 - 61, 1, 1)
        retired_version = self.employee.create_version({
            'date_version': date(2025, 12, 1),
            'l10n_be_is_retired': True,
        })
        self.check_condition('ONSSEMPLOYER_825', False)

        retired_version.date_version = date(2026, 1, 1)
        self.check_condition('ONSSEMPLOYER_825', True)

        self.check_condition_dimona_categories('ONSSEMPLOYER_825', ['stu', 'ivt', 'flx'], False)

    def test_onss_825_computation(self):
        """
        ONSSEMPLOYER_825
        Accounting: ONSS Workers Retirement Funds (Employer)
        """
        # Worker - Contribution Due
        self.payroll_config.l10n_be_worker_retirement_fund = '0'
        self.payroll_config.l10n_be_employer_category_id = self.category_horeca
        self.version.l10n_be_worker_code_id = self.be_worker
        self.check_quarter_total('ONSSEMPLOYER_825', [11.88] * 3, 3000 * 1.08 * 1.1 / 100)

        # Worker - Contribution Not Due
        self.payroll_config.l10n_be_worker_retirement_fund = '8'
        self.check_quarter_total('ONSSEMPLOYER_825', [0] * 3, 3000 * 1.08 * 0 / 100)

        # Worker - Increased Contribution
        self.payroll_config.l10n_be_worker_retirement_fund = '1'
        self.payroll_config.l10n_be_employer_category_id = self.category_food_industry
        self.check_quarter_total('ONSSEMPLOYER_825', [1.08] * 3, 3000 * 1.08 * 0.1 / 100)

        # Worker - Solidarity Contribution
        self.payroll_config.l10n_be_worker_retirement_fund = '2'
        self.check_quarter_total('ONSSEMPLOYER_825', [0.65, 0.65, 0.64], 3000 * 1.08 * 0.06 / 100)

    def test_onss_830_condition(self):
        """
        ONSSEMPLOYER_830
        Accounting: ONSS Employees Existence Security Funds (Employer)
        """
        self.assertFalse(self.payslip._should_apply_onss_contribution('830'))

        self.payroll_config.l10n_be_employer_category_id = self.category_horeca
        self.version.l10n_be_worker_code_id = self.be_acs
        self.assertTrue(self.payslip._should_apply_onss_contribution('830'))
        self.check_condition('ONSSEMPLOYER_830', False)

        self.version.l10n_be_joint_committee_id = self.cp_302
        self.check_condition('ONSSEMPLOYER_830', True)
        self.check_condition_dimona_categories('ONSSEMPLOYER_830', ['stu', 'ivt', 'flx'], False)

    def test_onss_830_computation(self):
        """
        ONSSEMPLOYER_830
        Accounting: ONSS Employees Existence Security Funds (Employer)
        """
        # ACS - Small Company
        self.payroll_config.onss_importance_code = '4'
        self.payroll_config.l10n_be_employer_category_id = self.category_horeca
        self.version.l10n_be_worker_code_id = self.be_acs
        self.version.l10n_be_joint_committee_id = self.cp_302
        self.check_quarter_total('ONSSEMPLOYER_830', [14] * 3, 3000 * 1.4 / 100)

        # ACS - Large Company
        self.payroll_config.onss_importance_code = '5'
        self.check_quarter_total('ONSSEMPLOYER_830', [14.5] * 3, 3000 * 1.45 / 100)

    def test_onss_831_condition(self):
        """
        ONSSEMPLOYER_831
        Accounting: ONSS Employees Social Funds CPAE (Employer)
        """
        self.assertTrue(self.payslip._should_apply_onss_contribution('831'))
        self.check_condition('ONSSEMPLOYER_831', True)
        self.check_condition_dimona_categories('ONSSEMPLOYER_831', ['stu', 'ivt', 'flx'], False)

    def test_onss_831_computation(self):
        """
        ONSSEMPLOYER_831
        Accounting: ONSS Employees Social Funds CPAE (Employer)
        """
        # Employee
        self.check_quarter_total('ONSSEMPLOYER_831', [2.3] * 3, 3000 * 0.23 / 100)

    def test_onss_835_condition(self):
        """
        ONSSEMPLOYER_835
        Accounting: ONSS Employees Retirement Funds (Employer)
        """
        self.assertFalse(self.payslip._should_apply_onss_contribution('835'))

        self.payroll_config.l10n_be_employer_category_id = self.category_food_industry
        self.version.l10n_be_worker_code_id = self.be_acs
        self.assertTrue(self.payslip._should_apply_onss_contribution('835'))
        self.check_condition('ONSSEMPLOYER_835', False)

        for retirement_fund in ['0', '1', '8']:
            self.payroll_config.l10n_be_employee_retirement_fund = retirement_fund
            self.check_condition('ONSSEMPLOYER_835', True)

        self.employee.birthday = date(2026 - 61, 1, 1)
        retired_version = self.employee.create_version({
            'date_version': date(2025, 12, 1),
            'l10n_be_is_retired': True,
        })
        self.check_condition('ONSSEMPLOYER_835', False)

        retired_version.date_version = date(2026, 1, 1)
        self.check_condition('ONSSEMPLOYER_835', True)

        self.check_condition_dimona_categories('ONSSEMPLOYER_835', ['stu', 'ivt', 'flx'], False)

    def test_onss_835_computation(self):
        """
        ONSSEMPLOYER_835
        Accounting: ONSS Employees Retirement Funds (Employer)
        """
        # ACS - Contribution Due
        self.payroll_config.l10n_be_employee_retirement_fund = '0'
        self.payroll_config.l10n_be_employer_category_id = self.category_food_industry
        self.version.l10n_be_worker_code_id = self.be_acs
        self.check_quarter_total('ONSSEMPLOYER_835', [12.5] * 3, 3000 * 1.25 / 100)

        # ACS - Increased Contribution
        self.payroll_config.l10n_be_employee_retirement_fund = '1'
        self.check_quarter_total('ONSSEMPLOYER_835', [16.5] * 3, 3000 * 1.65 / 100)

        # ACS - Contribution Not Due
        self.payroll_config.l10n_be_employee_retirement_fund = '8'
        self.check_quarter_total('ONSSEMPLOYER_835', [0] * 3, 3000 * 0 / 100)

    def test_onss_852_condition(self):
        """
        ONSSEMPLOYER_852
        Accounting: ONSS Risk Groups Contribution (Employer)
        """
        self.assertTrue(self.payslip._should_apply_onss_contribution('852'))
        self.check_condition('ONSSEMPLOYER_852', False)

        self.payroll_config.l10n_be_at_risk_groups_contribution = True
        self.check_condition('ONSSEMPLOYER_852', True)
        self.check_condition_dimona_categories('ONSSEMPLOYER_852', ['stu', 'ivt', 'flx'], False)

    def test_onss_852_computation(self):
        """
        ONSSEMPLOYER_852
        Accounting: ONSS Risk Groups Contribution (Employer)
        """
        # Employee
        self.payroll_config.l10n_be_at_risk_groups_contribution = True
        self.check_quarter_total('ONSSEMPLOYER_852', [1] * 3, 3000 * 0.1 / 100)

        # Worker
        self.version.l10n_be_worker_code_id = self.be_worker
        self.check_quarter_total('ONSSEMPLOYER_852', [1.08] * 3, 3000 * 1.08 * 0.1 / 100)

    def test_onss_855_condition(self):
        """
        ONSSEMPLOYER_855
        Accounting: ONSS Special Contribution with Salary Moderation (Employer)
        """
        self.assertTrue(self.payslip._should_apply_onss_contribution('855'))
        self.check_condition('ONSSEMPLOYER_855', True)
        self.check_condition_dimona_categories('ONSSEMPLOYER_855', ['stu', 'ivt', 'flx'], False)

        self.payroll_config.onss_importance_code = '2'
        self.check_condition('ONSSEMPLOYER_855', False)

        self.payroll_config.onss_importance_code = '3'
        self.check_condition('ONSSEMPLOYER_855', True)

        self.version.l10n_be_worker_code_id = self.be_employee_no_salary_moderation
        self.check_condition('ONSSEMPLOYER_855', False)

    def test_onss_855_computation(self):
        """
        ONSSEMPLOYER_855
        Accounting: ONSS Special Contribution with Salary Moderation (Employer)
        """
        # Employee
        self.check_quarter_total('ONSSEMPLOYER_855', [16.9] * 3, 3000 * 1.69 / 100)

        # Worker
        self.version.l10n_be_worker_code_id = self.be_worker
        self.check_quarter_total('ONSSEMPLOYER_855', [18.25, 18.25, 18.26], 3000 * 1.08 * 1.69 / 100)

    def test_onss_857_condition(self):
        """
        ONSSEMPLOYER_857
        Accounting: ONSS Special Contribution without Salary Moderation (Employer)
        """
        self.assertFalse(self.payslip._should_apply_onss_contribution('857'))

        self.version.l10n_be_worker_code_id = self.be_employee_no_salary_moderation
        self.assertTrue(self.payslip._should_apply_onss_contribution('857'))
        self.check_condition('ONSSEMPLOYER_857', True)
        self.check_condition_dimona_categories('ONSSEMPLOYER_857', ['stu', 'ivt', 'flx'], False)

        self.payroll_config.onss_importance_code = '2'
        self.check_condition('ONSSEMPLOYER_857', False)

        self.payroll_config.onss_importance_code = '3'
        self.check_condition('ONSSEMPLOYER_857', True)

    def test_onss_857_computation(self):
        """
        ONSSEMPLOYER_857
        Accounting: ONSS Special Contribution without Salary Moderation (Employer)
        """
        # Employee No Salary Moderation
        self.version.l10n_be_worker_code_id = self.be_employee_no_salary_moderation
        self.check_quarter_total('ONSSEMPLOYER_857', [16] * 3, 3000 * 1.6 / 100)

        # Worker No Salary Moderation
        self.version.l10n_be_worker_code_id = self.be_worker_no_salary_moderation
        self.check_quarter_total('ONSSEMPLOYER_857', [17.28] * 3, 3000 * 1.08 * 1.6 / 100)

    def test_onss_859_condition(self):
        """
        ONSSEMPLOYER_859
        Accounting: ONSS Temporary Unemployment (Employer)
        """
        self.assertTrue(self.payslip._should_apply_onss_contribution('859'))
        self.check_condition('ONSSEMPLOYER_859', True)
        self.check_condition_dimona_categories('ONSSEMPLOYER_859', ['stu', 'ivt', 'flx'], False)

    def test_onss_859_computation(self):
        """
        ONSSEMPLOYER_859
        Accounting: ONSS Temporary Unemployment (Employer)
        """
        # Employee
        self.check_quarter_total('ONSSEMPLOYER_859', [1] * 3, 3000 * 0.1 / 100)

        # Worker
        self.version.l10n_be_worker_code_id = self.be_worker
        self.check_quarter_total('ONSSEMPLOYER_859', [1.08] * 3, 3000 * 1.08 * 0.1 / 100)

    def test_onss_865_condition(self):
        """
        ONSSEMPLOYER_865
        Accounting: ONSS Group Insurance (Employer)
        """
        self.check_condition('ONSSEMPLOYER_865', False)

        self.version.l10n_be_group_insurance_company_contribution = 0.5
        self.check_condition('ONSSEMPLOYER_865', True)

    def test_onss_865_computation(self):
        """
        ONSSEMPLOYER_865
        Accounting: ONSS Group Insurance (Employer)
        """
        # Employee
        # GI.COMP.CONT = ONSS_BASE * COMPANY_CONTRIBUTION = 3000€ * 50% = 1500€
        self.version.l10n_be_group_insurance_company_contribution = 0.5
        self.check_quarter_total('ONSSEMPLOYER_865', [44.3] * 3, 1500 * 8.86 / 100)

        # Worker
        self.version.l10n_be_worker_code_id = self.be_worker
        self.check_quarter_total('ONSSEMPLOYER_865', [47.84, 47.85, 47.84], 1500 * 1.08 * 8.86 / 100)

    def test_onss_878_condition(self):
        """
        ONSSEMPLOYER_878
        Accounting: ONSS Journalist Pension Fund (Employer)
        """
        self.check_condition('ONSSEMPLOYER_878', False)

        self.version.l10n_be_worker_status = 'PJ'
        self.check_condition('ONSSEMPLOYER_878', True)

    def test_onss_878_computation(self):
        """
        ONSSEMPLOYER_878
        Accounting: ONSS Journalist Pension Fund (Employer)
        """
        self.version.l10n_be_worker_status = 'PJ'

        rate = 20
        percentage = 2.0  # 2.0%

        self.check_quarter_total('ONSSEMPLOYER_878', [rate] * 3, 3000 * percentage / 100)

    def test_onss_889_condition(self):
        """
        ONSSEMPLOYER_889
        Accounting: ONSS Traffic Fines Contribution (Employer)
        """
        self.assertTrue(self.payslip._should_apply_onss_contribution('889'))
        self.check_condition('ONSSEMPLOYER_889', False)

        self.payslip._set_input_value('TRAFFIC_FINES', 200)
        self.check_condition('ONSSEMPLOYER_889', True)
        self.check_condition_dimona_categories('ONSSEMPLOYER_889', ['stu', 'ivt', 'flx'], False)

    def test_onss_889_computation(self):
        """
        ONSSEMPLOYER_889
        Accounting: ONSS Traffic Fines Contribution (Employer)
        """
        # Employee
        self.payslip._set_input_value('TRAFFIC_FINES', 200)
        self.check_quarter_total('ONSSEMPLOYER_889', [66, None, None], 200 * 33 / 100)

        # Worker
        self.version.l10n_be_worker_code_id = self.be_worker
        self.check_quarter_total('ONSSEMPLOYER_889', [66, None, None], 200 * 33 / 100)

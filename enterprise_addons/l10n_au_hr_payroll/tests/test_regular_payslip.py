# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import date
from freezegun import freeze_time

from odoo.tests import tagged
from .common import TestPayrollCommon


@tagged("post_install_l10n", "post_install", "-at_install", "l10n_au_hr_payroll")
class TestRegularPayslip(TestPayrollCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.default_payroll_structure = cls.env.ref("l10n_au_hr_payroll.hr_payroll_structure_au_regular")
        cls.tax_treatment_category = 'R'

    def test_regular_payslip_1(self):
        employee, contract = self._create_employee(contract_info={
            'employee': 'Test Employee',
            'employment_basis_code': 'F',
            'leave_loading': 'once',
            'leave_loading_rate': 17.5,
            'workplace_giving_type': 'both',
            'workplace_giving_employee': 100,
            'workplace_giving_employer': 100,
            'salary_sacrifice_superannuation': 100,
            'salary_sacrifice_other': 0,
            'wage_type': 'monthly',
            'wage': 5000,
            'casual_loading': 0,
            'l10n_au_training_loan': False,
            'l10n_au_tax_free_threshold': True})
        self._test_payslip(
            employee,
            contract,
            expected_worked_days=[
                # (work_entry_type_id.id, number_of_day, number_of_hours, amount)
                (self.work_entry_types['002.00'].id, 21, 159.6, 5000),
            ],
            expected_lines=[
                # (code, total)
                ('BASIC', 5000),
                ('OTE', 5050),
                ('EXTRA', 50),
                ('SALARY.SACRIFICE.TOTAL', -200),
                ('SALARY.SACRIFICE.OTHER', -100),
                ('WORKPLACE.GIVING', -100),
                ('GROSS', 4750),
                ('WITHHOLD', -845),
                ('MEDICARE', 0),
                ('WITHHOLD.TOTAL', -845),
                ('NET', 3905),
                ('SUPER.CONTRIBUTION', 100),
                ('SUPER', 555.5),
            ],
            input_lines=[{
                'salary_rule_id': self.env.ref('l10n_au_hr_payroll.input_gross_director_fee').id,
                'amount': 50,
            }]
        )

    def test_regular_payslip_2(self):
        employee, contract = self._create_employee(contract_info={
            'employee': 'Test Employee',
            'employment_basis_code': 'F',
            'leave_loading': 'regular',
            'leave_loading_rate': 17.5,
            'workplace_giving_employee': 0,
            'workplace_giving_employer': 100,
            'salary_sacrifice_superannuation': 100,
            'salary_sacrifice_other': 0,
            'wage_type': 'monthly',
            'wage': 5000,
            'casual_loading': 0,
            'l10n_au_training_loan': False,
            'l10n_au_tax_free_threshold': True})
        self._test_payslip(
            employee,
            contract,
            expected_worked_days=[
                # (work_entry_type_id.id, number_of_day, number_of_hours, amount)
                (self.work_entry_types['002.00'].id, 21, 159.6, 5000),
            ],
            expected_lines=[
                # (code, total)
                ('BASIC', 5000),
                ('OTE', 5000),
                ('SALARY.SACRIFICE.TOTAL', -200),
                ('SALARY.SACRIFICE.OTHER', -100),
                ('GROSS', 4800),
                ('WITHHOLD', -862),
                ('MEDICARE', 0),
                ('WITHHOLD.TOTAL', -862),
                ('NET', 3938),
                ('SUPER.CONTRIBUTION', 100),
                ('SUPER', 550),
            ],
        )

    def test_regular_payslip_3(self):
        employee, contract = self._create_employee(contract_info={
            'employee': 'Test Employee',
            'employment_basis_code': 'F',
            'leave_loading': 'once',
            'leave_loading_rate': 17.5,
            'workplace_giving_employee': 200,
            'workplace_giving_employer': 0,
            'salary_sacrifice_superannuation': 0,
            'salary_sacrifice_other': 100,
            'wage_type': 'monthly',
            'wage': 5000,
            'casual_loading': 0,
            'l10n_au_training_loan': False,
            'l10n_au_tax_free_threshold': False})
        self._test_payslip(
            employee,
            contract,
            expected_worked_days=[
                # (work_entry_type_id.id, number_of_day, number_of_hours, amount)
                (self.work_entry_types['002.00'].id, 21, 159.6, 5000),
            ],
            expected_lines=[
                # (code, total)
                ('BASIC', 5000),
                ('OTE', 5000),
                ('SALARY.SACRIFICE.TOTAL', -100),
                ('SALARY.SACRIFICE.OTHER', -100),
                ('WORKPLACE.GIVING', -200),
                ('GROSS', 4700),
                ('WITHHOLD', -1352),
                ('WITHHOLD.TOTAL', -1352),
                ('NET', 3348),
                ('SUPER', 550),
            ],
        )

    def test_regular_payslip_4(self):
        employee, contract = self._create_employee(contract_info={
            'employee': 'Test Employee',
            'employment_basis_code': 'F',
            'leave_loading': 'regular',
            'leave_loading_rate': 17.5,
            'workplace_giving_employee': 0,
            'workplace_giving_employer': 0,
            'salary_sacrifice_superannuation': 100,
            'salary_sacrifice_other': 100,
            'wage_type': 'monthly',
            'wage': 5000,
            'casual_loading': 0,
            'l10n_au_training_loan': False,
            'l10n_au_tax_free_threshold': False})
        self._test_payslip(
            employee,
            contract,
            expected_worked_days=[
                # (work_entry_type_id.id, number_of_day, number_of_hours, amount)
                (self.work_entry_types['002.00'].id, 21, 159.6, 5000),
            ],
            expected_lines=[
                # (code, total)
                ('BASIC', 5000),
                ('OTE', 5000),
                ('SALARY.SACRIFICE.TOTAL', -200),
                ('SALARY.SACRIFICE.OTHER', -100),
                ('GROSS', 4800),
                ('WITHHOLD', -1387),
                ('WITHHOLD.TOTAL', -1387),
                ('NET', 3413),
                ('SUPER.CONTRIBUTION', 100),
                ('SUPER', 550),
            ],
        )

    def test_regular_payslip_5(self):
        employee, contract = self._create_employee(contract_info={
            'employee': 'Test Employee',
            'employment_basis_code': 'F',
            'tfn_declaration': '000000000',
            'leave_loading': 'regular',
            'leave_loading_rate': 17.5,
            'workplace_giving_employee': 100,
            'workplace_giving_employer': 100,
            'salary_sacrifice_superannuation': 100,
            'salary_sacrifice_other': 0,
            'wage_type': 'monthly',
            'wage': 5000,
            'casual_loading': 0,
            'l10n_au_training_loan': False,
            'l10n_au_tax_free_threshold': False})

        self._test_payslip(
            employee,
            contract,
            expected_worked_days=[
                # (work_entry_type_id.id, number_of_day, number_of_hours, amount)
                (self.work_entry_types['002.00'].id, 21, 159.6, 5000),
            ],
            expected_lines=[
                # (code, total)
                ('BASIC', 5000),
                ('OTE', 5000),
                ('SALARY.SACRIFICE.TOTAL', -200),
                ('SALARY.SACRIFICE.OTHER', -100),
                ('WORKPLACE.GIVING', -100),
                ('GROSS', 4700),
                ('WITHHOLD', -2207.75),
                ('WITHHOLD.TOTAL', -2207.75),
                ('NET', 2492.25),
                ('SUPER.CONTRIBUTION', 100),
                ('SUPER', 550),
            ],
        )

    def test_regular_payslip_weekly_withholding_extra(self):
        employee, contract = self._create_employee(contract_info={
            'employee': 'Test Employee',
            'employment_basis_code': 'F',
            'leave_loading': 'regular',
            'leave_loading_rate': 17.5,
            'workplace_giving_employee': 0,
            'workplace_giving_employer': 0,
            'salary_sacrifice_superannuation': 100,
            'salary_sacrifice_other': 100,
            'wage_type': 'monthly',
            'schedule_pay': 'weekly',
            'wage': 1250,
            'casual_loading': 0,
            'extra_pay': True,
            'l10n_au_training_loan': False})
        payslip_date = date(2023, 7, 3)
        payslip_end_date = date(2023, 7, 9)
        self._test_payslip(
            employee,
            contract,
            expected_worked_days=[
                # (work_entry_type_id.id, number_of_day, number_of_hours, amount)
                (self.work_entry_types['002.00'].id, 5, 38, 1250),
            ],
            expected_lines=[
                # (code, total)
                ('BASIC', 1250),
                ('OTE', 1250),
                ('SALARY.SACRIFICE.TOTAL', -200),
                ('SALARY.SACRIFICE.OTHER', -100),
                ('GROSS', 1050),
                ('WITHHOLD', -301),
                ('EXTRA.WITHHOLD', -3),
                ('WITHHOLD.TOTAL', -304),
                ('NET', 746),
                ('SUPER.CONTRIBUTION', 100),
                ('SUPER', 137.5),
            ],
            payslip_date_from=payslip_date,
            payslip_date_to=payslip_end_date,
        )

    def test_regular_payslip_7(self):
        employee, contract = self._create_employee(contract_info={
            'employee': 'Test Employee',
            'employment_basis_code': 'F',
            'tfn_declaration': 'provided',
            'tfn': '999999661',
            'salary_sacrifice_superannuation': 200,
            'salary_sacrifice_other': 100,
            'workplace_giving_employee': 50,
            'workplace_giving_employer': 50,
            'wage_type': 'monthly',
            'wage': 5000,
            'casual_loading': 0,
            'l10n_au_training_loan': True,
            'l10n_au_tax_free_threshold': True})

        self.assertEqual(employee.l10n_au_tax_treatment_code, 'RTSXXX')

        self._test_payslip(
            employee,
            contract,
            expected_worked_days=[
                # (work_entry_type_id.id, number_of_day, number_of_hours, amount)
                (self.work_entry_types['002.00'].id, 23, 174.8, 5000),
            ],
            expected_lines=[
                # (code, total)
                ('BASIC', 5000),
                ('OTE', 6050),
                ('EXTRA', 200),
                ('SALARY.SACRIFICE.TOTAL', -350),
                ('ALW', 550),
                ('ALW.TAXFREE', 0),
                ('RTW', 300),
                ('SALARY.SACRIFICE.OTHER', -150),
                ('WORKPLACE.GIVING', -50),
                ('GROSS', 5650),
                ('WITHHOLD', -945),
                ('RTW.WITHHOLD', -96),
                ('WITHHOLD.STUDY', -143),
                ('MEDICARE', 0),
                ('WITHHOLD.TOTAL', -1184),
                ('NET', 4466),
                ('SUPER.CONTRIBUTION', 200),
                ('SUPER', 695.75),
            ],
            input_lines=self.default_input_lines,
            payslip_date_from=date(2024, 7, 1),
            payslip_date_to=date(2024, 7, 31),
        )

        # Post Sept 2025 loan withhold
        self._test_payslip(
            employee,
            contract,
            expected_worked_days=[
                # (work_entry_type_id.id, number_of_day, number_of_hours, amount)
                (self.work_entry_types['002.00'].id, 22, 167.2, 5000),
            ],
            expected_lines=[
                # (code, total)
                ('BASIC', 5000),
                ('OTE', 6050),
                ('EXTRA', 200),
                ('SALARY.SACRIFICE.TOTAL', -350),
                ('ALW', 550),
                ('ALW.TAXFREE', 0),
                ('RTW', 300),
                ('SALARY.SACRIFICE.OTHER', -150),
                ('WORKPLACE.GIVING', -50),
                ('GROSS', 5650),
                ('WITHHOLD', -945),
                ('RTW.WITHHOLD', -96),
                ('WITHHOLD.STUDY', 0),
                ('MEDICARE', 0),
                ('WITHHOLD.TOTAL', -1041),
                ('NET', 4609),
                ('SUPER.CONTRIBUTION', 200),
                ('SUPER', 726),
            ],
            input_lines=self.default_input_lines,
            payslip_date_from=date(2025, 9, 1),
            payslip_date_to=date(2025, 9, 30),
        )

    def test_regular_payslip_8(self):
        employee, contract = self._create_employee(contract_info={
            'employee': 'Test Employee',
            'employment_basis_code': 'C',
            'tfn_declaration': '111111111',
            'salary_sacrifice_superannuation': 200,
            'salary_sacrifice_other': 100,
            'workplace_giving_employee': 50,
            'workplace_giving_employer': 50,
            'wage_type': 'monthly',
            'wage': 5000,
            'casual_loading': 0,
            'l10n_au_training_loan': False,
            'l10n_au_tax_free_threshold': True})

        self.assertEqual(employee.l10n_au_tax_treatment_code, 'RTXXXX')

        self._test_payslip(
            employee,
            contract,
            expected_worked_days=[
                # (work_entry_type_id.id, number_of_day, number_of_hours, amount)
                (self.work_entry_types['002.00'].id, 22, 167.2, 5000),
            ],
            expected_lines=[
                # (code, total)
                ('BASIC', 5000),
                ('OTE', 6050),
                ('EXTRA', 200),
                ('SALARY.SACRIFICE.TOTAL', -350),
                ('ALW', 550),
                ('ALW.TAXFREE', 0),
                ('RTW', 300),
                ('SALARY.SACRIFICE.OTHER', -150),
                ('WORKPLACE.GIVING', -50),
                ('GROSS', 5650),
                # ('WITHHOLD', -924), The Correct value once a variable schedule is implemented
                ('WITHHOLD', -945),
                ('RTW.WITHHOLD', -96),
                ('MEDICARE', 0),
                ('WITHHOLD.TOTAL', -1041),
                ('NET', 4609),
                ('SUPER.CONTRIBUTION', 200),
                ('SUPER', 695.75),
            ],
            input_lines=self.default_input_lines,
            payslip_date_from=date(2024, 8, 1),
            payslip_date_to=date(2024, 8, 31),
        )

    def test_regular_payslip_9(self):
        employee, contract = self._create_employee(contract_info={
            'employee': 'Test Employee',
            'employment_basis_code': 'F',
            'tfn_declaration': 'provided',
            'tfn': '999999661',
            'salary_sacrifice_superannuation': 200,
            'salary_sacrifice_other': 100,
            'workplace_giving_employee': 50,
            'workplace_giving_employer': 50,
            'wage_type': 'monthly',
            'wage': 5000,
            'casual_loading': 0,
            'l10n_au_training_loan': False,
            'l10n_au_tax_free_threshold': False})

        self.assertEqual(employee.l10n_au_tax_treatment_code, 'RNXXXX')

        self._test_payslip(
            employee,
            contract,
            expected_worked_days=[
                # (work_entry_type_id.id, number_of_day, number_of_hours, amount)
                (self.work_entry_types['002.00'].id, 23, 174.8, 5000),
            ],
            expected_lines=[
                # (code, total)
                ('BASIC', 5000),
                ('OTE', 6050),
                ('EXTRA', 200),
                ('SALARY.SACRIFICE.TOTAL', -350),
                ('ALW', 550),
                ('ALW.TAXFREE', 0),
                ('RTW', 300),
                ('SALARY.SACRIFICE.OTHER', -150),
                ('WORKPLACE.GIVING', -50),
                ('GROSS', 5650),
                ('WITHHOLD', -1426),
                ('RTW.WITHHOLD', -96),
                ('WITHHOLD.TOTAL', -1522),
                ('NET', 4128),
                ('SUPER.CONTRIBUTION', 200),
                ('SUPER', 695.75),
            ],
            input_lines=self.default_input_lines,
            payslip_date_from=date(2024, 7, 1),
            payslip_date_to=date(2024, 7, 31),
        )

    def test_regular_10_loan_stsl(self):
        # Weekly Loan STSL from 24 Sept 2025 onwards
        employee, contract = self._create_employee(contract_info={
            'employee': 'Test Employee',
            'employment_basis_code': 'F',
            'wage_type': 'monthly',
            'schedule_pay': 'weekly',
            'wage': 2608.36,
            'l10n_au_training_loan': True,
            'l10n_au_tax_free_threshold': True})

        self._test_payslip(
            employee,
            contract,
            expected_worked_days=[
                # (work_entry_type_id.id, number_of_day, number_of_hours, amount)
                (self.work_entry_types['002.00'].id, 5, 38, 2608.36),
            ],
            expected_lines=[
                # (code, total)
                ('BASIC', 2608.36),
                ('OTE', 2608.36),
                ('GROSS', 2608.36),
                ('WITHHOLD', -659),
                ('WITHHOLD.STUDY', -202),
                ('MEDICARE', 0),
                ('WITHHOLD.TOTAL', -861),
                ('NET', 1747.32),
                ('SUPER', 313),
            ],
            payslip_date_from=date(2025, 9, 29),
            payslip_date_to=date(2025, 10, 3)
        )

    def test_partial_period_uses_hourly_wage_and_worked_hours(self):
        """
        Partial period attendance amount should use hourly wage with worked hours only.
        amount = hourly_wage * worked_hours * amount_rate
        """
        employee, contract = self._create_employee(contract_info={
            'employee': 'Test Partial Period',
            'wage_type': 'hourly',
            'hourly_wage': 10,
        })
        attendance_work_entry_type = self.work_entry_types['002.00']
        attendance_work_entry_type.amount_rate = 1.5
        payslip = self.env["hr.payslip"].create({
            "employee_id": employee.id,
            "version_id": contract.id,
            "struct_id": self.default_payroll_structure.id,
            "date_from": date(2026, 5, 1),
            "date_to": date(2026, 5, 15),
        })
        payslip.action_refresh_from_work_entries()
        attendance_worked_day = payslip.worked_days_line_ids.filtered(
            lambda w: w.work_entry_type_id == attendance_work_entry_type
        )
        self.assertTrue(attendance_worked_day)
        self.assertAlmostEqual(attendance_worked_day.number_of_days, 11)
        self.assertAlmostEqual(attendance_worked_day.number_of_hours, 83.6, 2)
        self.assertAlmostEqual(attendance_worked_day.amount, 1254, 2)  # amount = 83.6 * 10 * 1.5 = 1254

    def test_work_entry_rate_with_leave_loading_casual_loading(self):
        """
        Case 1: Attendance work entry with casual loading.
            amount = hourly_wage * hours * (amount_rate + casual_loading)

        Case 2: AU.PT leave loading.
            amount = hourly_wage * hours * (1 + leave_loading_rate / 100)
            Continue after leave loading calculation (skip casual loading).

        Case 3: STP code 'T' overtime work entry.
            Casual loading must not be applied.
            amount = hourly_wage * hours * amount_rate
        """
        employee, contract = self._create_employee(contract_info={
            'employee': 'Test Mixed AU Case',
            'wage_type': 'hourly',
            'hourly_wage': 10,
            'casual_loading': 0.25,
            'leave_loading': 'regular',
            'leave_loading_rate': 17.5,
        })
        attendance_work_entry_type = self.work_entry_types['002.00']
        au_pt_leave_type = self.env.ref('hr_work_entry.l10n_au_work_entry_type_annual_leave')
        overtime_work_entry_type = self.env.ref('hr_work_entry.l10n_au_work_entry_type_public_holiday_week_day')
        attendance_work_entry_type.amount_rate = 1.5
        au_pt_leave_type.with_context(install_mode=True).write({
            'amount_rate': 1.5,
            'requires_allocation': False,
        })
        overtime_work_entry_type.with_context(install_mode=True).write({
            'amount_rate': 1.5,
            'requires_allocation': False,
            'count_as': 'absence',
            'l10n_au_work_stp_code': 'T',
        })
        self.env['hr.leave'].create([
            {
                'name': 'AU PT Leave',
                'employee_id': employee.id,
                'work_entry_type_id': au_pt_leave_type.id,
                'request_date_from': date(2026, 5, 11),
                'request_date_to': date(2026, 5, 11),
            },
            {
                'name': '1d Overtime',
                'employee_id': employee.id,
                'work_entry_type_id': overtime_work_entry_type.id,
                'request_date_from': date(2026, 5, 6),
                'request_date_to': date(2026, 5, 6),
            },
        ])._action_validate()
        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': contract.id,
            'struct_id': self.default_payroll_structure.id,
            'date_from': date(2026, 5, 1),
            'date_to': date(2026, 5, 31),
        })
        payslip.action_refresh_from_work_entries()

        attendance_worked_day = payslip.worked_days_line_ids.filtered(
            lambda w: w.work_entry_type_id == attendance_work_entry_type
        )
        self.assertTrue(attendance_worked_day)
        self.assertAlmostEqual(attendance_worked_day.number_of_days, 19)
        self.assertAlmostEqual(attendance_worked_day.number_of_hours, 144.4, 2)
        self.assertAlmostEqual(attendance_worked_day.amount, 2527, 2)  # amount = 144.4 * 10 * (1.5 + 0.25) = 2527

        au_pt_worked_day = payslip.worked_days_line_ids.filtered(
            lambda w: w.work_entry_type_id == au_pt_leave_type
        )
        self.assertTrue(au_pt_worked_day)
        self.assertAlmostEqual(au_pt_worked_day.number_of_days, 1)
        self.assertAlmostEqual(au_pt_worked_day.number_of_hours, 7.6)
        self.assertAlmostEqual(au_pt_worked_day.amount, 89.3, 2)  # amount = 7.6 * 10 * 1.175 = 89.3

        overtime_worked_day = payslip.worked_days_line_ids.filtered(
            lambda w: w.work_entry_type_id == overtime_work_entry_type
        )
        self.assertTrue(overtime_worked_day)
        self.assertAlmostEqual(overtime_worked_day.number_of_days, 1)
        self.assertAlmostEqual(overtime_worked_day.number_of_hours, 7.6)
        self.assertAlmostEqual(overtime_worked_day.amount, 114, 2)  # amount = 7.6 * 10 * 1.5 = 114

    def test_regular_11_qualifying_earnings(self):
        # There will be a new line QE on the paslip from 1st July 2026
        employee, contract = self._create_employee(contract_info={
            'employee': 'Test Employee',
            'employment_basis_code': 'F',
            'wage_type': 'monthly',
            'schedule_pay': 'weekly',
            'wage': 2608.36,
            'l10n_au_training_loan': True,
            'l10n_au_tax_free_threshold': True})

        self._test_payslip(
            employee,
            contract,
            expected_worked_days=[
                # (work_entry_type_id.id, number_of_day, number_of_hours, amount)
                (self.work_entry_types['002.00'].id, 5, 38, 2608.36),
            ],
            expected_lines=[
                # (code, total)
                ('BASIC', 2608.36),
                ('OTE', 2608.36),
                ('GROSS', 2608.36),
                ('WITHHOLD', -659),
                ('WITHHOLD.STUDY', -202),
                ('MEDICARE', 0),
                ('WITHHOLD.TOTAL', -861),
                ('NET', 1747.32),
                ('SUPER', 313),
            ],
            payslip_date_from=date(2026, 6, 1),
            payslip_date_to=date(2026, 6, 7)
        )

        self._test_payslip(
            employee,
            contract,
            expected_worked_days=[
                # (work_entry_type_id.id, number_of_day, number_of_hours, amount)
                (self.work_entry_types['002.00'].id, 5, 38, 2608.36),
            ],
            expected_lines=[
                # (code, total)
                ('BASIC', 2608.36),
                ('OTE', 2608.36),
                ('GROSS', 2608.36),
                ('QE', 2608.36),
                ('WITHHOLD', -654),
                ('WITHHOLD.STUDY', -193),
                ('MEDICARE', 0),
                ('WITHHOLD.TOTAL', -847),
                ('NET', 1761.36),
                ('SUPER', 313),
            ],
            payslip_date_from=date(2026, 7, 1),
            payslip_date_to=date(2026, 7, 7)
        )

    @freeze_time('2026-07-15')
    def test_regular_12_super_cap(self):
        """ From 1 July 2026 the Super Guarantee is computed on the Qualifying Earnings
        (QE) at the 12% rate, but only up to the yearly maximum contribution base (cap).
        Once the cumulative QE of the financial year reaches the cap (270830) no further
        super is accrued. Driven by ``rule_parameter_super_2026``: {"rate": 12, "cap": 270830}.
        """
        employee, contract = self._create_employee(contract_info={
            'employee': 'Test Employee',
            'employment_basis_code': 'F',
            'wage_type': 'monthly',
            'wage': 100000,
            'l10n_au_training_loan': False,
            'l10n_au_tax_free_threshold': True,
        })

        # Month 1: well below the cap -> full 12% on QE.
        self._test_payslip(
            employee,
            contract,
            expected_worked_days=[
                (self.work_entry_types['002.00'].id, 23, 174.8, 100000),
            ],
            expected_lines=[
                ('BASIC', 100000),
                ('OTE', 100000),
                ('GROSS', 100000),
                ('QE', 100000),
                ('WITHHOLD', -44157),
                ('MEDICARE', 0),
                ('WITHHOLD.TOTAL', -44157),
                ('NET', 55843),
                ('SUPER', 12000),  # 100000 * 12%
            ],
            payslip_date_from=date(2026, 7, 1),
            payslip_date_to=date(2026, 7, 31),
        )

        # Month 2: cumulative QE = 200000, still below the cap -> full 12%.
        self._test_payslip(
            employee,
            contract,
            expected_worked_days=[
                (self.work_entry_types['002.00'].id, 21, 159.6, 100000),
            ],
            expected_lines=[
                ('BASIC', 100000),
                ('OTE', 100000),
                ('GROSS', 100000),
                ('QE', 100000),
                ('WITHHOLD', -44157),
                ('MEDICARE', 0),
                ('WITHHOLD.TOTAL', -44157),
                ('NET', 55843),
                ('SUPER', 12000),  # 100000 * 12%
            ],
            payslip_date_from=date(2026, 8, 1),
            payslip_date_to=date(2026, 8, 31),
        )

        # Month 3: cumulative QE crosses the cap. Only 70830 (270830 - 200000) of QE
        # remains eligible -> super is capped.
        self._test_payslip(
            employee,
            contract,
            expected_worked_days=[
                (self.work_entry_types['002.00'].id, 22, 167.2, 100000),
            ],
            expected_lines=[
                ('BASIC', 100000),
                ('OTE', 100000),
                ('GROSS', 100000),
                ('QE', 100000),
                ('WITHHOLD', -44157),
                ('MEDICARE', 0),
                ('WITHHOLD.TOTAL', -44157),
                ('NET', 55843),
                ('SUPER', 8499.6),  # 70830 * 12%
            ],
            payslip_date_from=date(2026, 9, 1),
            payslip_date_to=date(2026, 9, 30),
        )

        # Month 4: cap already reached -> no super accrued.
        self._test_payslip(
            employee,
            contract,
            expected_worked_days=[
                (self.work_entry_types['002.00'].id, 22, 167.2, 100000),
            ],
            expected_lines=[
                ('BASIC', 100000),
                ('OTE', 100000),
                ('GROSS', 100000),
                ('QE', 100000),
                ('WITHHOLD', -44157),
                ('MEDICARE', 0),
                ('WITHHOLD.TOTAL', -44157),
                ('NET', 55843),
                ('SUPER', 0),  # cap reached
            ],
            payslip_date_from=date(2026, 10, 1),
            payslip_date_to=date(2026, 10, 31),
        )

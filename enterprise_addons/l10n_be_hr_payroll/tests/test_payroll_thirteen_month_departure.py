# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.tests import tagged
from .common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestPayrollThirteenMonthDeparture(TestPayrollCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.leaving_type_fired = cls.env.ref('hr.departure_fired')
        cls.leaving_type_resigned = cls.env.ref('hr.departure_resigned')
        cls.leaving_type_retired = cls.env.ref('hr.departure_retired')
        cls.leaving_type_freelance = cls.env.ref('l10n_be_hr_payroll.departure_freelance')
        cls.struct_thirteen_month = cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_thirteen_month')

    def _create_departure(self, employee, departure_date, reason):
        return self.env['hr.employee.departure'].create({
            'employee_id': employee.id,
            'dismissal_date': departure_date,
            'departure_date': departure_date,
            'departure_reason_id': reason.id,
            'departure_description': 'Test',
        })

    # Eligibility
    def test_fired_meets_seniority_is_eligible(self):
        employee = self.create_employee({
            'name': '13th Month Fired Eligible',
            'contract_date_start': date(2025, 1, 1),
        })
        departure = self._create_departure(employee, date(2025, 8, 1), self.leaving_type_fired)
        self.assertTrue(departure.l10n_be_thirteen_month_eligible)

    def test_fired_below_seniority_is_not_eligible(self):
        employee = self.create_employee({
            'name': '13th Month Fired Not Eligible',
            'contract_date_start': date(2025, 1, 1),
        })
        departure = self._create_departure(employee, date(2025, 3, 1), self.leaving_type_fired)
        self.assertFalse(departure.l10n_be_thirteen_month_eligible)

    def test_fired_exactly_six_months_is_eligible(self):
        employee = self.create_employee({
            'name': '13th Month Fired Exact Boundary',
            'contract_date_start': date(2025, 1, 1),
        })
        departure = self._create_departure(employee, date(2025, 7, 1), self.leaving_type_fired)
        self.assertTrue(departure.l10n_be_thirteen_month_eligible,
            "6 months of seniority should be enough for a fired employee to be eligible.")

    def test_resigned_meets_seniority_is_eligible(self):
        employee = self.create_employee({
            'name': '13th Month Resigned Eligible',
            'contract_date_start': date(2020, 1, 1),
        })
        departure = self._create_departure(employee, date(2025, 6, 1), self.leaving_type_resigned)
        self.assertTrue(departure.l10n_be_thirteen_month_eligible)

    def test_resigned_below_seniority_is_not_eligible(self):
        employee = self.create_employee({
            'name': '13th Month Resigned Not Eligible',
            'contract_date_start': date(2023, 6, 1),
        })
        departure = self._create_departure(employee, date(2025, 6, 1), self.leaving_type_resigned)
        self.assertFalse(departure.l10n_be_thirteen_month_eligible)

    def test_resigned_exactly_three_years_is_eligible(self):
        employee = self.create_employee({
            'name': '13th Month Resigned Exact Boundary',
            'contract_date_start': date(2022, 1, 1),
        })
        departure = self._create_departure(employee, date(2025, 1, 1), self.leaving_type_resigned)
        self.assertTrue(departure.l10n_be_thirteen_month_eligible,
            "3 years of seniority should be enough for a resigned employee to be eligible.")

    def test_retired_meets_six_month_seniority_is_eligible(self):
        employee = self.create_employee({
            'name': '13th Month Retired Eligible',
            'contract_date_start': date(2025, 1, 1),
        })
        departure = self._create_departure(employee, date(2025, 8, 1), self.leaving_type_retired)
        self.assertTrue(departure.l10n_be_thirteen_month_eligible,
            "Retired departures use the same 6-month seniority requirement as fired employees.")

    def test_other_departure_reason_requires_three_years_seniority(self):
        employee = self.create_employee({
            'name': '13th Month Freelance Not Eligible',
            'contract_date_start': date(2025, 1, 1),
        })
        departure = self._create_departure(employee, date(2025, 8, 1), self.leaving_type_freelance)
        self.assertFalse(departure.l10n_be_thirteen_month_eligible,
            "Departure reasons outside the 6-month list still require 3 years of seniority.")

    def test_other_departure_reason_meets_three_years_seniority_is_eligible(self):
        employee = self.create_employee({
            'name': '13th Month Freelance Eligible',
            'contract_date_start': date(2020, 1, 1),
        })
        departure = self._create_departure(employee, date(2025, 6, 1), self.leaving_type_freelance)
        self.assertTrue(departure.l10n_be_thirteen_month_eligible,
            "Departure reasons outside the 6-month list are eligible once 3 years of seniority is reached.")

    def test_non_jc200_employee_is_never_eligible(self):
        employee = self.create_employee({
            'name': '13th Month Non-CP200 Not Eligible',
            'contract_date_start': date(2000, 1, 1),
            'l10n_be_joint_committee_id': self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_302').id,
        })
        departure = self._create_departure(employee, date(2025, 6, 1), self.leaving_type_fired)
        self.assertFalse(departure.l10n_be_thirteen_month_eligible,
            "13th month upon departure is specific to JC200, regardless of seniority or departure reason.")

    # Payslip generation
    def test_generate_thirteen_month_prorates_full_months_only(self):
        employee = self.create_employee({
            'name': '13th Month Prorated Amount',
            'wage': 12000.0,
            'contract_date_start': date(2020, 1, 1),
        })
        departure_date = date(2025, 11, 9)
        departure = self._create_departure(employee, departure_date, self.leaving_type_fired)

        payslip = departure._generate_termination_thirteen_month()

        self.assertEqual(payslip.struct_id, self.struct_thirteen_month)
        self.assertEqual(payslip.date_from, departure_date)
        self.assertEqual(payslip.date_to, departure_date)
        basic = payslip._get_line_values(['BONUS_BASIC'])['BONUS_BASIC'][payslip.id]['total']
        self.assertAlmostEqual(basic, 12000.0 * 10 / 12, places=2,
            msg="Only the 10 full months from January to October should count; "
                "November is dropped since the departure isn't on month-end.")

    def test_generate_thirteen_month_returns_existing_payslip(self):
        employee = self.create_employee({
            'name': '13th Month Idempotent',
            'wage': 12000.0,
            'contract_date_start': date(2020, 1, 1),
        })
        departure_date = date(2025, 11, 9)
        departure = self._create_departure(employee, departure_date, self.leaving_type_fired)
        employee.contract_date_end = departure_date

        first_payslip = departure._generate_termination_thirteen_month()
        second_payslip = departure._generate_termination_thirteen_month()

        self.assertEqual(first_payslip, second_payslip)
        self.assertEqual(
            self.env['hr.payslip'].search_count([
                ('employee_id', '=', employee.id),
                ('struct_id', '=', self.struct_thirteen_month.id),
            ]), 1)

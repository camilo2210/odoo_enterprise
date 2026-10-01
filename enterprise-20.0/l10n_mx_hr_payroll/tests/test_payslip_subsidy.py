# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.addons.hr_payroll.tests.common import TestPayrollBase
from odoo.tests.common import tagged
from odoo.tools import float_compare


@tagged("-at_install", "post_install_l10n", "post_install")
class TestPayslipSubsidy(TestPayrollBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mexico = cls.env.ref('base.mx')
        cls.env.company.country_id = mexico.id
        cls._setup_common(
            country=cls.env.ref("base.mx"),
            structure=cls.env.ref("l10n_mx_hr_payroll.l10n_mx_regular_pay"),
            structure_type=cls.env.ref("l10n_mx_hr_payroll.l10n_mx_employee"),
            resource_calendar=cls.env.ref("l10n_mx_hr_payroll.resource_calendar_def_48h"),
        )

    def _assert_subsidy_values(self, date_from, date_to, expected_current_month, expected_next_month=0.0):
        payslip = self._generate_payslip(date_from, date_to)
        payslip.action_validate()
        payslip_results = dict()
        if float_compare(expected_current_month, 0.0, 1) == 1:
            payslip_results['SUBSIDY_CURRENT_MONTH'] = expected_current_month
        if float_compare(expected_next_month, 0.0, 1) == 1:
            payslip_results['SUBSIDY_NEXT_MONTH'] = expected_next_month
        if payslip_results:
            payslip_results['SUBSIDY'] = expected_current_month + expected_next_month
        self._validate_payslip(payslip, payslip_results, skip_lines=True)

    def test_subsidy_bimonthly(self):
        self.employee.write({
            "schedule_pay": "bi-monthly",
            "wage": 22985.33,
        })
        self._assert_subsidy_values(date(2026, 5, 1), date(2026, 6, 30), 0.0)

        self.employee.wage = 22985.32
        self._assert_subsidy_values(date(2026, 5, 1), date(2026, 6, 30), 535.65, 535.65)

    def test_subsidy_monthly(self):
        self.employee.write({
            "schedule_pay": "monthly",
            "wage": 11492.67,
        })
        self._assert_subsidy_values(date(2026, 5, 1), date(2026, 5, 31), 0.0)

        self.employee.wage = 11492.66
        self._assert_subsidy_values(date(2026, 5, 1), date(2026, 5, 31), 535.65)

    def test_subsidy_biweekly(self):
        self.employee.write({
            "schedule_pay": "bi-weekly",
            "wage": 5670.73,
        })
        self._assert_subsidy_values(date(2026, 5, 1), date(2026, 5, 15), 0.0)

        self.employee.wage = 5670.72
        self._assert_subsidy_values(date(2026, 5, 1), date(2026, 5, 15), 267.82)

    def test_subsidy_14_days(self):
        self.employee.write({
            "schedule_pay": "14_days",
            "wage": 5292.68,
        })
        self._assert_subsidy_values(date(2026, 4, 29), date(2026, 5, 12), 0.0, 0.0)
        self._assert_subsidy_values(date(2026, 5, 13), date(2026, 5, 26), 0.0, 0.0)
        self._assert_subsidy_values(date(2026, 5, 27), date(2026, 6, 9), 0.0, 0.0)

        self.employee.wage = 5292.67
        self._assert_subsidy_values(date(2026, 4, 29), date(2026, 5, 12), 35.24, 211.44)
        self._assert_subsidy_values(date(2026, 5, 13), date(2026, 5, 26), 246.68)
        self._assert_subsidy_values(date(2026, 5, 27), date(2026, 6, 9), 77.53, 158.58)

    def test_subsidy_10_days(self):
        self.employee.write({
            "schedule_pay": "10_days",
            "wage": 3780.49,
        })
        self._assert_subsidy_values(date(2026, 4, 29), date(2026, 5, 8), 0.0, 0.0)
        self._assert_subsidy_values(date(2026, 5, 9), date(2026, 5, 18), 0.0, 0.0)
        self._assert_subsidy_values(date(2026, 5, 19), date(2026, 5, 28), 0.0, 0.0)
        self._assert_subsidy_values(date(2026, 5, 29), date(2026, 6, 7), 0.0, 0.0)

        self.employee.wage = 3780.48
        self._assert_subsidy_values(date(2026, 4, 29), date(2026, 5, 8), 35.24, 140.96)
        self._assert_subsidy_values(date(2026, 5, 9), date(2026, 5, 18), 176.20)
        self._assert_subsidy_values(date(2026, 5, 19), date(2026, 5, 28), 176.20)
        self._assert_subsidy_values(date(2026, 5, 29), date(2026, 6, 7), 42.29, 123.34)

    def test_subsidy_weekly(self):
        self.employee.write({
            "schedule_pay": "weekly",
            "wage": 2646.34,
        })
        self._assert_subsidy_values(date(2026, 4, 29), date(2026, 5, 5), 0.0, 0.0)
        self._assert_subsidy_values(date(2026, 5, 6), date(2026, 5, 12), 0.0, 0.0)
        self._assert_subsidy_values(date(2026, 5, 13), date(2026, 5, 19), 0.0, 0.0)
        self._assert_subsidy_values(date(2026, 5, 20), date(2026, 5, 26), 0.0, 0.0)
        self._assert_subsidy_values(date(2026, 5, 27), date(2026, 6, 2), 0.0, 0.0)

        self.employee.wage = 2646.33
        self._assert_subsidy_values(date(2026, 4, 29), date(2026, 5, 5), 35.24, 88.10)
        self._assert_subsidy_values(date(2026, 5, 6), date(2026, 5, 12), 123.34)
        self._assert_subsidy_values(date(2026, 5, 13), date(2026, 5, 19), 123.34)
        self._assert_subsidy_values(date(2026, 5, 20), date(2026, 5, 26), 123.34)
        self._assert_subsidy_values(date(2026, 5, 27), date(2026, 6, 2), 77.53, 35.24)

    def test_subsidy_across_years_bimonthly(self):
        self.employee.write({
            "schedule_pay": "bi-monthly",
            "wage": 20342.01,
        })
        self._assert_subsidy_values(date(2025, 12, 1), date(2026, 1, 31), 0.0, 536.22)

        self.employee.wage = 20342.0
        self._assert_subsidy_values(date(2025, 12, 1), date(2026, 1, 31), 474.65, 536.22)

    def test_subsidy_across_years_14_days(self):
        self.employee.write({
            "schedule_pay": "14_days",
            "wage": 4684.02,
        })
        self._assert_subsidy_values(date(2025, 12, 25), date(2026, 1, 7), 0.0, 123.47)

        self.employee.wage = 4684.01
        self._assert_subsidy_values(date(2025, 12, 25), date(2026, 1, 7), 109.29, 123.47)

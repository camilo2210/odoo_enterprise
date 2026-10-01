# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.addons.l10n_mx_hr_payroll_account.tests.test_salary_rules import TestPayslipValidation
from odoo.tests.common import tagged


@tagged("-at_install", "post_install_l10n", "post_install")
class TestPayslipSubsidyEdi(TestPayslipValidation):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee.write({
            "schedule_pay": "14_days",
            "wage": 5000.0,
        })

    def _assert_subsidy_warning(self, payslip, expected):
        warnings = payslip.issues.values()
        has_warning = any("Salary Limit for Employment Subsidy" in (w.get('message') or "") for w in warnings)

        if expected:
            self.assertTrue(has_warning, "Payslip should be flagged for Limit Salary Subsidy exceeded.")
        else:
            self.assertFalse(has_warning, "Payslip incorrectly flagged as Limit Salary Subsidy exceeded.")

    def test_subsidy_warning_exceeded_by_commissions(self):
        payslip_without_commission = self._generate_payslip(date(2026, 2, 1), date(2026, 2, 14))
        payslip_without_commission.action_validate()

        payslip = self._generate_payslip(date(2026, 2, 15), date(2026, 2, 28))
        self._assert_subsidy_warning(payslip, expected=False)

        payslip._set_input_value('COMMISSIONS', 2000.0)
        payslip.compute_sheet()
        self._assert_subsidy_warning(payslip, expected=True)

    def test_subsidy_warning_exceeded_by_wage_increase(self):
        self.version.contract_date_end = date(2026, 2, 14)
        self.version = self.employee.create_version({
            "date_version": date(2026, 2, 15),
            "contract_date_start": date(2026, 2, 15),
            "wage": 7000.0,
        })

        payslip_old = self._generate_payslip(date(2026, 2, 1), date(2026, 2, 14))
        payslip_old.action_validate()

        payslip = self._generate_payslip(date(2026, 2, 15), date(2026, 2, 28), version_id=self.version.id)
        payslip.compute_sheet()
        self._assert_subsidy_warning(payslip, expected=True)

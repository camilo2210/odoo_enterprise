from datetime import date

from odoo.addons.hr_payroll.tests.common import TestPayrollBase
from odoo.exceptions import ValidationError
from odoo.tests.common import tagged


@tagged("-at_install", "post_install_l10n", "post_install")
class TestPayslipIsr(TestPayrollBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.country_id = cls.env.ref('base.mx').id
        cls._setup_common(
            country=cls.env.ref("base.mx"),
            structure=cls.env.ref("l10n_mx_hr_payroll.l10n_mx_regular_pay"),
            structure_type=cls.env.ref("l10n_mx_hr_payroll.l10n_mx_employee"),
        )

    def _assert_isr(self, date_from, date_to, expected_isr):
        payslip = self._generate_payslip(date_from, date_to)
        payslip.action_validate()
        self._validate_payslip(payslip, {'ISR': expected_isr}, skip_lines=True)

    def test_isr_standard_method_is_the_default(self):
        self.assertEqual(self.env.company.l10n_mx_isr_calculation_method, 'standard')
        self.assertEqual(self.env.company.l10n_mx_isr_days_per_month, 30.4)

        self.employee.write({"schedule_pay": "bi-weekly", "wage": 10000.0})
        # Bi-weekly table: (10000.00 - 8651.41) * 21.36% + 916.20
        self._assert_isr(date(2026, 5, 1), date(2026, 5, 15), -1204.26)

        self.employee.write({"schedule_pay": "weekly", "wage": 3000.0})
        # Weekly table: (3000.00 - 2900.88) * 16.00% + 232.96
        self._assert_isr(date(2026, 5, 6), date(2026, 5, 12), -248.82)

    def test_isr_monthly_with_period_factor_biweekly(self):
        self.env.company.l10n_mx_isr_calculation_method = 'monthly_with_period_factor'
        self.employee.write({"schedule_pay": "bi-weekly", "wage": 10000.0})
        # Period factor: 30.4 / 15 = 2.026666...
        # Monthly taxable income: 10000.00 * 2.026666... = 20266.67
        # Monthly ISR: (20266.67 - 17533.65) * 21.36% + 1856.84 = 2440.613072
        # Bi-weekly ISR: 2440.613072 / 2.026666... = 1204.25
        self._assert_isr(date(2026, 5, 1), date(2026, 5, 15), -1204.25)

    def test_isr_monthly_with_period_factor_weekly(self):
        self.env.company.l10n_mx_isr_calculation_method = 'monthly_with_period_factor'
        self.employee.write({"schedule_pay": "weekly", "wage": 3000.0})
        # Period factor: 30.4 / 7 = 4.342857...
        # Monthly taxable income: 3000.00 * 4.342857... = 13028.57
        # Monthly ISR: (13028.57 - 12598.03) * 16.00% + 1011.68 = 1080.5664
        # Weekly ISR: 1080.5664 / 4.342857... = 248.81
        self._assert_isr(date(2026, 5, 6), date(2026, 5, 12), -248.81)

    def test_isr_monthly_with_period_factor_10_days(self):
        self.env.company.l10n_mx_isr_calculation_method = 'monthly_with_period_factor'
        self.employee.write({"schedule_pay": "10_days", "wage": 4000.0})
        # Period factor: 30.4 / 10 = 3.04
        # Monthly taxable income: 4000.00 * 3.04 = 12160.00
        # Monthly ISR: (12160.00 - 7168.52) * 10.88% + 420.95 = 964.023024
        # 10-days ISR: 964.023024 / 3.04 = 317.11
        self._assert_isr(date(2026, 5, 9), date(2026, 5, 18), -317.11)

    def test_isr_monthly_with_period_factor_custom_days_per_month(self):
        self.env.company.write({
            'l10n_mx_isr_calculation_method': 'monthly_with_period_factor',
            'l10n_mx_isr_days_per_month': 30.0,
        })
        self.employee.write({"schedule_pay": "bi-weekly", "wage": 10000.0})
        # Period factor: 30.0 / 15 = 2.0
        # Monthly ISR: (20000.00 - 17533.65) * 21.36% + 1856.84 = 2383.65236
        # Bi-weekly ISR: 2383.65236 / 2.0 = 1191.83
        self._assert_isr(date(2026, 5, 1), date(2026, 5, 15), -1191.83)

    def test_isr_days_per_month_must_be_positive(self):
        with self.assertRaises(ValidationError):
            self.env.company.l10n_mx_isr_days_per_month = 0.0

    def test_isr_monthly_with_period_factor_below_minimum_wage(self):
        """The minimum wage exemption still applies with the alternative method."""
        self.env.company.l10n_mx_isr_calculation_method = 'monthly_with_period_factor'
        # 2026 general zone daily minimum wage: 315.04
        self.employee.write({"schedule_pay": "weekly", "wage": 2000.0})
        payslip = self._generate_payslip(date(2026, 5, 6), date(2026, 5, 12))
        payslip.action_validate()
        self.assertEqual(payslip._get_line_values(['ISR'])['ISR'][payslip.id]['total'], 0.0)

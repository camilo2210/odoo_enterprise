# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
from datetime import date

from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon
from odoo.tests.common import tagged


@tagged('post_install', 'post_install_l10n', '-at_install', 'payslips_validation')
class TestSalaryRulesUzbekistan(TestPayslipValidationCommon):

    @classmethod
    @TestPayslipValidationCommon.setup_country('uz')
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_common(
            country=cls.env.ref('base.uz'),
            structure=cls.env.ref('l10n_uz_hr_payroll.l10n_uz_monthly_pay_structure'),
            structure_type=cls.env.ref('l10n_uz_hr_payroll.l10n_uz_employee_payroll_structure_type'),
            version_fields={
                'wage': 16000000.0,
            },
            resource_calendar=cls.env.ref('l10n_uz_hr_payroll.resource_calendar_def_40h'),
        )

        cls.env['account.chart.template']._configure_payroll_account_uz(cls.company)

        account_domain = [('company_ids', 'in', cls.company.id)]

        # Balance Sheet Accounts (Payables)
        cls.wages_payable = cls.env['account.account'].search([('code', '=', '6710')] + account_domain, limit=1)
        cls.taxes_payable = cls.env['account.account'].search([('code', '=', '6410')] + account_domain, limit=1)
        cls.pension_state_payable = cls.env['account.account'].search([('code', '=', '6520')] + account_domain, limit=1)
        cls.pension_inps_payable = cls.env['account.account'].search([('code', '=', '6530')] + account_domain, limit=1)
        cls.expense_claims_payable = cls.env['account.account'].search([('code', '=', '6970')] + account_domain, limit=1)

        # Profit & Loss Expense Accounts
        cls.salaries_expense = cls.env['account.account'].search([('code', '=', '9421')] + account_domain, limit=1)
        cls.leave_comp_expense = cls.env['account.account'].search([('code', '=', '9422')] + account_domain, limit=1)
        cls.social_tax_expense = cls.env['account.account'].search([('code', '=', '9423')] + account_domain, limit=1)
        cls.severance_expense = cls.env['account.account'].search([('code', '=', '9424')] + account_domain, limit=1)

    def test_basic_payslip_accounting_posting(self):
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip.action_payslip_done()

        move = payslip.move_id
        self.assertTrue(move, "A journal entry should be created upon payslip validation.")

        if move.state == 'draft':
            move.action_post()

        debit_by_account = defaultdict(float)
        credit_by_account = defaultdict(float)
        for line in move.line_ids:
            debit_by_account[line.account_id] += line.debit
            credit_by_account[line.account_id] += line.credit

        # Debits (Expenses & Deductions)
        self.assertAlmostEqual(debit_by_account[self.salaries_expense], 16000000.0, places=2)      # Basic Salary (9421)
        self.assertAlmostEqual(debit_by_account[self.social_tax_expense], 1920000.0, places=2)     # Social Tax Expense (9423)
        self.assertAlmostEqual(debit_by_account[self.taxes_payable], 16000.0, places=2)            # INPS Tax Deduction/Offset Debit on 6410

        # Credits (Liabilities)
        self.assertAlmostEqual(credit_by_account[self.wages_payable], 14080000.0, places=2)         # Net Salary (6710)
        self.assertAlmostEqual(credit_by_account[self.taxes_payable], 1920000.0, places=2)          # PIT Withholding Credit on 6410
        self.assertAlmostEqual(credit_by_account[self.pension_state_payable], 1920000.0, places=2)  # Social Tax Payable (6520)
        self.assertAlmostEqual(credit_by_account[self.pension_inps_payable], 16000.0, places=2)     # INPS Pension Payable (6530)

    def test_end_of_service_payslip_accounting_posting(self):
        departure_reason = self.env['hr.departure.reason'].create({
            'name': 'Test Departure With Severance',
            'l10n_uz_is_severance_paid': True,
        })

        self.env['hr.employee.departure'].create({
            'employee_id': self.employee.id,
            'dismissal_date': date(2024, 1, 16),
            'departure_reason_id': departure_reason.id,
            'departure_description': 'Test Departure',
        }).action_register()

        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip.action_payslip_done()

        move = payslip.move_id
        self.assertTrue(move, "A journal entry should be created for departure payslips.")

        if move.state == 'draft':
            move.action_post()

        debit_by_account = defaultdict(float)
        for line in move.line_ids:
            debit_by_account[line.account_id] += line.debit

        # Verify that severance pay is correctly debited to 9424 instead of 9420
        self.assertGreater(debit_by_account[self.severance_expense], 0.0)

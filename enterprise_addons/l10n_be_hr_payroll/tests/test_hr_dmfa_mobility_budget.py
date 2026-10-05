# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from dateutil.relativedelta import relativedelta

from odoo.tests import tagged

from odoo.addons.l10n_be_hr_payroll.models.hr_dmfa import DMFAOccupationInformation, format_amount
from .common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install', 'payroll_dmfa')
class TestHrDmfaMobilityBudget(TestPayrollCommon):

    def _compute_payslip(self, version, date_from, amount=None, input_code='MOBILITY_PAYMENT'):
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee_withholding_taxes.id,
            'version_id': version.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'date_from': date_from,
            'date_to': date_from + relativedelta(months=1, day=1, days=-1),
        })
        version.generate_work_entries(payslip.date_from, payslip.date_to)
        if amount is not None:
            payslip._set_input_value(input_code, amount)
        payslip.compute_sheet()
        return payslip

    def test_mobility_budget_declared_from_current_version(self):
        version = self.employee_withholding_taxes_contracts
        version.write({
            'l10n_be_mobility_budget': True,
            'l10n_be_mobility_budget_amount': 1234.56,
        })

        payslip = self._compute_payslip(version, date(2025, 12, 1), amount=543.21)

        occupation_info = DMFAOccupationInformation(payslip, ['mobility_budget'], quarter_start=date(2025, 10, 1))
        self.assertEqual(occupation_info.mobility_budget, format_amount(1234.56))

    def test_mobility_budget_falls_back_to_previous_quarter_version(self):
        previous_version = self.employee_withholding_taxes_contracts
        previous_version.write({
            'contract_date_end': date(2025, 12, 31),
            'l10n_be_mobility_budget': True,
            'l10n_be_mobility_budget_amount': 1234.56,
        })
        current_version = previous_version.copy({
            'date_version': date(2026, 1, 1),
            'contract_date_start': date(2026, 1, 1),
            'contract_date_end': False,
            'l10n_be_mobility_budget': False,
            'l10n_be_mobility_budget_amount': 0,
        })

        # The balance is paid on the new version (2026), which no longer carries a mobility
        # budget: the amount must be looked up from the previous version (which ended in Q4).
        payslip = self._compute_payslip(current_version, date(2026, 1, 1), amount=543.21, input_code='MOBILITY_PAYMENT_PREV_YEAR')

        occupation_info = DMFAOccupationInformation(payslip, ['mobility_budget'], quarter_start=date(2026, 1, 1))
        self.assertEqual(occupation_info.mobility_budget, format_amount(1234.56))

    def test_mobility_budget_not_declared_without_payment(self):
        version = self.employee_withholding_taxes_contracts
        payslip = self._compute_payslip(version, date(2025, 12, 1))

        occupation_info = DMFAOccupationInformation(payslip, [], quarter_start=date(2025, 10, 1))
        self.assertEqual(occupation_info.mobility_budget, -1, "No balance should be declared when nothing was paid")

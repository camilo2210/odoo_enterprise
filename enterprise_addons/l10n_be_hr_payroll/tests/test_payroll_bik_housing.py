# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from freezegun import freeze_time

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.l10n_be_hr_payroll.tests.common import TestPayrollCommon


@tagged('post_install', '-at_install', 'post_install_l10n')
class TestPayrollBIKHousing(TestPayrollCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with freeze_time('2026-01-20'):
            cls.housing_employee = cls.create_employee({
                'name': 'Housing Employee',
                'date_version': date(2025, 1, 1),
                'contract_date_start': date(2025, 1, 1),
                'contract_date_end': False,
                # A full month on that wage gives the 3142.64 gross of the specification
                'wage': 3142.64,
                'fuel_card': 0.0,
                'housing_onss_amount': 350.0,
                'housing_fiscal_amount': 200.0,
            })
            cls.housing_employee.version_id.generate_work_entries(date(2026, 1, 1), date(2026, 1, 31))

    def _get_line(self, payslip, code):
        return payslip.line_ids.filtered(lambda line: line.code == code)

    def _compute_payslip(self):
        with freeze_time('2026-01-20'):
            payslip = self.env['hr.payslip'].create({
                'name': 'Housing Payslip January 2026',
                'employee_id': self.housing_employee.id,
                'company_id': self.belgian_company.id,
                'version_id': self.housing_employee.version_id.id,
                'date_from': date(2026, 1, 1),
                'date_to': date(2026, 1, 31),
            })
            payslip.compute_sheet()
        return payslip

    def test_housing_benefit_split_between_onss_and_withholding(self):
        """
        Ensure that the housing benefit in kind raises the ONSS base with its ONSS amount
        and the withholding tax base with its fiscal amount, without mixing both.
        """
        payslip = self._compute_payslip()

        basic = self._get_line(payslip, 'BASIC').total
        onss = self._get_line(payslip, 'ONSS').total
        self.assertAlmostEqual(basic, 3142.64, 2, "The gross of the specification should be paid")

        # Only the ONSS amount is added to the gross the social contributions are computed on.
        self.assertAlmostEqual(
            self._get_line(payslip, 'SALARY').total, 3492.64, 2,
            "The housing amount for ONSS should be added to the gross submitted to ONSS"
        )
        self.assertAlmostEqual(
            onss, -456.49, 2,
            "The social contribution is due on the housing amount for ONSS"
        )

        # The taxable salary keeps the fiscal amount only, the ONSS one never entered that base.
        self.assertAlmostEqual(
            self._get_line(payslip, 'GROSS').total, 2886.15, 2,
            "Only the fiscal housing amount should be taxed"
        )
        self.assertAlmostEqual(
            self._get_line(payslip, 'ATN_HOUSING_ONSS_DED').total, -350.0, 2,
            "The ONSS housing amount should be given back right after the social contribution"
        )
        self.assertAlmostEqual(
            self._get_line(payslip, 'ATN_HOUSING_FISCAL_DED').total, -200.0, 2,
            "The fiscal housing amount should be given back right after the withholding tax"
        )
        self.assertFalse(
            self._get_line(payslip, 'ATN_DED'),
            "The housing benefit has its own lines, so no benefit in kind total is left to show"
        )

        # A benefit in kind is never paid out, so the net is the salary minus what is withheld on it.
        withheld = onss + self._get_line(payslip, 'P.P').total + self._get_line(payslip, 'M.ONSS').total
        self.assertAlmostEqual(
            self._get_line(payslip, 'NET').total, basic + withheld, 2,
            "The housing benefit should not be paid to the employee"
        )

    def test_housing_benefit_excluded_from_the_benefits_in_kind_total(self):
        """ Ensure that the benefits in kind total keeps the other benefits and drops the housing ones. """
        # Electricity is a plain monthly benefit in kind, so it is the only one the total should hold
        self.housing_employee.version_id.electricity_amount = 100.0
        payslip = self._compute_payslip()

        self.assertAlmostEqual(
            self._get_line(payslip, 'ATN_DED').total, -100.0, 2,
            "Only the electricity benefit should be in the benefits in kind total"
        )

    def test_housing_amounts_cannot_be_filled_alone(self):
        """ Ensure that filling one housing amount without the other is blocked. """
        with self.assertRaises(ValidationError, msg="A housing amount alone should be refused"):
            self.housing_employee.version_id.housing_fiscal_amount = 0.0

# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from dateutil.relativedelta import relativedelta
from freezegun import freeze_time

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install', 'payroll_arrear_salary')
class TestPayrollArrearSalary(TestPayrollCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with freeze_time('2025-01-01'):
            cls.arrear_employee = cls.create_employee({
                'name': 'Arrear Declaration Employee',
                'date_version': date(2024, 1, 1),
                'contract_date_start': date(2024, 1, 1),
                'contract_date_end': False,
                'wage': 2500.0,
                'niss': '/',
                'private_street': 'Rue du Test 1',
                'private_zip': '1000',
                'private_city': 'Brussels',
            })
            version = cls.arrear_employee.version_id
            structure = cls.env.ref(
                'l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary'
            )

            cls.arrear_regular_slips = cls.env['hr.payslip']
            for month in range(1, 4):
                date_from = date(2025, month, 1)
                date_to = date_from + relativedelta(months=1, day=1, days=-1)
                slip = cls.env['hr.payslip'].create({
                    'name': f'Payslip {month:02d}/2025 - Arrear Declaration',
                    'employee_id': cls.arrear_employee.id,
                    'struct_id': structure.id,
                    'version_id': version.id,
                    'date_from': date_from,
                    'date_to': date_to,
                })
                slip.compute_sheet()
                slip.action_payslip_done()
                cls.arrear_regular_slips |= slip

        with freeze_time('2026-04-15'):
            cls.arrear_slip = cls.env['hr.payslip'].create({
                'name': 'Arrear Salary Jul 2025 (paid Apr 2026)',
                'employee_id': cls.arrear_employee.id,
                'company_id': cls.arrear_employee.company_id.id,
                'version_id': cls.arrear_employee.version_id.id,
                'date_from': date(2025, 7, 1),
                'date_to': date(2025, 7, 31),
                'l10n_be_arrear_salary': True,
            })
            cls.arrear_slip.compute_sheet()
            cls.arrear_slip.action_payslip_done()

    def test_arrear_salary_validation_error_same_year(self):
        """
        Validation error is raised when l10n_be_arrear_salary is set to True on a
        payslip whose period is in the same calendar year as its creation date.
        """
        with freeze_time('2026-01-15'):
            employee = self.create_employee({
                'name': 'Arrear Validation Test Employee',
                'date_version': date(2025, 1, 1),
                'contract_date_start': date(2025, 1, 1),
                'contract_date_end': False,
            })
            payslip = self.env['hr.payslip'].create({
                'employee_id': employee.id,
                'company_id': employee.company_id.id,
                'version_id': employee.version_id.id,
                'date_from': date(2026, 1, 1),
                'date_to': date(2026, 1, 31),
            })
            with self.assertRaises(ValidationError):
                payslip.write({'l10n_be_arrear_salary': True})

    def test_arrear_salary_withholding_tax(self):
        """
        Arrear salary payslips must apply the dedicated P.P.ARREAR withholding-tax
        rule instead of the standard P.P rule.

        The tax amount must equal:
            P.P.ARREAR = -GROSS_arrear * (total_PPTOTAL_prior_year / total_GROSS_prior_year)

        """

        with freeze_time('2026-04-15'):

            line_values = self.arrear_slip._get_line_values(['P.P', 'P.P.ARREAR', 'GROSS'])
            pp_value = line_values['P.P'][self.arrear_slip.id]['total']
            pp_arrear_value = line_values['P.P.ARREAR'][self.arrear_slip.id]['total']
            gross_value = line_values['GROSS'][self.arrear_slip.id]['total']

            self.assertEqual(
                pp_value, 0.0,
                msg="P.P (regular withholding tax) must be 0 for an arrear salary payslip",
            )

            average_rate = self.arrear_slip._get_l10n_be_arrear_average_tax_rate()
            expected_pp_arrear = -gross_value * average_rate
            self.assertAlmostEqual(
                pp_arrear_value, expected_pp_arrear, 2,
                msg="P.P.ARREAR must equal -GROSS * (total_PPTOTAL_2025 / total_GROSS_2025)",
            )

    def test_arrear_salary_included_in_274_declaration(self):
        """
        An arrear payslip must be counted on the 274.XX sheet of the month in
        which it is paid (its done_date), regardless of its salary period.
        """
        with freeze_time('2026-04-20'):
            sheet = self.env['l10n_be.274_xx'].create({
                'year': 2026,
                'month': '4',
                'company_id': self.arrear_employee.company_id.id,
            })

            valid_payslips = sheet.with_context(
                wizard_274xx_force_employee_ids=self.arrear_employee.ids,
            )._get_valid_payslips()

            self.assertIn(
                self.arrear_slip, valid_payslips,
                "The arrear payslip paid in April 2026 must appear on the 274.XX sheet of April 2026",
            )

            arrear_values = self.arrear_slip._get_line_values(['GROSS', 'PPTOTAL'])
            arrear_gross = arrear_values['GROSS'][self.arrear_slip.id]['total']
            arrear_pp = arrear_values['PPTOTAL'][self.arrear_slip.id]['total']

            self.assertAlmostEqual(
                sheet.taxable_amount_10, arrear_gross, 2,
                msg="274.XX taxable amount must include the arrear GROSS paid this month",
            )
            self.assertAlmostEqual(
                sheet.pp_amount_10, arrear_pp, 2,
                msg="274.XX withholding tax amount must include the arrear PPTOTAL paid this month",
            )

    def test_arrear_salary_included_in_281_10_declaration(self):
        """
        On the 281.10 of the year in which the arrear payslip is paid, its
        GROSS must be reported under box 2064 (Arrears - f10_2064_afzbelachterstall)
        and must NOT be added to box 2060 (Ordinary remuneration -
        f10_2060_gewonebezoldiginge).

        Setup
        -----
        - 3 regular payslips validated in Jan-Mar 2025.
        - 1 arrear payslip (period Jul 2025) validated on 2026-04-15.
        - 281.10 generated for year 2026.

        Assertions
        ----------
        1. f10_2064_afzbelachterstall == arrear GROSS (in euro-cents).
        2. f10_2060_gewonebezoldiginge == 0 (no regular 2026 payslip exists).       """
        with freeze_time('2026-04-20'):
            declaration = self.env['l10n_be.281_xx'].create({
                'year': '2026',
                'company_id': self.arrear_employee.company_id.id,
            })
            report_281_10 = declaration.l10n_be_281_10_ids[:1]
            report_281_10.action_generate_declarations()
            self.assertIn(
                self.arrear_employee, report_281_10.line_ids.employee_id,
                "The employee with an arrear paid in 2026 must have a 281.10 line in 2026",
            )

            rendering_data = report_281_10.with_context(
                round_281=True,
            )._get_rendering_data(self.arrear_employee)
            employees_data = rendering_data['employees_data']
            self.assertEqual(len(employees_data), 1, "Exactly one employee sheet expected")
            sheet_values = employees_data[0]

            arrear_gross = self.arrear_slip._get_line_values(['GROSS'])['GROSS'][self.arrear_slip.id]['total']
            expected_arrear_eurocent = int(round(arrear_gross, 2) * 100)

            self.assertEqual(
                sheet_values['f10_2064_afzbelachterstall'], expected_arrear_eurocent,
                "Box 2064 must equal the arrear GROSS (in euro-cents)",
            )
            self.assertEqual(
                sheet_values['f10_2060_gewonebezoldiginge'], 0,
                "Box 2060 must NOT include the arrear GROSS (no regular 2026 payslip exists)",
            )

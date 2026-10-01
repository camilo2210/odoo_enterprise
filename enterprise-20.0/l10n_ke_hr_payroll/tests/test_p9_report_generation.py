# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged
from datetime import date, datetime


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestP9Report(TransactionCase):
    def setUp(self):
        # In setup, create Kenyan company, 2 Kenyan employees, 2 versions for them

        super().setUp()
        self.company_ke = self.env['res.company'].create({
            'name': 'KE Co',
            'country_id': self.env.ref('base.ke').id,
        })
        employees_vals = [
            {
                'name': 'KE Employee',
                'company_id': self.company_ke.id,
            },
            {
                'name': 'KE Employee 2',
                'company_id': self.company_ke.id,
            },
        ]
        self.employees_ke = self.env['hr.employee'].create(employees_vals)
        versions_vals = [
            {
                'name': 'Test Contract',
                'employee_id': self.employees_ke[0].id,
                'date_version': datetime(2026, 1, 1),
                'contract_date_start': datetime(2026, 1, 1),
                'contract_date_end': datetime(2026, 12, 31),
                'wage': 1000,
                'company_id': self.company_ke.id,
                'structure_type_id': self.env.ref('l10n_ke_hr_payroll.structure_type_employee_ken').id,
            },
            {
                'name': 'Test Contract 2',
                'employee_id': self.employees_ke[1].id,
                'date_version': datetime(2026, 1, 1),
                'contract_date_start': datetime(2026, 1, 1),
                'contract_date_end': datetime(2026, 12, 31),
                'wage': 1000,
                'company_id': self.company_ke.id,
                'structure_type_id': self.env.ref('l10n_ke_hr_payroll.structure_type_employee_ken').id,
            },
        ]
        self.versions = self.env['hr.version'].create(versions_vals)

    def test_ke_p9_report_generation(self):
        # First create payslips for our emloyees and validate them

        payslips_vals = [
            {
                'employee_id': self.employees_ke[0].id,
                'version_id': self.versions[0].id,
                'date_from': date(2026, 1, 1),
                'date_to': date(2026, 1, 31),
            },
            {
                'employee_id': self.employees_ke[1].id,
                'version_id': self.versions[1].id,
                'date_from': date(2026, 1, 1),
                'date_to': date(2026, 1, 31),
            },
        ]

        payslips = self.env['hr.payslip'].create(payslips_vals)

        payslips.compute_sheet()
        payslips.action_validate()

        self.assertEqual(len(payslips), 2)
        for payslip in payslips:
            self.assertEqual(payslip.state, 'validated')

        # Create tax deduction card (in P9 report tab) -> populate employees that have validated payslips by generating declarations
        l10n_ke_tax_deduction_card = self.env['l10n_ke.tax.deduction.card'].with_company(self.company_ke).create({'name': "Test Deduction 2026", 'year': 2026})
        l10n_ke_tax_deduction_card.action_generate_declarations()

        # Get all declarations and generate PDF for them
        all_declarations = self.env['hr.payroll.employee.declaration'].search([])
        for declaration in all_declarations:
            declaration.action_generate_pdf()

        self.env['hr.payslip'].with_company(self.company_ke)._cron_generate_pdf()

        # Check PDF's
        for declaration in all_declarations:
            self.assertTrue(declaration.pdf_filename)
            self.assertTrue(declaration.pdf_file)

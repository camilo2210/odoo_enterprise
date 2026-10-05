# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.tests import tagged
from .common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestTerminationDocumentsPayrun(TestPayrollCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.be_monthly_structure = cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary')
        cls.termination_structures = (
            cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_termination_fees')
            + cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_thirteen_month')
            + cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_departure_n_holidays')
        )

    def _create_departure(self, employee, departure_date):
        departure = self.env['hr.employee.departure'].create({
            'employee_id': employee.id,
            'dismissal_date': departure_date,
            'departure_reason_id': self.env.ref('hr.departure_fired').id,
            'l10n_be_notice_respect': 'without',
            'departure_description': 'Test',
        })
        departure.action_register()
        return departure

    def test_generate_payslips_in_payrun_creates_termination_documents_in_same_run(self):
        """ Generating the payslips of a monthly payrun that contains an employee's last
        payslip should generate the termination documents right away, in the same payrun,
        instead of waiting for that payslip to be validated. """
        employee = self.create_employee({
            'name': 'Termination On Payrun Creation',
            'wage': 3000.0,
            'contract_date_start': date(2020, 1, 1),
        })
        departure = self._create_departure(employee, date(2026, 6, 15))

        payrun = self.env['hr.payslip.run'].create({
            'name': 'June 2026',
            'date_start': date(2026, 6, 1),
            'date_end': date(2026, 6, 30),
            'company_id': self.belgian_company.id,
            'structure_id': self.be_monthly_structure.id,
            'version_ids': [(6, 0, employee.version_id.ids)],
        })
        payrun._generate_payslips()

        self.assertTrue(departure.l10n_be_termination_documents_generated,
            "The termination documents should be marked as generated once the payrun creates the last payslip.")

        generated_payslips = self.env['hr.payslip'].search([
            ('employee_id', '=', employee.id),
            ('struct_id', 'in', self.termination_structures.ids),
        ])
        self.assertEqual(len(generated_payslips), 3,
            "The termination fees, holiday attest and 13th month payslips should all be generated.")
        self.assertEqual(set(generated_payslips.payslip_run_id.ids), {payrun.id},
            "The generated termination documents should be added to the same payrun as the main payslip.")

        main_payslip = payrun.slip_ids - generated_payslips
        main_payslip.action_validate()

        self.assertEqual(
            self.env['hr.payslip'].search_count([
                ('employee_id', '=', employee.id),
                ('struct_id', 'in', self.termination_structures.ids),
            ]),
            len(generated_payslips),
            "Validating the main payslip afterwards should not regenerate or duplicate the termination documents.")

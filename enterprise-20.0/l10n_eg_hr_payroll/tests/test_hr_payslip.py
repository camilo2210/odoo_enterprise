# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.tests import tagged

from .common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestEgyptianHrPayslip(TestPayrollCommon):

    def test_errors_on_slip_required_field_not_found_eta_form2(self):
        self.employee_payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'struct_id': self.employee.structure_id.id,
            'date_from': date(2025, 5, 1),
            'date_to': date(2025, 5, 31),
        })
        self.employee.write({
            'passport_id': 'passport',
            'l10n_eg_ssn': '3213131',
            'job_id': self.env['hr.job'].create({
                'name': 'Developer',
            }),
        })
        self.employee_payslip._compute_issues()
        self.assertIn(self.employee._fields['identification_id'].string, self.employee_payslip.issues['0']['message'])
        self.assertIn('danger', self.employee_payslip.issues['0']['level'])
        self.employee.identification_id = 'id1221212no'
        self.employee_payslip._compute_issues()
        self.assertFalse(self.employee_payslip.issues)

    def test_warnings_on_slip_required_field_not_found_eta_form2(self):
        self.employee_payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'struct_id': self.employee.structure_id.id,
            'date_from': date(2025, 6, 1),
            'date_to': date(2025, 6, 30),
        })
        self.employee.identification_id = 'id1221212no'
        self.employee_payslip._compute_issues()
        for field in ['passport_id', 'l10n_eg_ssn', 'job_title']:
            self.assertIn(self.employee._fields[field].string, str(self.employee_payslip.issues))
        self.employee.write({
            'identification_id': 'eg112121',
            'passport_id': 'Passport',
            'l10n_eg_ssn': '3213131',
            'job_id': self.env['hr.job'].create({
                'name': 'Developer',
            }),
        })
        self.employee_payslip._compute_issues()
        self.assertFalse(self.employee_payslip.issues)

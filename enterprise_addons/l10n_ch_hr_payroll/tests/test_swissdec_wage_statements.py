# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestSwissdecWageStatements(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'Swiss Company',
            'country_id': cls.env.ref('base.ch').id,
        })
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=cls.company.ids))
        cls.hans, cls.ruth = cls.env['hr.employee'].create([{
            'name': 'Hans Muster',
            'registration_number': '12',
            'company_id': cls.company.id,
        }, {
            'name': 'Ruth Schmid',
            'registration_number': '13',
            'company_id': cls.company.id,
        }])
        cls.report = cls.env['ch.yearly.report'].create({'name': 'Yearly Declaration', 'company_id': cls.company.id})
        # The third person has no employee anymore (archived or deleted)
        cls.persons = [{'Particulars': {'EmployeeNumber': number}} for number in ('12', '13', '99')]

    def _patch_swissdec(self):
        self.requests = []
        declaration = {'SalaryDeclaration': {'Company': {'Staff': {'Person': self.persons}}}}

        def render_wage_statements(company, route, data, from_person=1, to_person=1, **kwargs):
            """ Mocks the Swissdec service: one PDF per person from from_person to to_person (excluded). """
            self.requests.append((from_person, to_person))
            persons = data['SalaryDeclaration']['Company']['Staff']['Person']
            return {'tax_accounting_reports': {
                f"tax_accounting_pers_{person['Particulars']['EmployeeNumber']}.pdf":
                    base64.b64encode(f"PDF {person['Particulars']['EmployeeNumber']} {len(self.requests)}".encode())
                for person in persons[from_person - 1:to_person - 1]
            }}

        return (
            patch.object(self.registry['ch.yearly.report'], '_get_declaration', lambda report: declaration),
            patch.object(self.registry['res.company'], '_l10n_ch_swissdec_request', render_wage_statements),
        )

    def _get_wage_statements(self):
        return self.env['hr.payroll.employee.declaration'].search([
            ('res_model', '=', self.report._name),
            ('res_id', '=', self.report.id),
        ])

    def _get_posted_pdf(self):
        self.report.invalidate_recordset(['message_ids'])
        attachment = self.report.message_ids[:1].attachment_ids
        self.assertEqual(len(attachment), 1, "The last message of the declaration should carry the wage statement")
        return attachment.name, attachment.raw.content

    def test_generate_single_wage_statement(self):
        patch_declaration, patch_request = self._patch_swissdec()
        with patch_declaration, patch_request:
            self.report.action_generate_wage_statement('13')
        self.assertEqual(self.requests, [(2, 3)], "Only the wage statement of the second person should be rendered")
        wage_statement = self._get_wage_statements()
        self.assertEqual(wage_statement.employee_id, self.ruth)
        self.assertEqual(wage_statement.pdf_file.content, b"PDF 13 1")
        self.assertEqual(self._get_posted_pdf(), (f"{wage_statement.pdf_filename}.pdf", b"PDF 13 1"))

        # Generating it again replaces the previous statement, and posts the new one
        with patch_declaration, patch_request:
            self.report.action_generate_wage_statement('13')
        self.assertEqual(self._get_wage_statements(), wage_statement)
        self.assertEqual(wage_statement.pdf_file.content, b"PDF 13 2")
        self.assertEqual(self._get_posted_pdf(), (f"{wage_statement.pdf_filename}.pdf", b"PDF 13 2"))

    def test_send_wage_statements_after_single_generation(self):
        patch_declaration, patch_request = self._patch_swissdec()
        with patch_declaration, patch_request:
            self.report.action_generate_wage_statement('12')
            self.report.send_tax_accounting_reports()
        wage_statements = self._get_wage_statements()
        self.assertEqual(wage_statements.employee_id, self.hans | self.ruth, "Each employee keeps a single wage statement")
        self.assertEqual(
            wage_statements.filtered(lambda s: s.employee_id == self.hans).pdf_file.content,
            b"PDF 12 2",
            "Sending the wage statements should replace the one generated before",
        )
        self.assertEqual(self.report.wage_statement_count, 2)
        self.assertIn(
            f"Tax_Accounting_Report_{self.report.year}_99.pdf",
            self.env['ir.attachment'].search([('res_model', '=', self.report._name), ('res_id', '=', self.report.id)]).mapped('name'),
            "The wage statement of a person without employee should be attached to the declaration",
        )

    def test_generate_wage_statement_without_employee(self):
        patch_declaration, patch_request = self._patch_swissdec()
        with patch_declaration, patch_request:
            self.report.action_generate_wage_statement('99')
        self.assertEqual(self.requests, [(3, 4)])
        self.assertFalse(self._get_wage_statements())
        self.assertEqual(self._get_posted_pdf(), (f"Tax_Accounting_Report_{self.report.year}_99.pdf", b"PDF 99 1"))

    def test_generate_wage_statement_unknown_person(self):
        patch_declaration, patch_request = self._patch_swissdec()
        with patch_declaration, patch_request, self.assertRaises(UserError):
            self.report.action_generate_wage_statement('42')
        self.assertFalse(self.requests)

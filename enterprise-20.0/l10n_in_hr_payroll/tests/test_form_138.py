# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.tests import tagged

from odoo.addons.l10n_in_hr_payroll.tests.common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestForm138(TestPayrollCommon):

    def setUp(self):
        super().setUp()
        employee_partner_state = self.env['res.country.state'].search([
            ('country_id.code', '=', 'IN'),
        ], limit=1)
        if not employee_partner_state:
            employee_partner_state = self.env['res.country.state'].create({
                'name': 'Tamil Nadu',
                'code': 'TN',
                'country_id': self.in_country.id,
            })

        self.jethalal_emp.write({
            'l10n_in_pan': 'ABCDE1234F',
            'work_email': 'employee@example.com',
            'work_phone': '9123456780',
            'private_email': 'employee.private@example.com',
            'private_phone': '9123456780',
            'private_street': '20 Payroll Street',
            'private_street2': 'Block A',
            'private_city': 'Chennai',
            'private_zip': '600002',
            'private_country_id': self.in_country.id,
            'private_state_id': employee_partner_state.id,
            'job_title': 'Payroll Manager',
        })

        self.company_in.partner_id.write({
            'street': '10 Industrial Area',
            'city': 'Chennai',
            'zip': '600001',
            'phone': '9876543210',
            'email': 'company@example.com',
            'country_id': self.in_country.id,
            'state_id': employee_partner_state.id,
        })
        self.company_in.write({
            'l10n_in_deductor_tan': 'ABCD12345E',
            'l10n_in_deductor_pan': 'ABCDE1234F',
            'l10n_in_deductor_type': 'K',
            'l10n_in_responsible_person_id': self.jethalal_emp.id,
        })

        self.version = self.jethalal_emp.create_version({
            'date_version': date(2025, 1, 1),
            'contract_date_start': date(2025, 1, 1),
            'contract_date_end': date(2026, 12, 31),
            'resource_calendar_id': self.env.company.resource_calendar_id.id,
            'wage': 200000.0,
            'structure_type_id': self.structure_type.id,
        })

        self.form_138 = self.env['l10n.in.payroll.form.138'].with_company(self.company_in).create({
            'company_id': self.company_in.id,
            'financial_year_start': '2026',
            'quarter': 'q1',
        })

    def test_form_138_generates_txt_file(self):
        payslip = self.env['hr.payslip'].with_company(self.company_in).create({
            'name': 'April 2026 Payslip',
            'employee_id': self.jethalal_emp.id,
            'version_id': self.version.id,
            'company_id': self.company_in.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 4, 1),
            'date_to': date(2026, 4, 30),
        })
        payslip.compute_sheet()
        payslip.action_payslip_done()
        payslip.action_payslip_paid()

        challan = self.env['l10n.in.tds.challan'].with_company(self.company_in).create({
            'company_id': self.company_in.id,
            'challan_date_from': date(2026, 4, 1),
            'challan_date_to': date(2026, 4, 30),
            'paid_date': date(2026, 4, 30),
            'challan_number': '12345',
            'bsr_code': '1234567',
            'minor_head': '200',
            'mode_of_payment': 'C',
            'interest': 0.0,
            'penalty': 0.0,
            'fee': 0.0,
        })
        challan.action_import_payslips(payslip.ids)
        self.assertEqual(challan.form_138_id, self.form_138)
        self.assertEqual(len(challan.challan_line_ids), 1)

        challan_line = challan.challan_line_ids[0]
        tds_total = payslip._get_line_values(['TDS'])['TDS'][payslip.id]['total']

        self.assertEqual(challan_line.payslip_id, payslip)
        self.assertEqual(challan_line.employee_id, self.jethalal_emp)
        self.assertAlmostEqual(challan_line.total_tds_paid, max(-tds_total, 0.0), places=2)
        self.assertAlmostEqual(challan.tds_amount, challan_line.total_tds_paid, places=2)
        self.assertAlmostEqual(challan.total_paid, challan.tds_amount, places=2)

        self.form_138.generate_138_txt_file()
        self.assertEqual(self.form_138.txt_filename, '202627Q1.txt')

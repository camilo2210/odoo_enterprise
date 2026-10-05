# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.addons.l10n_be_hr_payroll.tests.common import TestBelgiumCommon
from odoo.tests import tagged

from .test_payslip import TestPayslipBase


@tagged('post_install', '-at_install', 'third_party_transport')
class TestThirdPartyTransport(TestPayslipBase, TestBelgiumCommon):

    def setUp(self):
        super().setUp()
        # The employee starts a regular CP200 monthly contract at the start of the period.
        self.update_version(date(2024, 9, 1))
        self.monthly_struct = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary')

    def test_third_party_transport_lines(self):
        """ The subscription must produce a visible rule line and an equal negative deduction line. """
        payslip = self.create_payslip(self.monthly_struct, date(2024, 9, 1), date(2024, 9, 30))
        # The employer paid a 100 monthly bus subscription for the employee.
        payslip._set_input_value('TRANSPORT_3P', 100)
        payslip.compute_sheet()
        # The encoded amount is tracked by the rule and shown on the payslip PDF when non-zero.
        line_values = payslip._get_line_values(['TRANSPORT_3P', 'TRANSPORT_3P_DED'])
        self.assertEqual(line_values['TRANSPORT_3P'][payslip.id]['total'], 100, "Subscription rule should hold the 100 amount.")
        self.assertEqual(line_values['TRANSPORT_3P_DED'][payslip.id]['total'], -100, "Deduction should cancel the 100 added.")
        transport_line = payslip.line_ids.filtered(lambda l: l.code == 'TRANSPORT_3P')
        self.assertEqual(transport_line.appears_on_payslip, 'non_zero', "Subscription line must be visible on the payslip PDF.")

    def test_net_unchanged(self):
        """ Adding the subscription must not change the real net paid to the employee. """
        baseline = self.create_payslip(self.monthly_struct, date(2024, 9, 1), date(2024, 9, 30))
        baseline.compute_sheet()
        # Net computed without any third party transport input.
        baseline_net = baseline._get_line_values(['NET'])['NET'][baseline.id]['total']
        with_sub = self.create_payslip(self.monthly_struct, date(2024, 9, 1), date(2024, 9, 30))
        # Encode a 100 subscription that the employer paid directly.
        with_sub._set_input_value('TRANSPORT_3P', 100)
        with_sub.compute_sheet()
        # TRANSPORT_3P has no categories so it does not flow into NET, keeping pay neutral.
        with_sub_net = with_sub._get_line_values(['NET'])['NET'][with_sub.id]['total']
        self.assertEqual(with_sub_net, baseline_net, "Third party transport should be net neutral.")

    def test_no_input_no_lines(self):
        """ Without an encoded subscription neither line should be generated. """
        payslip = self.create_payslip(self.monthly_struct, date(2024, 9, 1), date(2024, 9, 30))
        payslip.compute_sheet()
        # No input means the input rule and its deduction do not produce any line.
        codes = payslip.line_ids.mapped('code')
        self.assertNotIn('TRANSPORT_3P', codes, "No subscription line without an encoded amount.")
        self.assertNotIn('TRANSPORT_3P_DED', codes, "No deduction line without an encoded amount.")

    def test_281_10_box_14a(self):
        """ The 281.10 box 14a (public transport) must include the third party paid subscription. """
        # The 281.10 generation requires a valid private address and NISS on the employee.
        self.employee.write({
            'niss': '/', 'l10n_be_legal_first_name': 'Test', 'l10n_be_legal_last_name': 'Employee',
            'private_street': 'Rue du Paradis 1', 'private_zip': '1000',
            'private_city': 'Brussels', 'private_country_id': self.env.ref('base.be').id,
        })
        # The 281.10 also requires that the company has street, zip, city, phone and VAT.
        self.env.company.write({
            'street': 'Rue du Paradis', 'zip': '6870', 'city': 'Eghezee', 'vat': 'BE0897223670', 'phone': '061928374',
        })
        payslip = self.create_payslip(self.monthly_struct, date(2024, 9, 1), date(2024, 9, 30))
        # Encode a 150 EUR subscription paid directly by the employer to the transit company.
        payslip._set_input_value('TRANSPORT_3P', 150)
        payslip.compute_sheet()
        # Only validated or paid payslips are included in the 281.10 declaration.
        self.employee.write({'review_state': '1_reviewed'})
        payslip.action_payslip_done()
        declaration = self.env['l10n_be.281_xx'].create({'year': '2024'})
        data = declaration.l10n_be_281_10_ids._get_rendering_data(self.employee)
        employee_data = data['employees_data'][0]
        # Box 14a must contain exactly the 150 EUR encoded subscription.
        self.assertAlmostEqual(
            employee_data['f10_2086_openbaargemeenschap'], 150.0, places=2,
            msg="Box 14a should reflect the 150 EUR third party transport subscription.",
        )

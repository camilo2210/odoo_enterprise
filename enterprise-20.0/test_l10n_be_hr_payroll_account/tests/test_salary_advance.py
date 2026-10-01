from datetime import date

from odoo.addons.l10n_be_hr_payroll.tests.common import TestBelgiumCommon
from odoo.tests import tagged

from .test_payslip import TestPayslipBase


@tagged('post_install', '-at_install', 'salary_advance')
class TestSalaryAdvance(TestPayslipBase, TestBelgiumCommon):

    def setUp(self):
        super().setUp()
        self.update_version(date(2024, 9, 1))
        self.saladv_struct = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_salary_advance')
        self.monthly_struct = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary')
        self.journal = self.env['account.journal'].create({
            'name' : 'MISC',
            'code' : 'MSC',
            'type' : 'general',
        })
        self.monthly_struct.journal_id = self.journal
        self.saladv_struct.journal_id = self.journal

    def test_salary_advance(self):
        self.payslip = self.create_payslip(self.saladv_struct, date(2024, 9, 1), date(2024, 9, 30))

        # First salary advance payslip of 500 on 01/09/2024
        george_saladv_payslip1 = self.create_payslip(self.saladv_struct, date(2024, 9, 1), date(2024, 9, 30))
        # Setting the advance amount to 500 and validate the payslip
        george_saladv_payslip1._set_input_value("SALARYADV", 500)
        george_saladv_payslip1.compute_sheet()
        george_saladv_payslip1.action_payslip_done()
        self.assertEqual(george_saladv_payslip1._get_line_values(['SALARYADV'])['SALARYADV'][george_saladv_payslip1.id]['total'], 500)

        # Second salary advance payslip of 200 on 15/09/2024
        george_saladv_payslip2 = self.create_payslip(self.saladv_struct, date(2024, 9, 15), date(2024, 9, 30))
        george_saladv_payslip2._set_input_value('SALARYADV', 200)
        george_saladv_payslip2.compute_sheet()
        george_saladv_payslip2.action_payslip_done()
        self.assertEqual(george_saladv_payslip2._get_line_values(['SALARYADV'])['SALARYADV'][george_saladv_payslip2.id]['total'], 200)

        # September monthly payslip
        george_payslip_sept = self.create_payslip(self.monthly_struct, date(2024, 9, 1), date(2024, 9, 30))
        george_payslip_sept.compute_sheet()
        # September monthly pay should have salary advance recovery = 700 by default
        amount_rec = george_payslip_sept._get_input_line_amount("SALARYADVREC")
        self.assertEqual(amount_rec, 700)
        # Changing the recovery amount to 500 and validate the payslip
        george_payslip_sept._set_input_value("SALARYADVREC", 500)
        george_payslip_sept.compute_sheet()
        george_payslip_sept.action_payslip_done()
        amount_rec = george_payslip_sept._get_input_line_amount("SALARYADVREC")
        self.assertEqual(amount_rec, 500)

        # Third salary advance payslip of 300 on 1/10/2024
        george_saladv_payslip3 = self.create_payslip(self.saladv_struct, date(2024, 10, 1), date(2024, 10, 31))
        george_saladv_payslip3._set_input_value('SALARYADV', 300)
        george_saladv_payslip3.compute_sheet()
        george_saladv_payslip3.action_payslip_done()

        # October monthly pay should have salary advance recovery = 500 (200+300) by default
        george_payslip_oct = self.create_payslip(self.monthly_struct, date(2024, 10, 1), date(2024, 10, 31))
        george_payslip_oct.compute_sheet()
        george_payslip_oct.action_payslip_done()
        amount_rec = george_payslip_oct._get_input_line_amount("SALARYADVREC")
        self.assertEqual(amount_rec, 500)

        # November monthly pay should have salary advance recovery = 0
        george_payslip_nov = self.create_payslip(self.monthly_struct, date(2024, 11, 1), date(2024, 11, 30))
        george_payslip_nov.compute_sheet()
        george_payslip_nov.action_payslip_done()
        amount_rec = george_payslip_nov._get_input_line_amount("SALARYADVREC")
        self.assertEqual(amount_rec, 0)

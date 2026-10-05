from datetime import date

from odoo.addons.l10n_in_hr_payroll.tests.common import TestPayrollCommon
from odoo.tests.common import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestPayslipFlow(TestPayrollCommon):

    def test_payslip_name(self):
        """
            This test checks that the name of the payslip contains the title provided in the `title` field or not.
        """
        payslip = self.env['hr.payslip'].create({
            'name': 'Jethalal',
            'employee_id': self.jethalal_emp.id,
            'version_id': self.contract_jethalal.id,
            'date_from': date(2023, 1, 1),
            'date_to': date(2023, 1, 31),
        })
        payslip.title = 'Test title'
        self.assertIn('Test title', payslip.name)

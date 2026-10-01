# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from odoo.tests import tagged

from odoo.addons.hr_payroll.tests.common import TestPayslipContractBase


@tagged('-at_install', 'post_install', 'salary')
class TestPayslipComputation(TestPayslipContractBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.contract_cdi.structure_type_id.country_id = cls.env.ref('base.be').id
        cls.contract_cdi.wage = 4000.33
        cls.richard_payslip = cls.env['hr.payslip'].create({
            'name': 'Payslip of Richard',
            'employee_id': cls.richard_emp.id,
            'version_id': cls.contract_cdi.id,
            'struct_id': cls.developer_pay_structure.id,
            'date_from': date(2016, 1, 1),
            'date_to': date(2016, 1, 31)
        })

    def test_worked_days_amount_with_unpaid(self):
        self.richard_payslip._compute_worked_days_line_ids()

        attendance_line = self.richard_payslip.worked_days_line_ids.filtered(lambda l: l.code == "002.00")
        self.assertAlmostEqual(attendance_line.amount, 4000.33, delta=0.01, msg="His attendance must be paid 4033.33")
        self.richard_payslip.version_id.wage = 3000.33
        attendance_line = self.richard_payslip.worked_days_line_ids.filtered(lambda l: l.code == "002.00")
        self.assertAlmostEqual(attendance_line.amount, 3000.33, delta=0.01, msg="His attendance must be paid 3033.33")

# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import ValidationError
from odoo.tests.common import tagged
from odoo.addons.hr_payroll.tests.common import TestPayslipBase


@tagged('at_install', '-post_install')
class TestSalaryRule(TestPayslipBase):

    def test_unique_code_constraint(self):
        self.env['hr.salary.rule'].create({
            'name': 'Test Performance Bonus',
            'sequence': 6,
            'amount_select': 'fix',
            'amount_fix': 500,
            'code': 'TESTPB',
            'category_ids': [(4, self.env.ref('hr_payroll.ALW').id)],
            'struct_ids': [(4, self.developer_pay_structure.id)],
        })
        with self.assertRaises(ValidationError):
            self.env['hr.salary.rule'].create({
                'name': 'Test Performance Bonus Copy',
                'sequence': 6,
                'amount_select': 'fix',
                'amount_fix': 500,
                'code': 'TESTPB',
                'category_ids': [(4, self.env.ref('hr_payroll.ALW').id)],
                'struct_ids': [(4, self.developer_pay_structure.id)],
            })

# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.addons.hr_payroll.tests.common import TestPayslipBase


@tagged('payslip_computation')
class TestPayslipAccessRights(TestPayslipBase):
    def test_payslip_access_officer(self):
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.richard_emp.id,
            'date_from': date(2018, 1, 1),
            'date_to': date(2018, 1, 31)
        })

        payslip.action_payslip_done()
        self.assertEqual(payslip.state, 'validated')

        payslip_run = self.env['hr.payslip.run'].create({
            'date_start': '2025-11-01',
            'date_end': '2025-11-30',
            'name': 'Payslip for Employee',
            'structure_id': self.developer_pay_structure.id,
        })
        payslip_run._generate_payslips()

        self.assertEqual(len(payslip_run.slip_ids), 1)
        payslip_run.action_validate()
        self.assertEqual(payslip_run.slip_ids[0].state, 'validated')

    def test_payslip_access_assistant(self):
        self.env.user.write({'group_ids': [
            Command.unlink(self.env.ref('hr_payroll.group_hr_payroll_officer').id),
            Command.link(self.env.ref('hr_payroll.group_hr_payroll_user').id),
        ]})

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.richard_emp.id,
            'date_from': date(2018, 1, 1),
            'date_to': date(2018, 1, 31)
        })

        self.assertEqual(payslip.state, 'draft')
        with self.assertRaisesRegex(ValidationError, "You do not have sufficient permissions to validate payslips."):
            payslip.action_payslip_done()

        payslip_run = self.env['hr.payslip.run'].create({
            'date_start': '2025-11-01',
            'date_end': '2025-11-30',
            'name': 'Payslip for Employee',
            'structure_id': self.developer_pay_structure.id,
        })
        payslip_run._generate_payslips()

        self.assertEqual(len(payslip_run.slip_ids), 1)
        with self.assertRaisesRegex(ValidationError, "You do not have sufficient permissions to validate payslips."):
            payslip_run.action_validate()

# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.addons.hr_payroll.tests.common import TestPayslipBase
from odoo.tests import tagged, HttpCase
from odoo.fields import Date

from datetime import date


@tagged('post_install', '-at_install')
class TestPayrunFlow(TestPayslipBase, HttpCase):

    def test_payrun_flow(self):

        # create a payrun where some pasylips have issues
        self.employee_amah = self.env['hr.employee'].create({
            'name': 'test amah',
            'country_id': self.env.ref('base.us').id,
            'date_version': Date.to_date('2025-01-01'),
            'contract_date_start': Date.to_date('2025-01-01'),
            'wage': 3000,
            'structure_type_id': self.structure_type.id,
        })
        payslip_run = self.env['hr.payslip.run'].create({
            'date_start': date(2026, 8, 1),
            'date_end': date(2026, 8, 31),
            'name': 'Test pay run',
            'structure_id': self.developer_pay_structure.id,
            'version_ids': [(4, self.employee_amah.version_id.id)],
        })
        payslip_run._generate_payslips()

        self.user_admin = self.env.ref('base.user_admin')
        self.user_admin.company_ids |= self.company_us
        self.user_admin.write({
            'company_id': self.env.company.id,
            'email': 'mitchell.admin@example.com',
        })
        # TODO why cr.flush() makes the test fail?

        self.start_tour("/odoo", 'payroll_payrun_tour', login="admin")

    def _setup_for_branch_company_selection(self, country_id):
        self.parent_company = self.env['res.company'].create({
            'name': 'Parent Company',
            'country_id': country_id,
        })
        self.branch_company = self.env['res.company'].create({
            'name': 'Branch Company',
            'country_id': country_id,
            'parent_id': self.parent_company.id,
        })
        self.env = self.env(context=dict(
            self.env.context,
            company_id=self.parent_company.id,
            allowed_company_ids=[self.parent_company.id, self.branch_company.id]
        ))
        self.structure_type = self.env['hr.payroll.structure.type'].create({
            'name': 'Test Structure Type',
        })
        self.developer_pay_structure = self.env['hr.payroll.structure'].create({
            'name': 'Test Salary Structure',
            'type_id': self.structure_type.id,
            'sequence': 1,
        })
        self.employee_faruk = self.env['hr.employee'].create({
            'name': 'test Faruk',
            'employee_type_id': self.env.ref('hr.contract_type_employee').id,
            'country_id': country_id,
            'company_id': self.branch_company.id,
            'date_version': Date.to_date('2026-01-01'),
            'contract_date_start': Date.to_date('2026-01-01'),
            'wage': 5000,
            'structure_type_id': self.structure_type.id,
        })
        self.user_admin = self.env.ref('base.user_admin')
        self.user_admin.company_ids |= self.parent_company | self.branch_company
        self.user_admin.write({
            'company_id': self.parent_company.id,
            'email': 'mitchell.admin@example.com',
        })

    def test_branch_company_selection_payrun(self):
        self._setup_for_branch_company_selection(self.env.ref('base.us').id)
        self.start_tour("/odoo", 'branch_company_selection_payrun_tour', login="admin")

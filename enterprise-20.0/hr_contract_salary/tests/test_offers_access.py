from odoo import Command
from odoo.tests.common import TransactionCase, tagged


@tagged('-at_install', 'post_install', 'salary')
class TestOffersAccess(TransactionCase):
    def test_salary_offer_access_rights(self):
        company = self.env.company
        hr_admin, payroll_user = self.env['res.users'].create([
            {
                'name': "HR Admin",
                'login': "hr_admin_access_check",
                'email': "hr_admin@example.com",
                'company_id': company.id,
                'company_ids': [Command.set([company.id])],
                'group_ids': [Command.set([
                    self.env.ref('base.group_user').id,
                    self.env.ref('hr.group_hr_manager').id,
                ])],
            },
            {
                'name': "Payroll Officer",
                'login': "payroll_user_access_check",
                'email': "payroll_user@example.com",
                'company_id': company.id,
                'company_ids': [Command.set([company.id])],
                'group_ids': [Command.set([
                    self.env.ref('base.group_user').id,
                    self.env.ref('hr_payroll.group_hr_payroll_user').id,
                ])],
            },
        ])

        salary_offer_model = self.env['hr.contract.salary.offer']

        self.assertFalse(salary_offer_model.with_user(hr_admin).has_access('read'))
        self.assertTrue(salary_offer_model.with_user(payroll_user).has_access('read'))

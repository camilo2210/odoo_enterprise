# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command
from odoo.addons.sign.tests.sign_request_common import SignRequestCommon
from odoo.tests.common import new_test_user, tagged


@tagged('post_install', '-at_install')
class TestSignDocumentEmail(SignRequestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.employee_user = new_test_user(
            cls.env,
            login='employee_sign_test',
            groups='base.group_user,sign.group_sign_user',
        )
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Test Employee',
            'work_email': 'work@test.com',
            'private_email': 'private@test.com',
            'work_contact_id': cls.employee_user.partner_id.id,
        })

    def fill_sign_request_wizard(self, mail_to):
        wizard = self.env['hr.contract.sign.document.wizard'].create({
            'employee_ids': [Command.set([self.employee.id])],
            'responsible_id': self.employee_user.id,
            'employee_role_id': self.role_signer_1.id,
            'sign_template_ids': [Command.set([self.template_1_role.id])],
            'mail_to': mail_to,
            'subject': 'Sign plz',
        })
        wizard.validate_signature()

    def test_employee_can_see_sign_request_sent_to_work_email(self):
        self.fill_sign_request_wizard(mail_to='work')
        items = self.env['sign.request.item'].with_user(self.employee_user).search([
            ('partner_id', '=', self.employee_user.partner_id.id),
        ])
        self.assertEqual(len(items), 1,
            "Employee should see the sign request sent to their work email.")
        self.assertEqual(items.signer_email, 'work@test.com',
            "Email should be sent to the employee's work email")

    def test_employee_can_see_sign_request_sent_to_private_email(self):
        self.fill_sign_request_wizard(mail_to='private')
        items = self.env['sign.request.item'].with_user(self.employee_user).search([
            ('partner_id', '=', self.employee_user.partner_id.id),
        ])
        self.assertEqual(len(items), 1,
            "Employee should see the sign request sent to their private email.")
        self.assertEqual(items.signer_email, 'private@test.com',
            "Email should be sent to the employee's private email")

    def test_employee_can_see_sign_request_sent_to_both_emails(self):
        self.fill_sign_request_wizard(mail_to='work')
        self.fill_sign_request_wizard(mail_to='private')
        items = self.env['sign.request.item'].with_user(self.employee_user).search([
            ('partner_id', '=', self.employee_user.partner_id.id),
        ])
        self.assertEqual(len(items), 2,
            "Employee should see both sign requests sent to their work and private emails.")

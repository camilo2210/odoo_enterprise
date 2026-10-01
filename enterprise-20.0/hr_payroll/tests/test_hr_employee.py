from odoo import tests
from odoo.addons.mail.tests.common import MailCase
from odoo.tests import new_test_user


@tests.tagged('post_install', '-at_install')
class TestHrEmployee(MailCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        departments = cls.env['hr.department'].create([
            {'name': 'Admin'},
            {'name': 'IT'},
        ])

        cls.dep_adm, cls.dep_it = departments

        cls.john_emp = cls.env['hr.employee'].create({
            'name': 'John',
            'wage': 2000,
            'department_id': cls.dep_adm.id
        })

        cls.non_payroll_user = new_test_user(
            cls.env,
            login='non_payroll_user',
            groups='base.group_user, hr.group_hr_manager',
            name='Non Payroll User',
        )

        cls.payroll_user = new_test_user(
            cls.env,
            login='payroll_user',
            groups='hr_payroll.group_hr_payroll_user',
            name='Payroll User',
        )

    def test_payroll_tracking_visibility(self):
        """Test that payroll-sensitive tracking messages are only visible
        to payroll users while non-sensitive tracking remains visible to all.
        """
        self.env = self.env(context={**self.env.context, 'lang': 'en_US'})
        payroll_subtype = self.env.ref('hr_payroll.mt_hr_payroll_sensitive')
        with self.mock_mail_app():
            self.john_emp.with_user(self.payroll_user).write({
                'wage': 3000,
                'department_id': self.dep_it.id,
            })
            self.flush_tracking()

        employee_msgs = self._new_msgs.filtered(
            lambda m: m.model == 'hr.employee'
        )
        # --- 1. check message content globally as sudo ---
        self.assertEqual(
            len(employee_msgs), 2,
            "Expected two tracking messages: one payroll-sensitive, one normal",
        )
        payroll_msg = employee_msgs.filtered(
            lambda m: m.subtype_id == payroll_subtype
        )
        normal_msg = employee_msgs - payroll_msg

        self.assertEqual(len(payroll_msg), 1, "Expected exactly one payroll message")
        self.assertEqual(len(normal_msg), 1, "Expected exactly one normal message")

        # check payroll message has correct subtype and tracking values
        self.assertMessageFields(payroll_msg, {
            'subtype_id': payroll_subtype,
            'model': 'hr.employee',
            'res_id': self.john_emp.id,
            'tracking_values': [
                ('wage', 'monetary', 2000, 3000, {'currency': self.env.ref('base.USD')}),
                ('final_yearly_costs', 'monetary', 24000, 36000, {'currency': self.env.ref('base.USD')}),
            ],
        })
        # check normal message has correct subtype and tracking values
        self.assertMessageFields(normal_msg, {
            'subtype_id': self.env.ref('mail.mt_note'),
            'model': 'hr.employee',
            'res_id': self.john_emp.id,
            'tracking_values': [
                ('department_id', 'many2one', self.dep_adm, self.dep_it),
            ],
        })
        # --- check access via _message_fetch (real chatter access) ---
        non_payroll_fetched = self.env['mail.message'].with_user(
            self.non_payroll_user
        )._message_fetch(domain=None, thread=self.john_emp)['messages']

        payroll_fetched = self.env['mail.message'].with_user(
            self.payroll_user
        )._message_fetch(domain=None, thread=self.john_emp)['messages']

        # payroll message hidden from non-payroll user in chatter
        self.assertNotIn(
            payroll_msg.id,
            non_payroll_fetched.ids,
            "Payroll message should not appear in non-payroll user chatter",
        )
        # payroll message visible to payroll user in chatter
        self.assertIn(
            payroll_msg.id,
            payroll_fetched.ids,
            "Payroll message should appear in payroll user chatter",
        )
        # normal message visible to both users in chatter
        self.assertIn(
            normal_msg.id,
            non_payroll_fetched.ids,
            "Normal message should appear in non-payroll user chatter",
        )
        self.assertIn(
            normal_msg.id,
            payroll_fetched.ids,
            "Normal message should appear in payroll user chatter",
        )

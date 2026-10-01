# Part of Odoo. See LICENSE file for full copyright and licensing details.

from contextlib import contextmanager

from odoo import Command
from odoo.addons.hr.tests.common import TestHrCommon
from odoo.addons.sign.tests.sign_request_common import SignRequestCommon
from odoo.tests import Form, tagged, users


@tagged('at_install', '-post_install')
class TestHrSignRequest(TestHrCommon, SignRequestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        employee_model = cls.env['ir.model']._get('hr.employee')

        cls.name_item_type = cls.env['sign.item.type'].create({
            'name': 'Employee Name',
            'item_type': 'text',
            'model_id': employee_model.id,
            'auto_field': 'name',
        })

        cls.env['sign.item'].create({
            'type_id': cls.name_item_type.id,
            'responsible_id': cls.role_signer_1.id,
            'required': True,
            'page': 1,
            'posX': 0.273,
            'posY': 0.158,
            'width': 0.150,
            'height': 0.015,
            'document_id': cls.document_2.id,
        })

    def _create_wizard(self, employee):
        return self.env['hr.contract.sign.document.wizard'].create({
            'employee_ids': [Command.set(employee.ids)],
            'sign_template_ids': [Command.set(self.template_1_role.ids)],
            'employee_role_id': self.role_signer_1.id,
            'signing_employee': 'hr_responsible',
            'responsible_id': self.env.user.id,
        })

    @contextmanager
    def _wizard_form(self, employee, signing_employee='hr_responsible'):
        wizard_form = Form(self.env['hr.contract.sign.document.wizard'])

        wizard_form.employee_ids.add(employee)
        wizard_form.sign_template_ids.add(self.template_1_role)
        wizard_form.signing_employee = signing_employee

        yield wizard_form

    @users('admin')
    def test_cc_partner_updated_based_on_signer(self):
        """
        Verify the CC recipients according to the selected signer.

          1. When the HR responsible is the signer, the employee is added
             to the CC recipients.

          2. When the employee is the signer, the employee is removed from
             the CC recipients because they are already the intended signer.
        """
        employee = self.employee

        with self._wizard_form(employee) as wizard:
            self.assertIn(employee.work_contact_id, wizard.cc_partner_ids, "Employee should be added to CC when HR responsible signs the document.")

        with self._wizard_form(employee, signing_employee='employee') as wizard:
            self.assertFalse(
                wizard.cc_partner_ids,
                "Employee should not be added to CC when the employee signs the document.",
            )

    @users('admin')
    def test_sign_now_employee_linked_field_autofilled(self):
        """
        When signing_employee = 'hr_responsible' and sign_now=True:
        the HR responsible signs the document immediately (Sign Now flow).

        1. sign.request.reference_doc must point to the employee - this is
            what Odoo Sign uses to resolve employee-linked auto-fill fields.

        2. The HR user (env.user) is the actual signer for sign_now, so
            request_item_ids.partner_id must be env.user.partner_id -
            confirming the HR responsible signs directly, ready to sign now.

        3. The employee must be in cc_partner_ids, since the HR responsible
            is the signer and the employee should stay informed.

        4. sign_now() must return an ir.actions.client action to open the
            document in signable mode, confirming the HR responsible is
            taken straight to signing rather than just creating the request.
        """
        employee = self.employee
        employee.work_email = 'employee@test.com'
        self.env.user.email = 'admin@test.com'

        wizard = self._create_wizard(employee)
        action = wizard.sign_now()
        self.assertEqual(
            action.get('tag'),
            'sign.SignableDocument',
            "sign_now() should return a client action to open the signable document.",
        )

        sign_requests = self.env['sign.request'].search([
            ('reference_doc', '=', f'{employee._name},{employee.id}'),
        ], limit=1)

        self.assertEqual(
            sign_requests.reference_doc,
            employee,
            "The sign request should reference the employee for resolving employee-linked auto-fill fields.",
        )
        self.assertEqual(
            sign_requests.request_item_ids.partner_id,
            self.env.user.partner_id,
            "The HR responsible should be the signer, ready to sign now.",
        )

    @users('admin')
    def test_sign_now_without_work_email(self):
        """
        Ensure that sign_now() warns about the missing work email instead of
        crashing when the employee has no email to send the request to.
        """
        employee = self.env['hr.employee'].create({'name': 'Employee Without Email'})

        action = self._create_wizard(employee).sign_now()
        self.assertEqual(
            action.get('tag'),
            'display_notification',
            "sign_now() should return a notification when the work email is missing.",
        )
        # Nothing may be created since the request could not be sent
        self.assertFalse(
            self.env['sign.request'].search_count([
                ('reference_doc', '=', f'{employee._name},{employee.id}'),
            ]),
            "No sign request should be created when the work email is missing.",
        )

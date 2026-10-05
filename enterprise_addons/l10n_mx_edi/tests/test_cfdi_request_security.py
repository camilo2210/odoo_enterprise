from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import tagged

from odoo.addons.l10n_mx_edi.tests.common_sat_download import (
    TestCfdiRequestCommon,
    DEFAULT_REQUEST_UUID,
)


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestCfdiRequestSecurity(TestCfdiRequestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.user_employee = cls.env['res.users'].create({
            'name': 'Employee No Accounting',
            'login': 'employee_sat_sec@example.com',
            'company_id': cls.env.company.id,
            'company_ids': [Command.set([cls.env.company.id])],
            'group_ids': [Command.set([cls.env.ref('base.group_user').id])],
        })

        cls.user_accountant = cls.env['res.users'].create({
            'name': 'Accountant SAT',
            'login': 'accountant_sat_sec@example.com',
            'company_id': cls.env.company.id,
            'company_ids': [Command.set([cls.env.company.id])],
            'group_ids': [Command.set([
                cls.env.ref('base.group_user').id,
                cls.env.ref('account.group_account_user').id,
            ])],
        })

        cls.user_readonly = cls.env['res.users'].create({
            'name': 'Readonly Accountant SAT',
            'login': 'readonly_sat_sec@example.com',
            'company_id': cls.env.company.id,
            'company_ids': [Command.set([cls.env.company.id])],
            'group_ids': [Command.set([
                cls.env.ref('base.group_user').id,
                cls.env.ref('account.group_account_readonly').id,
            ])],
        })

    def test_non_accountant_has_no_access(self):
        """A user without accounting rights can neither read nor process CFDI requests."""
        request = self._create_new_request()
        with self.assertRaises(AccessError):
            request.with_user(self.user_employee).read(['state'])
        with self.assertRaises(AccessError):
            request.with_user(self.user_employee).action_verify_request()

    def test_accountant_can_process_requests(self):
        """An accounting user can create/process requests."""
        request = self._create_new_request(
            state='in_download', package_uuid=f'{DEFAULT_REQUEST_UUID}_01',
        )
        with self.mx_external_setup(self.frozen_today, certificate=self.fiel_certificate), \
             self.mocked_send_cfdi_request(
                 self._build_package_download_response(package_zip=self.default_cfdi_package_raw)
             ):
            request.with_user(self.user_accountant).action_download_package()
            self.assertEqual(request.state, 'unpacking')
            request.with_user(self.user_accountant).action_unpack_package()

        self.assertEqual(request.state, 'done')
        self.assertTrue(request.l10n_mx_edi_document_ids)

    def test_readonly_cannot_retry(self):
        """A read-only accountant can read a request but cannot retry or write to it."""
        with self.mx_external_setup(self.frozen_today, certificate=self.fiel_certificate):
            request = self._create_new_request(state='rejected', is_retryable=False)
            self.assertTrue(request.with_user(self.user_readonly).read(['state']))
            with self.mocked_send_cfdi_request(self._build_request_download_response(request_type='batch_issued')):
                with self.assertRaises(AccessError):
                    request.with_user(self.user_readonly).action_retry_request()
        with self.assertRaises(AccessError):
            request.with_user(self.user_readonly).write({'is_retryable': True})

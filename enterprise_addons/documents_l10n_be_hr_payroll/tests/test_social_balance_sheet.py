# Part of Odoo. See LICENSE file for full copyright and licensing details.
from unittest.mock import patch

from odoo import Command
from odoo.addons.documents.models.documents_document import DocumentsDocument
from odoo.exceptions import AccessError
from odoo.tests import tagged, RecordCapturer
from odoo.tools import mute_logger

from odoo.addons.l10n_be_hr_payroll.tests.common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestDocumentsSocialBalanceSheet(TestPayrollCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employees_folder = cls.belgian_company.documents_employee_folder_id
        cls.payroll_manager, cls.payroll_user, cls.other_payroll_manager = payroll_users = cls.env['res.users'].create([{
            'name': "Payroll manager",
            'login': "be_payroll_manager",
            'company_id': cls.belgian_company.id,
            'company_ids': [Command.set(cls.belgian_company.ids)],
            'group_ids': [Command.link(cls.env.ref('hr_payroll.group_hr_payroll_manager').id)],
        }, {
            'name': "Payroll user",
            'login': "be_payroll_user",
            'company_id': cls.belgian_company.id,
            'company_ids': [Command.set(cls.belgian_company.ids)],
            'group_ids': [Command.link(cls.env.ref('hr_payroll.group_hr_payroll_user').id)],
        }, {
            # payroll manager of another company: the document is not for them either
            'name': "Payroll manager of another company",
            'login': "other_payroll_manager",
            'company_id': cls.env.ref('base.main_company').id,
            'company_ids': [Command.set(cls.env.ref('base.main_company').ids)],
            'group_ids': [Command.link(cls.env.ref('hr_payroll.group_hr_payroll_manager').id)],
        }])
        # The users are newer than the group of the company, created with the employees folder.
        cls.belgian_company.documents_hr_payroll_group_id.user_ids |= payroll_users

    @patch.object(DocumentsDocument, '_get_is_multipage', lambda __: False)
    def test_payroll_reports_documents_access(self):
        """Check that the company payroll reports are only shared with the payroll managers of the company."""
        for model, filename in (
            ('l10n.be.social.balance.sheet', "social_balance_sheet.pdf"),
            ('l10n.be.social.security.certificate', "social_security_certificate.pdf"),
        ):
            with self.subTest(model=model):
                wizard = self.env[model].with_company(self.belgian_company).create({})
                with RecordCapturer(self.env["documents.document"]) as capture:
                    wizard._post_process_generated_file(b"company payroll report", filename)
                document = capture.records
                self.assertEqual(len(document), 1, "The report document should have been created")
                self.assertEqual(document.folder_id, self.employees_folder)
                self.assertFalse(document.owner_id)

                # The access of the employees folder is neither inherited nor reachable through the link.
                self.assertTrue(self.employees_folder.access_ids.group_id, "The folder is shared with groups")
                self.assertFalse(document.access_ids.group_id, "The folder groups are not inherited")
                self.assertIn(self.payroll_manager.partner_id, document.access_ids.partner_id,
                              "The payroll managers of the company are members of the document")
                self.assertFalse(
                    document.access_ids.partner_id
                    & (self.payroll_user | self.other_payroll_manager).partner_id,
                    "Neither the payroll users nor the payroll managers of another company are members")
                self.assertEqual(set(document.access_ids.mapped('role')), {'edit'})
                self.assertEqual(document.access_internal, 'none')
                self.assertEqual(document.access_via_link, 'none')
                self.assertTrue(document.is_access_via_link_hidden)

                self.assertEqual(document.with_user(self.payroll_manager).user_permission, 'edit')
                # The payroll user manages the employees folder, but not the company report inside it.
                self.assertEqual(self.employees_folder.with_user(self.payroll_user).user_permission, 'edit')
                for user in (self.payroll_user, self.other_payroll_manager):
                    with mute_logger('odoo.addons.base.models.ir_access'), self.assertRaises(
                            AccessError, msg=f"{user.name} must not access {document.name}"):
                        document.with_user(user).mapped('name')

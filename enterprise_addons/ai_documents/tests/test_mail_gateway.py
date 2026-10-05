# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.mail.tests.common import MailCommon
from odoo.addons.test_mail.data.test_mail_data import MAIL_EML_ATTACHMENT
from odoo.tests import tagged

from odoo.addons.ai_documents.tests.test_common import TestAiDocumentsCommon


@tagged('at_install', '-post_install')  # LEGACY at_install
class TestMailGateway(TestAiDocumentsCommon, MailCommon):
    def test_ai_documents_send_mail(self):
        self.folder.alias_name = "inbox-test"

        documents = self.env["documents.document"].search([("folder_id", "=", self.folder.id)])
        self.assertFalse(documents)

        with self.mock_mail_gateway(), self.mock_completion_request([]) as mocked_request_llm:
            self.format_and_process(
                MAIL_EML_ATTACHMENT,
                "test@example.com",
                f"inbox-test@{self.alias_domain}",
                subject="Test document creation on incoming mail",
                target_model="documents.document",
                references="<f3b9f8f8-28fa-2543-cab2-7aa68f679ebb@odoo.com>",
                msg_id="<cb7eaf62-58dc-2017-148c-305d0c78892f@odoo.com>",
            )

        self.assertFalse(mocked_request_llm.called)
        documents = self.env["documents.document"].search([("folder_id", "=", self.folder.id)])
        self.assertEqual(len(documents), 2)
        self.assertTrue(all(documents.mapped("ai_to_sort")))

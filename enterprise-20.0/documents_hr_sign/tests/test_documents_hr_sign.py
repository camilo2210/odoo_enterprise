# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.documents_hr.tests.test_documents_hr_common import TransactionCaseDocumentsHr
from odoo.addons.sign.tests.sign_controller_common import TestSignControllerCommon
from odoo.tests.common import tagged


@tagged('test_document_bridge')
class TestDocumentsHrSign(TestSignControllerCommon, TransactionCaseDocumentsHr):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env['hr.employee'].create({
            'name': "Employee (related to doc_user)",
            'user_id': cls.doc_user.id,
            'work_contact_id': cls.doc_user.partner_id.id,
        })
        cls.signature_request_tag = cls.env.ref('documents_hr_sign.document_tag_signature_request')

    def _request_signature(self, record):
        """Request a signature on an employee or a version, as `hr.contract.sign.document.wizard`."""
        sign_request = self.create_sign_request_1_role(
            signer=self.employee.work_contact_id, cc_partners=self.env['res.partner'])
        record.sudo().sign_request_ids += sign_request
        return sign_request

    def _sign(self, sign_request):
        """Complete the signature through the (overridden) sign controller."""
        sign_request_item = sign_request.request_item_ids[0]
        response = self._json_url_open(
            '/sign/sign/%d/%s' % (sign_request.id, sign_request_item.access_token),
            data={'signature': self.single_signer_sign_values},
        ).json()['result']
        self.assertTrue(response.get('success'), "The document should have been signed")
        self.assertEqual(sign_request.state, 'signed')

    def _check_signed_document(self, record):
        """Check the document created for the signed request of the given employee / version."""
        document = self.env['documents.document'].search([
            ('res_model', '=', record._name), ('res_id', '=', record.id), ('type', '!=', 'folder')])
        self.assertEqual(len(document), 1, "The signed document should have been created once")
        self.assertEqual(document.folder_id, self.employee.hr_employee_folder_id,
                         "The signed document is filed in the employee folder")
        self.assertEqual(document.owner_id, self.employee.user_id)
        self.assertEqual(document.partner_id, self.employee.work_contact_id)
        self.assertIn(self.signature_request_tag, document.tag_ids)
        # The employee folder access is not inherited: a signed document is only for its owner.
        self.assertEqual(
            {(access.partner_id, access.group_id, access.role) for access in document.access_ids},
            {(self.employee.user_id.partner_id, self.env['res.group.functional'], False)},
            "Only the owner of the signed document has access to it")
        self.assertEqual(document.access_internal, 'none')
        self.assertEqual(document.access_via_link, 'view')
        self.assertEqual(document.with_user(self.employee.user_id).user_permission, 'edit',
                         "The owner of the signed document can manage it")

    def test_sign_request_on_employee(self):
        """Check creation and access of a signature requested from an employee."""
        self._sign(self._request_signature(self.employee))
        self._check_signed_document(self.employee)

    def test_sign_request_on_version(self):
        """Check creation and access of a signature requested from a version."""
        version = self.employee.version_id
        self._sign(self._request_signature(version))
        self._check_signed_document(version)

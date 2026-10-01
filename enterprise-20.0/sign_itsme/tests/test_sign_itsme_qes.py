# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from odoo.addons.sign.models.sign_request_item import QES_IAP_SERVICE_NAME
from odoo.addons.sign.tests.sign_request_common import SignRequestCommon


@tagged('post_install', '-at_install')
class TestSignItsmeQes(SignRequestCommon):
    """ What signing with itsme® adds to a role. The flow it takes part in belongs to sign,
    and the signatures themselves are made by the qualified signature host. """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.qes_role = cls.env['sign.item.role'].create({
            'name': 'itsme QES Role',
            'auth_method': 'itsme_qes',
        })

    def test_the_role_signs_the_documents_itself(self):
        self.assertTrue(
            self.qes_role.requires_external_signature,
            "a signer signing with itsme® seals the documents with a certificate of their own")

    def test_the_role_names_itsme_as_its_service(self):
        self.assertEqual(
            self.qes_role._get_external_signature_provider(), 'itsme',
            "Get external provider should tell the host what provider to use")

    def test_the_identity_method_signs_nothing_itself(self):
        identity_role = self.env['sign.item.role'].create({
            'name': 'itsme Identity Role',
            'auth_method': 'itsme',
        })
        self.assertFalse(identity_role.requires_external_signature)
        self.assertFalse(
            identity_role._get_external_signature_provider(),
            "checking who a signer is has nothing to do with producing their signature")

    def test_qualified_signatures_are_billed_to_their_own_service(self):
        self.assertEqual(
            self.qes_role._get_iap_service_name(), QES_IAP_SERVICE_NAME,
            "itsme® identity credits do not pay for a qualified signature")
        self.assertEqual(
            self.env['sign.item.role'].create({
                'name': 'itsme Identity Role',
                'auth_method': 'itsme',
            })._get_iap_service_name(), 'itsme_proxy')

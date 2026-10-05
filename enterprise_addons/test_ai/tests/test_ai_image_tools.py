# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged
from odoo.addons.base.tests.files import PNG_B64, PNG_RAW

from odoo.addons.ai.utils.ai_image_tools import retrieve_image_data_from_record


@tagged('post_install', '-at_install')
class TestAIImageTools(TransactionCase):
    def test_retrieve_image_data_from_record_access(self):
        """
        Test retrieval of data from a record field respects user access rights. Even
        if the user has access to the record, the access to the field is also checked
        """
        test_record = self.env['test.ai.image.generation'].create({
            'name': 'Test',
            'binary_field': PNG_B64,
        })
        restricted_user = self.env['res.users'].create({
            'name': 'Restricted User',
            'login': 'restricted_user',
        })
        restricted_record = test_record.with_user(restricted_user)
        # Assert that the restricted user has access to the record
        restricted_record.check_access('read')
        with self.assertRaises(AccessError):
            # The user doesn't have access to the binary field
            retrieve_image_data_from_record(restricted_record, 'binary_field')

        data = retrieve_image_data_from_record(test_record, 'binary_field')
        self.assertEqual(data['mimetype'], 'image/png')
        self.assertEqual(data['content'], PNG_RAW)

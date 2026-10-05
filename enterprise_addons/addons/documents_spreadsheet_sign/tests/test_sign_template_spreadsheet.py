# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.addons.sign.tests.sign_request_common import SignRequestCommon
from odoo.tests.common import new_test_user
from odoo import Command


@tagged('post_install', '-at_install')
class TestSignTemplateSpreadsheet(SignRequestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.sign_manager = new_test_user(
            cls.env,
            login="sign_manager",
            groups='sign.group_sign_manager'
        )

        cls.document_2b = cls.env['sign.document'].create({
            'attachment_id': cls.attachment.id,
            'template_id': cls.template_1_role.id,
            'name': 'Second Document',
        })

        cls.initial_item_doc2 = cls.env['sign.item'].create({
            'name': 'Initial Box Doc2',
            'type_id': cls.env.ref('sign.sign_item_type_initial').id,
            'required': True,
            'responsible_id': cls.role_signer_1.id,
            'page': 1,
            'posX': 0.1,
            'posY': 0.1,
            'document_id': cls.document_2.id,
            'width': 0.1,
            'height': 0.1,
        })

        cls.initial_item_doc2b = cls.env['sign.item'].create({
            'name': 'Initial Box Doc2b',
            'type_id': cls.env.ref('sign.sign_item_type_initial').id,
            'required': True,
            'responsible_id': cls.role_signer_1.id,
            'page': 1,
            'posX': 0.1,
            'posY': 0.2,
            'document_id': cls.document_2b.id,
            'width': 0.1,
            'height': 0.1,
        })

        cls.checkbox_item_doc2b = cls.env['sign.item'].create({
            'name': 'Checkbox',
            'type_id': cls.env.ref('sign.sign_item_type_checkbox').id,
            'required': True,
            'responsible_id': cls.role_signer_1.id,
            'page': 1,
            'posX': 0.2,
            'posY': 0.3,
            'document_id': cls.document_2b.id,
            'width': 0.1,
            'height': 0.1,
        })

    def test_open_spreadsheet_access_other_user(self):
        """Test that a regular user without access rights raises an AccessError."""
        template = self.template_1_role
        with self.assertRaises(AccessError):
            template.with_user(self.user_5).action_sign_template_open_linked_spreadsheet()

    def test_spreadsheet_access_request_separation(self):
        """ Test that Template Owner (User 2) cannot see Manager's private requests. """
        template = self.template_1_role
        template.user_id = self.user_2
        req = self.env['sign.request'].with_user(self.sign_manager).create({
            'template_id': self.template_1_role.id,
            'reference': self.template_1_role.display_name,
            'request_item_ids': [Command.create({
                'partner_id': self.partner_1.id,
                'role_id': self.role_signer_1.id,
            })],
        })
        req.sudo().write({
            'state': 'signed'
        })

        template.invalidate_recordset()
        template_as_manager = self.env['sign.template'].with_user(self.sign_manager).browse(template.id)
        table_mgr, _ = template_as_manager._compute_spreadsheet_table_for_doc()
        self.assertEqual(len(table_mgr[0]), 2, "Manager should see the request they created")

        template.invalidate_recordset()
        template_as_owner = self.env['sign.template'].with_user(self.user_2).browse(template.id)
        table_owner, _ = template_as_owner._compute_spreadsheet_table_for_doc()
        self.assertEqual(len(table_owner[0]), 1, "Owner should not see private request")

    def test_answers_folder_created(self):
        """The 'Sign Request Answers' folder should exist or be created."""
        template = self.template_1_role
        folder = template._get_sign_answers_folder_sudo()
        self.assertTrue(folder.exists())
        self.assertEqual(folder.name, 'Sign Request Answers')
        self.assertEqual(folder.type, 'folder')

    def test_compute_spreadsheet_table_only_signed_requests(self):
        """Only signed requests should appear in the spreadsheet table."""
        template = self.template_1_role
        self.create_sign_request_1_role(self.partner_1, cc_partners=self.partner_2)
        req_signed = self.env['sign.request'].search([('template_id', '=', template.id)], limit=1)
        self.populate_sign_request_with_dummy_values(req_signed)

        table_all, idxs = template._compute_spreadsheet_table_for_doc()
        self.assertEqual(len(table_all), 5, "Expected 5 columns for all documents combined: Timestamp, Signer, Initials x2, Text, Checkbox")
        # First column length = header + signed rows
        self.assertEqual(len(table_all[0]), 2)
        self.assertEqual(len(idxs), 1)

        table_doc2, idxs = template._compute_spreadsheet_table_for_doc(document_id=self.document_2.id)
        self.assertEqual(len(table_doc2), 4, "Expected 4 columns for document_2: Timestamp, Signer, Initials, Text")
        self.assertEqual(len(idxs), 0)

        table_doc2b, idxs = template._compute_spreadsheet_table_for_doc(document_id=self.document_2b.id)
        self.assertEqual(len(table_doc2b), 4, "Expected 4 columns for document_2b: Timestamp, Signer, Initials, Checkbox")
        self.assertEqual(len(idxs), 1)

    def test_compute_spreadsheet_table_specific_request_ids(self):
        """Test that only the provided sign request IDs are included in the spreadsheet table."""
        template = self.template_1_role

        req1 = self.create_sign_request_1_role(self.partner_1, cc_partners=self.partner_2)
        req2 = self.create_sign_request_1_role(self.partner_2, cc_partners=self.partner_1)

        self.populate_sign_request_with_dummy_values(req1)
        self.populate_sign_request_with_dummy_values(req2)

        table_filtered, idxs = template._compute_spreadsheet_table_for_doc(sign_requests=req1)
        self.assertEqual(len(table_filtered[0]), 2, "Table should include only 1 signed request row")
        self.assertEqual(len(idxs), 1)
        table_filtered2, idxs = template._compute_spreadsheet_table_for_doc(sign_requests=req2)
        self.assertEqual(len(table_filtered2[0]), 2, "Table should include only 1 signed request row")

        table_all, idxs = template._compute_spreadsheet_table_for_doc()
        self.assertEqual(len(table_all[0]), 3, "Table should include 2 signed request rows")
        self.assertEqual(len(idxs), 1)

    def test_value_formatting_types(self):
        template = self.template_1_role
        self.assertEqual(template._format_sign_value(self.checkbox_item_doc2b, "any_text"), "TRUE")
        self.assertEqual(template._format_sign_value(self.checkbox_item_doc2b, "on"), "TRUE")
        self.assertEqual(template._format_sign_value(self.checkbox_item_doc2b, "off"), "FALSE")
        self.assertEqual(template._format_sign_value(self.checkbox_item_doc2b, False), "FALSE")

    def test_spreadsheet_json_validation_rules(self):
        """
        Test that _build_spreadsheet_data generates the correct
        JSON structure with dataValidationRules.
        """
        template = self.template_1_role
        req = self.create_sign_request_1_role(self.partner_1, cc_partners=self.partner_2)
        self.populate_sign_request_with_dummy_values(req)

        spreadsheet_data = template._build_spreadsheet_data()

        sheet_doc2b = next(
            (s for s in spreadsheet_data['sheets'] if str(self.document_2b.id) in s['id']),
            None
        )
        self.assertIsNotNone(sheet_doc2b, "Sheet for Document 2b should exist")

        rules = sheet_doc2b.get('dataValidationRules', [])
        self.assertTrue(rules, "Document 2b (with checkbox) should have validation rules")

        rule = rules[0]
        self.assertEqual(rule['criterion']['type'], 'isBoolean', "Rule type must be isBoolean")
        self.assertTrue(rule['ranges'], "Rule must apply to a range")
        self.assertRegex(rule['ranges'][0], r"[A-Z]+\d+:[A-Z]+\d+")

# Part of Odoo. See LICENSE file for full copyright and licensing details.

from .sign_request_common import SignRequestCommon

from odoo.fields import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import tagged, new_test_user


@tagged('at_install', '-post_install')  # LEGACY at_install
class TestAccessRight(SignRequestCommon):

    def test_update_item_partner(self):
        self.role_signer_1.change_authorized = True
        sign_request_3_roles = self.create_sign_request_3_roles(signer_1=self.partner_1, signer_2=self.partner_2,
                                                                signer_3=self.partner_3, cc_partners=self.partner_4)
        role2sign_request_item = dict([(sign_request_item.role_id, sign_request_item) for sign_request_item in
                                       sign_request_3_roles.request_item_ids])
        sign_request_item_signer_1 = role2sign_request_item[self.role_signer_1]
        # We update the item partner with a non-privileged sign user.
        sign_request_item_signer_1.with_user(self.user_1).partner_id = self.partner_5
        # reassign
        self.assertEqual(sign_request_item_signer_1.signer_email, "char.aznable.a@example.com", 'email address should be char.aznable.a@example.com')

    def test_user_can_edit_only_own_templates_and_documents(self):
        """ Ensure basic sign users can only edit their own templates and documents. """
        res = self.env['sign.template'].with_user(self.user_1).create_from_attachment_data(
            attachment_data_list=[{'name': 'sample_contract.pdf', 'raw': self.pdf_value}]
        )
        user_1_template_id = res.get('id')
        user_1_template = self.env['sign.template'].with_user(self.user_1).browse(user_1_template_id)
        user_1_document = user_1_template.document_ids[0]
        with self.assertRaises(AccessError):
            user_1_template.with_user(self.user_2).write({'name': 'My New Name!'})
        with self.assertRaises(AccessError):
            user_1_document.with_user(self.user_2).write({'name': 'My New Name!'})

    def test_user_validation_sign_request(self):
        """ Ensure that user cannot link a sign request item with an existing sign request. """
        user_A = new_test_user(self.env, login="user_A", groups='sign.group_sign_user')
        partner_A = user_A.partner_id
        sign_request_A = self.create_sign_request_1_role(partner_A, partner_A)

        user_B = new_test_user(self.env, login="user_B", groups='sign.group_sign_user')
        partner_B = user_B.partner_id
        sign_request_B = self.create_sign_request_1_role(partner_B, partner_B)

        self.assertEqual(self.env['sign.request'].with_user(user_A).search([]), sign_request_A)
        self.assertEqual(self.env['sign.request'].with_user(user_B).search([]), sign_request_B)

        # If we "try to move" a ``sign.request.item`` on an existing ``sign.request`` a validation
        # error must be triggered because we must have the same number of ``sign.request.item`` on the
        # ``sign.request`` and on the ``sign.template`` linked to the ``sign.request``.
        # Thanks to the constraint ``_check_signers_validity``.

        # Test create validation
        with self.assertRaises(ValidationError):
            self.env['sign.request.item'].with_user(user_B).create({
                    'partner_id': partner_B.id,
                    'role_id': self.env.ref('sign.sign_item_role_default').id,
                    'sign_request_id': sign_request_A.id
            })

        # Test write validation
        with self.assertRaises(ValidationError):
            sign_request_B.request_item_ids.with_user(user_B).sign_request_id = sign_request_A

    def test_shared_custom_item_type_visibility(self):
        """ Test that shared custom sign item types are visible to all users. """
        test_user_2 = new_test_user(self.env, "test_user_2", email="u2@opoo.com", groups='sign.group_sign_user')
        shared_item = self.env['sign.item.type'].with_user(self.user_1).create({
            'name': 'Shared Field', 'item_type': 'text', 'shared': True,
        })
        user1_items = self.env['sign.item.type'].with_user(self.user_1).search([('id', '=', shared_item.id)])
        user2_items = self.env['sign.item.type'].with_user(test_user_2).search([('id', '=', shared_item.id)])
        self.assertTrue(user1_items, 'Creators should see their own shared item types.')
        self.assertTrue(user2_items, 'Other users should see shared item types.')

    def test_private_custom_item_type_visibility(self):
        """ Test that private custom sign item types are only visible to creator. """
        test_user_2 = new_test_user(self.env, "test_user_2", email="u2@opoo.com", groups='sign.group_sign_user')
        private_item = self.env['sign.item.type'].with_user(self.user_1).create({
            'name': 'Private Field', 'item_type': 'text', 'shared': False,
        })
        user1_items = self.env['sign.item.type'].with_user(self.user_1).search([('id', '=', private_item.id)])
        user2_items = self.env['sign.item.type'].with_user(test_user_2).search([('id', '=', private_item.id)])
        self.assertTrue(user1_items, 'Creators should see their private item types.')
        self.assertFalse(user2_items, 'Other users should not see private item types.')

    def test_authorized_user_added_but_cannot_write(self):
        """ Test that a user can be authorized for a custom item type but cannot edit it directly. """
        authorized_user = new_test_user(self.env, "test_user_2", email="u2@opoo.com", groups='sign.group_sign_user')
        custom_item_type = self.env['sign.item.type'].create({
            'name': 'custom Field', 'item_type': 'text', 'shared': True,
        })
        custom_item_type.with_user(authorized_user)._add_authorized_users(authorized_user)
        self.assertIn(authorized_user.id, custom_item_type.authorized_users.ids, "Authorized user should be added to authorized_users")
        with self.assertRaises(AccessError):
            # Non-creator should not be able to modify the custom item type directly.
            custom_item_type.with_user(authorized_user).write({'name': 'custom field'})

    def test_group_restricted_item_type_visibility(self):
        """Test that a non-shared custom item type with groups set in "Used by" is visible to
        users in those groups, but not to every sign user."""
        test_group = self.env['res.groups'].create({'name': 'Test Sign Group'})
        group_member = new_test_user(self.env, "group_member", email="member@example.com", groups='sign.group_sign_user')
        group_member.group_ids = [Command.link(test_group.id)]
        outsider = new_test_user(self.env, "outsider", email="outsider@example.com", groups='sign.group_sign_user')

        restricted_item = self.env['sign.item.type'].with_user(self.user_1).create({
            'name': 'Restricted Field', 'item_type': 'text', 'shared': False,
            'authorized_group_ids': [Command.link(test_group.id)],
        })

        member_items = self.env['sign.item.type'].with_user(group_member).search([('id', '=', restricted_item.id)])
        outsider_items = self.env['sign.item.type'].with_user(outsider).search([('id', '=', restricted_item.id)])
        creator_items = self.env['sign.item.type'].with_user(self.user_1).search([('id', '=', restricted_item.id)])

        self.assertTrue(member_items, 'Users in the authorized group should see the restricted item type.')
        self.assertFalse(outsider_items, 'Users outside the authorized group should not see the restricted item type.')
        self.assertTrue(creator_items, 'The creator should always see their own item type.')

    def test_get_sidebar_item_types_group_access_scoped_to_its_template(self):
        """Granting a group access to a template makes the group able to use a private field already placed on that template."""
        test_group = self.env['res.groups'].create({'name': 'Template Access Group'})
        group_member = new_test_user(self.env, "group_member", email="member@example.com", groups='sign.group_sign_user')
        group_member.group_ids = [Command.link(test_group.id)]

        res = self.env['sign.template'].with_user(self.user_1).create_from_attachment_data(
            attachment_data_list=[{'name': 'sidebar_test', 'raw': self.pdf_value}]
        )
        template = self.env['sign.template'].with_user(self.user_1).browse(res['id'])
        private_item = self.env['sign.item.type'].with_user(self.user_1).create({
            'name': 'Sidebar Test Field', 'item_type': 'text', 'shared': False,
        })
        self.env['sign.item'].with_user(self.user_1).create({
            'document_id': template.document_ids.id, 'type_id': private_item.id,
            'page': 1, 'posX': 0.1, 'posY': 0.1, 'width': 0.1, 'height': 0.1,
        })
        # Grant the group access to the template.
        template.with_user(self.user_1).write({'group_ids': [Command.link(test_group.id)]})

        template_results = self.env['sign.item.type'].with_user(group_member).get_sidebar_item_types(template.id)
        self.assertIn(private_item.id, [vals['id'] for vals in template_results],
            'A group granted access to the template should be able to use the field already placed on it.')

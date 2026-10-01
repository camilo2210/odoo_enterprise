from .common import TestMxEdiCommon
from odoo import Command
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestCFDIResPartner(TestMxEdiCommon):

    _test_user_groups = None  # FIXME list needed groups

    def test_duplicate_partner(self):
        user = self.env['res.users'].create({
            'name': 'New User',
            'login': 'new_user',
            'group_ids': [Command.set([self.env.ref('base.group_user').id, self.env.ref('base.group_partner_manager').id])],
        })
        # We want to be sure that the user have no access to acccounting
        self.assertFalse(user.has_group('account.group_account_invoice'))
        self.assertFalse(user.has_group('account.group_account_manager'))
        self.partner_mx.with_user(user).copy()

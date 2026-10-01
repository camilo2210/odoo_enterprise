# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestResPartnerBank(TransactionCase):

    def setUp(self):
        super().setUp()
        self.partner_hk = self.env['res.partner'].create({'name': 'Partner'})
        self.bank_account = self.env['res.partner.bank'].create({
            'account_number': '004-123456-789',
            'partner_id': self.partner_hk.id,
        })

    def test_01_hk_account_sanitization(self):
        self.bank_account._compute_sanitized_account_number()
        self.assertEqual(self.bank_account.sanitized_account_number, '004123456789')

    def test_02_hk_empty_account(self):
        self.bank_account.account_number = False

        # Run normally without failing.
        self.bank_account._compute_sanitized_account_number()
        self.assertFalse(self.bank_account.sanitized_account_number, "Sanitized number should be empty if account_number is False")

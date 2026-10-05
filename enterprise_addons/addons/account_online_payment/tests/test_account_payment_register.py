from odoo import Command, fields
from odoo.tests import Form, tagged
from odoo.addons.account_online_synchronization.tests.common import AccountOnlineSynchronizationCommon


@tagged('post_install', '-at_install')
class TestAccountOnlinePaymentBatch(AccountOnlineSynchronizationCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account_online_link.is_payment_enabled = True
        cls.account_online_link.is_payment_activated = True

        cls.partner_bank = cls.env['res.partner.bank'].create({
            'account_number': 'BE68539007547034',
            'account_type': 'iban',
            'allow_out_payment': True,
            'partner_id': cls.partner.id,
        })

        sepa_ct = cls.env.ref('account_iso20022.account_payment_method_sepa_ct')
        cls.sepa_method_line = cls.euro_bank_journal.outbound_payment_method_line_ids.filtered(
            lambda line: line.payment_method_id == sepa_ct,
        )[0]

    def test_no_partner_bank_id_in_payment_register(self):
        partner = self.env['res.partner'].create({'name': 'test'})
        move = self.env['account.move'].create({
            'partner_id': partner.id,
            'move_type': 'in_invoice',
            'invoice_date': fields.Date.today(),
            'currency_id': self.ref('base.EUR'),
            'invoice_line_ids': [
                Command.create({
                    'name': 'Product',
                    'price_unit': 1,
                    'quantity': 1,
                    'tax_ids': [],
                })
            ]
        })
        move.action_post()
        with Form.from_action(self.env, move.action_register_payment()) as wizard:
            self.assertFalse(wizard.could_initiate_payment)
            wizard.partner_bank_id = self.partner_bank
            self.assertTrue(wizard.could_initiate_payment)

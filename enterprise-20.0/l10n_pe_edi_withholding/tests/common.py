# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import Command

from odoo.addons.l10n_pe_edi.tests.common import TestPeEdiCommon


class TestPeEdiWithholdingCommon(TestPeEdiCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestPeEdiCommon.setup_country('pe')
    def setUpClass(cls):
        super().setUpClass()

        cls.maxDiff = None

        # Purchase journal with LATAM documents.
        cls.company_data['default_journal_purchase'].l10n_latam_use_documents = True

        # Purchase IGV tax (18%) for vendor bill lines.
        cls.purchase_tax_18 = cls.env['account.tax'].create({
            'name': 'IGV 18% Purchase',
            'amount_type': 'percent',
            'amount': 18,
            'l10n_pe_edi_tax_code': '1000',
            'l10n_pe_edi_unece_category': 'S',
            'type_tax_use': 'purchase',
            'tax_group_id': cls.tax_group.id,
        })

        cls.withholding_sequence = cls.env['ir.sequence'].create({
            'implementation': 'no_gap',
            'name': 'Test Withholding Sequence',
            'padding': 4,
            'number_increment': 1,
        })
        cls.withholding_tax = cls.env['account.tax'].search([
            ('amount', '=', -3),
            ('is_withholding_tax', '=', True),
            ('company_id', '=', cls.company_data['company'].id),
        ], limit=1)
        cls.withholding_tax.withholding_sequence_id = cls.withholding_sequence

        if not cls.company_data['company'].withholding_tax_base_account_id:
            cls.company_data['company'].withholding_tax_base_account_id = cls.env['account.account'].create({
                'code': 'WITHB',
                'name': 'Withholding Tax Base Account',
                'account_type': 'asset_current',
            })

    def setUp(self):
        super().setUp()
        self.bill_counter = 0

    def _create_vendor_bill(self, **kwargs):
        """Create and post a single vendor bill."""
        self.bill_counter += 1
        vals = {
            'move_type': 'in_invoice',
            'name': 'F FFI-%05d' % self.bill_counter,
            'partner_id': self.partner_a.id,
            'invoice_date': '2017-01-01',
            'date': '2017-01-01',
            'l10n_latam_document_type_id': self.env.ref('l10n_pe.document_type01').id,
            'invoice_line_ids': [Command.create({
                'product_id': self.product.id,
                'price_unit': 10000.0,
                'quantity': 1,
                'tax_ids': [Command.set((self.purchase_tax_18 | self.withholding_tax).ids)],
            })],
        }
        vals.update(kwargs)
        bill = self.env['account.move'].create(vals)
        bill.action_post()
        return bill

    def _create_payment_with_retention(self, bills=None, payment_amount=None, payment_currency=None):
        """Register a payment with 3% withholding on the given (or a new) vendor bill.

        When ``payment_amount`` is given, the wizard is partially paid for that
        amount (in the wizard's currency) so the withholding line is prorated.

        When ``payment_currency`` is given, the payment is made in that currency
        (allowing the bill currency and payment currency to differ).

        Returns the account.payment in 'paid' state with reconciled bills.
        """
        if bills is None:
            bills = self._create_vendor_bill()
        register_vals = {}
        if payment_currency is not None:
            register_vals['currency_id'] = payment_currency.id
        if len(bills) > 1:
            register_vals['group_payment'] = True
        if payment_amount is not None:
            register_vals['amount'] = payment_amount
        payment_register = self.env['account.payment.register']\
            .with_context(active_model='account.move', active_ids=bills.ids)\
            .create(register_vals)

        return payment_register._create_payments()

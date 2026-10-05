from odoo import Command
from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestPrintCheck(AccountTestInvoicingCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @AccountTestInvoicingCommon.setup_country('PH')
    def setUpClass(cls):
        super().setUpClass()

        cls.company_data['company'].account_check_printing_layout = 'l10n_ph_check_printing.action_print_check'

        bank_journal = cls.company_data['default_journal_bank']

        cls.payment_method_line_check = bank_journal.outbound_payment_method_line_ids\
            .filtered(lambda l: l.code == 'check_printing')

        cls.outstanding_account = cls.env['account.account'].create({
            'name': "Outstanding Payments",
            'code': 'OSTP420',
            'account_type': 'asset_current',
        })

        cls.partner_a.write({
            'vat': '123-456-789-001',
            'l10n_ph_branch_code': '001',
            'name': 'JMC Company',
            'street': "250 Amorsolo Street",
            'city': "Manila",
            'country_id': cls.env.ref('base.ph').id,
            'zip': "+900–1-096",
            'is_company': True,
        })

    def test_check_with_withholding_tax(self):
        withholding_tax = self.env['account.chart.template'].ref('l10n_ph_tax_purchase_10_wi011')
        withholding_tax.is_withholding_tax = True

        invoice = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner_a.id,
            'date': '2026-01-01',
            'invoice_date': '2026-01-01',
            'invoice_line_ids': [Command.create({
                'product_id': self.product_a.id,
                'price_unit': 3000.0,
                'tax_ids': [withholding_tax.id],
            })]
        })
        invoice.action_post()

        payment_register = self.env['account.payment.register'].with_context(
            lang='en_US',
            active_model='account.move',
            active_ids=invoice.ids,
        ).create({
            'payment_method_line_id': self.payment_method_line_check.id,
            'withholding_outstanding_account_id': self.outstanding_account.id,
        })

        payment_register.withholding_line_ids[0].name = "1"
        payment = payment_register._create_payments()
        check_page_info = payment._check_get_pages()[0]

        self.assertEqual(check_page_info['amount_no_currency'], "2,700.00")
        self.assertEqual(check_page_info['amount_in_word'], "Two Thousand Seven Hundred ONLY")

    def test_check_printing_only(self):
        """ Test that if the amount does not contain decimals,
            The amount in words on the check contains the keyword 'ONLY'
        """
        vendor_bill = self.init_invoice(
            move_type='in_invoice',
            partner=self.partner_a,
            amounts=[91490],
            post=True,
        )

        payment = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=vendor_bill.ids, lang='en_US'
        ).create({
            'payment_method_line_id': self.payment_method_line_check.id,
        })._create_payments()

        self.assertEqual(payment.check_amount_in_words, 'Ninety-One Thousand Four Hundred Ninety ONLY')

    def test_check_printing_rounding(self):
        """ Test that the amount in words on the check is rounded to 2 decimals,
            And does not contain the keyword 'ONLY'
         """
        vendor_bill = self.init_invoice(
            move_type='in_invoice',
            partner=self.partner_a,
            amounts=[91490.15],
            post=True,
        )

        payment = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=vendor_bill.ids, lang='en_US'
        ).create({
            'payment_method_line_id': self.payment_method_line_check.id,
        })._create_payments()

        self.assertEqual(payment.check_amount_in_words, 'Ninety-One Thousand Four Hundred Ninety and 15/100')

    def test_check_printing_rounding_two_decimals(self):
        """ Test that even with a different rounding factor,
            The amount in words on the check is still rounded to 2 decimals
        """
        self.env.ref('product.decimal_price').digits = 4
        self.env.company.currency_id.rounding = 0.0001

        vendor_bill = self.init_invoice(
            move_type='in_invoice',
            partner=self.partner_a,
            amounts=[91490.1579],
            post=True,
        )

        payment = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=vendor_bill.ids, lang='en_US'
        ).create({
            'payment_method_line_id': self.payment_method_line_check.id,
        })._create_payments()

        self.assertEqual(payment.check_amount_in_words, 'Ninety-One Thousand Four Hundred Ninety and 16/100')

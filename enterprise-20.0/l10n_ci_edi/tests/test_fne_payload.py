from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestCIEdiFNEPayload(AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country('ci')
    def setUpClass(cls):
        super().setUpClass()

        # Partners
        cls.partner_b2b = cls.env['res.partner'].create({
            'name': 'B2B Partner',
            'is_company': True,
            'country_id': cls.env.ref('base.ci').id,
            'vat': '1234567Z',
            'phone': '+225 0102030405',
            'email': 'b2b@example.com',
        })

        # Taxes
        ChartTemplate = cls.env['account.chart.template'].with_company(cls.company_data['company'])
        cls.tax_tva_18 = ChartTemplate.ref('tva_sale_18')
        cls.custom_tax = cls.env['account.tax'].create({
            'name': 'Custom Tax 5%',
            'amount_type': 'percent',
            'amount': 5.0,
            'type_tax_use': 'sale',
            'company_id': cls.company_data['company'].id,
        })

    def test_invoice_payload_generation(self):
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_b2b.id,
            'l10n_ci_edi_fne_payment_method': 'cash',
            'invoice_line_ids': [
                Command.create({
                    'product_id': self.product_a.id,
                    'quantity': 2.0,
                    'price_unit': 100.0,
                    'discount': 10.0,
                    'tax_ids': [Command.set(self.tax_tva_18.ids)],
                }),
                Command.create({
                    'product_id': self.product_b.id,
                    'quantity': 1.0,
                    'price_unit': 50.0,
                    'tax_ids': [Command.set((self.tax_tva_18 + self.custom_tax).ids)],
                })
            ],
        })

        payload = move._l10n_ci_edi_prepare_invoice_payload()

        self.assertEqual(payload['invoiceType'], 'sale')
        self.assertEqual(payload['paymentMethod'], 'cash')
        self.assertEqual(payload['template'], 'B2B')
        self.assertEqual(payload['clientNcc'], '1234567Z')
        self.assertEqual(payload['clientCompanyName'], 'B2B Partner')
        self.assertEqual(payload['discount'], 0.0)

        self.assertEqual(len(payload['items']), 2)
        item_1 = next(i for i in payload['items'] if i['description'] == 'product_a')
        self.assertEqual(item_1['quantity'], 2.0)
        self.assertEqual(item_1['amount'], 100.0)
        self.assertEqual(item_1['discount'], 10.0)
        self.assertIn('TVA', item_1['taxes'])
        self.assertEqual(item_1['customTaxes'], [])

        item_2 = next(i for i in payload['items'] if i['description'] == 'product_b')
        self.assertEqual(item_2['quantity'], 1.0)
        self.assertEqual(item_2['amount'], 50.0)
        self.assertEqual(item_2['discount'], 0.0)
        self.assertIn('TVA', item_2['taxes'])
        self.assertEqual(len(item_2['customTaxes']), 1)
        self.assertEqual(item_2['customTaxes'][0]['name'], 'Custom Tax 5%')

    def test_credit_note_payload(self):
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_b2b.id,
            'l10n_ci_edi_fne_payment_method': 'cash',
            'invoice_line_ids': [
                Command.create({'product_id': self.product_a.id, 'quantity': 2.0, 'price_unit': 100.0}),
            ],
        })
        invoice.action_post()
        # Simulate invoice sent and assigned an ID
        invoice.l10n_ci_edi_fne_invoice_id = 'FNE-ORIG-1'
        invoice._l10n_ci_edi_get_product_lines().l10n_ci_edi_fne_item_id = 'fne_item_123'

        credit_note = invoice._reverse_moves()

        self.assertEqual(credit_note.reversed_entry_id, invoice)
        payload = credit_note._l10n_ci_edi_prepare_credit_note_payload()
        self.assertEqual(len(payload['items']), 1)
        self.assertEqual(payload['items'][0]['id'], 'fne_item_123')
        self.assertEqual(payload['items'][0]['quantity'], 2.0)

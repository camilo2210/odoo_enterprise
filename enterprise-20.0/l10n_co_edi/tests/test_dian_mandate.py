from odoo.tests import tagged, freeze_time
from odoo.addons.l10n_co_edi.tests.common import TestCoEdiCommon


@freeze_time('2024-01-30')
@tagged('post_install_l10n', 'post_install', '-at_install')
class TestDianMandate(TestCoEdiCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner_mandate = cls.env['res.partner'].create({
            'name': "MANDATE PARTNER",
            'property_account_receivable_id': cls.company_data['default_account_receivable'].id,
            'property_account_payable_id': cls.company_data['default_account_payable'].id,
            'country_id': cls.env.ref('base.co').id,
            'vat': "2131234321",
        })

        cls.product_a.l10n_co_edi_mandate_contract = True

        cls.mandate_invoice = cls._create_invoice(
            partner_id=cls.partner_co.id,
            move_type='out_invoice',
            journal_id=cls.company_data['default_journal_sale'].id,
            invoice_line_ids=[
                cls._prepare_invoice_line(product_id=cls.product_a, price_unit=100),
                cls._prepare_invoice_line(product_id=cls.product_b, price_unit=100),
            ],
        )

        mandate_line = cls.mandate_invoice.invoice_line_ids.filtered(lambda line: line.product_id == cls.product_a)
        mandate_line.partner_id = cls.partner_mandate
        cls.mandate_invoice.l10n_co_edi_operation_type = '11'

        cls.mandate_invoice.action_post()

    def test_invoice_mandate(self):
        self.assertInvoiceValues(self.mandate_invoice, [
            {'product_id': self.product_b.id,   'tax_line_id': False,              'partner_id': self.partner_co.id},
            {'product_id': self.product_a.id,   'tax_line_id': False,              'partner_id': self.partner_mandate.id},
            {'product_id': False,               'tax_line_id': self.tax_sale_a.id, 'partner_id': self.partner_co.id},
            {'product_id': False,               'tax_line_id': self.tax_sale_a.id, 'partner_id': self.partner_mandate.id},  # tax line belonging to mandate partner
            {'product_id': False,               'tax_line_id': self.tax_sale_b.id, 'partner_id': self.partner_co.id},
            {'product_id': False,               'tax_line_id': False,              'partner_id': self.partner_co.id},
        ], {})

        xml = self.env['account.edi.xml.ubl_dian']._export_invoice(self.mandate_invoice)[0]
        self._assert_document_dian(xml, "l10n_co_edi/tests/attachments/invoice_mandate.xml")

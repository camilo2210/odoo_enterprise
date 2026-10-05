from odoo.addons.account.tests.common import AccountTestInvoicingCommon


class TestDoEdiCommon(AccountTestInvoicingCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @AccountTestInvoicingCommon.setup_country('do')
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.company_data['company']
        cls.company.write({
            'vat': '088390123',
            'street': 'Calle Test 123',
        })

        # Document types
        cls.doc_type_31 = cls.env.ref('l10n_do.ecf_31')
        cls.doc_type_32 = cls.env.ref('l10n_do.ecf_32')
        cls.doc_type_33 = cls.env.ref('l10n_do.ecf_33')
        cls.doc_type_34 = cls.env.ref('l10n_do.ecf_34')

        # Document type ranges
        cls.range_31 = cls.env['l10n_do_edi.document.type.range'].create({
            'start_number': 1,
            'end_number': 10000,
            'expiration_date': '2026-12-31',
            'company_id': cls.company.id,
        })
        cls.range_32 = cls.env['l10n_do_edi.document.type.range'].create({
            'start_number': 1,
            'end_number': 10000,
            'expiration_date': '2026-12-31',
            'company_id': cls.company.id,
        })
        cls.range_33 = cls.env['l10n_do_edi.document.type.range'].create({
            'start_number': 1,
            'end_number': 10000,
            'expiration_date': '2026-12-31',
            'company_id': cls.company.id,
        })
        cls.range_34 = cls.env['l10n_do_edi.document.type.range'].create({
            'start_number': 1,
            'end_number': 10000,
            'expiration_date': '2026-12-31',
            'company_id': cls.company.id,
        })

        # Link ranges to document types (company-dependent property field)
        cls.doc_type_31.with_company(cls.company).l10n_do_edi_property_document_range_id = cls.range_31
        cls.doc_type_32.with_company(cls.company).l10n_do_edi_property_document_range_id = cls.range_32
        cls.doc_type_33.with_company(cls.company).l10n_do_edi_property_document_range_id = cls.range_33
        cls.doc_type_34.with_company(cls.company).l10n_do_edi_property_document_range_id = cls.range_34

        # Journal
        cls.journal_sale = cls.company_data['default_journal_sale']
        cls.journal_sale.l10n_latam_use_documents = True

        cls.journal_purchase = cls.company_data['default_journal_purchase']

        # Partners
        cls.partner = cls.partner_a
        cls.partner.write({
            'vat': '101520787',
            'country_id': cls.env.ref('base.do').id,
        })

        cls.no_vat_partner = cls.env['res.partner'].create({
            'name': 'No VAT Partner',
            'country_id': cls.env.ref('base.do').id,
            'property_payment_term_id': cls.pay_terms_a.id,
            'street': 'Calle Principal 1',
            'city': 'Santo Domingo',
        })

        # a Cédula identifies the partner, but it is not the RNC a type 31 requires
        cls.cedula_partner = cls.env['res.partner'].create({
            'name': 'Cedula Partner',
            'additional_identifiers': {'DO_CEDULA': '00113918205'},
            'country_id': cls.env.ref('base.do').id,
            'property_payment_term_id': cls.pay_terms_a.id,
            'street': 'Calle Duarte 5',
            'city': 'Santiago',
        })

        cls.foreign_partner = cls.env['res.partner'].create({
            'name': 'US Foreign Partner',
            'vat': '123456789',
            'country_id': cls.env.ref('base.us').id,
            'property_payment_term_id': cls.pay_terms_a.id,
            'street': '123 Main St',
            'city': 'New York',
        })

        # Taxes (one per invoicing indicator)
        cls.tax_non_billable = cls.env['account.tax'].create({
            'name': 'TEST Non-billable',
            'amount': 0,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'l10n_do_edi_invoicing_indicator': '0',
            'company_id': cls.company.id,
        })

        cls.tax_18 = cls.company_data['default_tax_sale']
        cls.tax_18.write({
            'name': '18% ITBIS',
            'amount': 18,
            'l10n_do_edi_invoicing_indicator': '1',
        })

        cls.tax_16 = cls.env['account.tax'].create({
            'name': 'TEST 16% ITBIS',
            'amount': 16,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'l10n_do_edi_invoicing_indicator': '2',
            'company_id': cls.company.id,
        })

        cls.tax_0 = cls.env['account.tax'].create({
            'name': 'TEST 0% ITBIS',
            'amount': 0,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'l10n_do_edi_invoicing_indicator': '3',
            'company_id': cls.company.id,
        })

        cls.tax_exempt = cls.env['account.tax'].create({
            'name': 'TEST Exempt',
            'amount': 0,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'l10n_do_edi_invoicing_indicator': '4',
            'company_id': cls.company.id,
        })

        cls.tax_withholding_itbis = cls.env['account.tax'].create({
            'name': 'TEST -30% ITBIS',
            'amount': -30,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'l10n_do_edi_invoicing_indicator': '5',
            'invoice_label': 'TEST -30% ITBIS',
            'description': 'TEST -30% ITBIS',
            'company_id': cls.company.id,
        })

        cls.tax_withholding_isr = cls.env['account.tax'].create({
            'name': 'TEST -10% ISR',
            'amount': -10,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'l10n_do_edi_invoicing_indicator': '6',
            'invoice_label': 'TEST -10% ISR',
            'description': 'TEST -10% ISR',
            'company_id': cls.company.id,
        })

        cls.tax_additional = cls.env['account.tax'].create({
            'name': 'TEST 10% Additional',
            'amount': 10,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'l10n_do_edi_invoicing_indicator': '7',
            'l10n_do_edi_additional_tax_code': '001',
            'company_id': cls.company.id,
        })

        # Currency rate: 1 USD = 2 DOP
        cls.currency_usd = cls.env.ref('base.USD')
        cls.env['res.currency.rate'].create({
            'name': '2026-01-01',
            'currency_id': cls.currency_usd.id,
            'company_id': cls.company.id,
            'rate': 2.0,
        })

    def _create_invoice(self, doc_type=None, **kwargs):
        vals = {
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'journal_id': self.journal_sale.id,
            'invoice_date': '2026-01-15',
            'l10n_latam_document_type_id': (doc_type or self.doc_type_31).id,
            'l10n_do_edi_income_type': '01',
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product_a.id,
                'price_unit': 1000.0,
                'quantity': 1,
                'tax_ids': [(6, 0, self.tax_18.ids)],
            })],
            'company_id': self.company.id,
        }
        vals.update(kwargs)
        return self.env['account.move'].create(vals)

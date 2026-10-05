from freezegun import freeze_time
from unittest.mock import patch

from lxml import etree

from odoo import fields
from odoo.tests import Form, tagged
from odoo.tools import file_open
from .common import TestL10nClEdiCommon, _check_with_xsd_patch, _is_valid_certificate


@tagged('post_install_l10n', 'post_install', '-at_install', 'l10n_cl_fetchmail')
@patch('odoo.tools.xml_utils._check_with_xsd', _check_with_xsd_patch)
@patch('odoo.addons.certificate.models.certificate.CertificateCertificate._compute_is_valid', _is_valid_certificate)
class TestClFetchmailServer(TestL10nClEdiCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_data_2 = cls.setup_other_company()
        purchase_journal = cls.env['account.journal'].search([
            ('type', '=', 'purchase'),
            ('company_id', '=', cls.company_data['company'].id)
        ], limit=1)
        purchase_journal.write({'l10n_latam_use_documents': True})
        sale_journal = cls.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', cls.company_data['company'].id)
        ], limit=1)
        sale_journal.write({'l10n_cl_point_of_sale_type': 'online', 'l10n_latam_use_documents': True})

    def test_get_dte_recipient_company_incoming_supplier_document(self):
        # setting the secondary company as the dte recipient
        self.company_data['company'].vat = '22060449-7'
        self.company_data_2['company'].vat = '76201224-3'
        att_name = 'incoming_supplier_dte.xml'
        from_address = 'incoming_dte@test.com'
        with file_open(f'l10n_cl_edi/tests/fetchmail_dtes/{att_name}', 'rb') as f:
            content = f.read()
        file_data = {'name': att_name, 'raw': content, 'xml_tree': etree.fromstring(content)}
        origin_type = self.env['fetchmail.server']._get_xml_origin_type(file_data['xml_tree'])
        company = self.env['fetchmail.server']._get_dte_recipient_company(file_data['xml_tree'], origin_type)
        self.assertEqual(
            company,
            self.company_data_2['company'],
        )
        self.env['fetchmail.server']._process_incoming_supplier_document(file_data, from_address, company.id)

    def test_incoming_supplier_dte_52(self):
        """ Test that a DTE is well discarded when it is from a wrong type """
        att_name = 'incoming_supplier_dte_52.xml'
        from_address = 'incoming_dte@test.com'
        with file_open(f'l10n_cl_edi/tests/fetchmail_dtes/{att_name}', 'rb') as f:
            content = f.read()
        file_data = {'name': att_name, 'raw': content, 'xml_tree': etree.fromstring(content)}
        with patch('logging.Logger.info') as logger:
            self.env['fetchmail.server']._process_incoming_supplier_document(file_data, from_address, self.company_data['company'].id)
            logger.assert_any_call('DTE has been discarded! The document type %s is not a vendor bill', '52')

    def test_get_dte_recipient_company_incoming_sii_dte_result(self):
        with file_open('l10n_cl_edi/tests/fetchmail_dtes/incoming_sii_dte_result.xml', 'rb') as f:
            incoming_sii_dte_result = f.read()
        xml_content = etree.fromstring(incoming_sii_dte_result)
        self.assertEqual(
            self.env['fetchmail.server']._get_dte_recipient_company(xml_content, 'incoming_sii_dte_result'),
            self.company_data['company']
        )

    def test_get_dte_recipient_company_incoming_acknowledge(self):
        with file_open('l10n_cl_edi/tests/fetchmail_dtes/incoming_acknowledge.xml', 'rb') as f:
            incoming_acknowledge = f.read()
        xml_content = etree.fromstring(incoming_acknowledge)
        self.assertEqual(
            self.env['fetchmail.server']._get_dte_recipient_company(xml_content, 'incoming_acknowledge'),
            self.company_data['company']
        )

    def test_get_dte_recipient_company_incoming_commercial_accept(self):
        with file_open('l10n_cl_edi/tests/fetchmail_dtes/incoming_commercial_accept.xml', 'rb') as f:
            incoming_commercial_accept = f.read()
        xml_content = etree.fromstring(incoming_commercial_accept)
        self.assertEqual(
            self.env['fetchmail.server']._get_dte_recipient_company(xml_content, 'incoming_commercial_accept'),
            self.company_data['company']
        )

    def test_get_dte_recipient_company_incoming_commercial_reject(self):
        with file_open('l10n_cl_edi/tests/fetchmail_dtes/incoming_commercial_reject.xml', 'rb') as f:
            incoming_commercial_reject = f.read()
        xml_content = etree.fromstring(incoming_commercial_reject)
        self.assertEqual(
            self.env['fetchmail.server']._get_dte_recipient_company(xml_content, 'incoming_commercial_reject'),
            self.company_data['company']
        )

    @freeze_time('2019-11-23 18:00:00')
    def test_create_invoice_33_from_attachment(self):
        """DTE with unknown partner but known products"""
        att_name = 'incoming_invoice_33.xml'
        from_address = 'incoming_dte@test.com'
        with file_open(f'l10n_cl_edi/tests/fetchmail_dtes/{att_name}', 'rb', filter_ext=('.xml',)) as f:
            content = f.read()
            file_data = {'name': att_name, 'raw': content, 'xml_tree': etree.fromstring(content)}

        def create_move_from_document():
            moves = self.env['fetchmail.server']._process_incoming_supplier_document(
                file_data, from_address, self.company_data['company'].id
            )
            self.assertEqual(len(moves), 1)
            return moves[0]

        def get_expected_lines(product_non_billable_line_account):
            return [
                {
                    'product_id': self.product_a.id,
                    'tax_ids': self.company_data['default_tax_purchase'].ids,
                    'account_id': self.company_data['default_account_expense'].id,
                },
                {
                    'product_id': self.product_a.id,
                    'tax_ids': self.company_data['default_tax_purchase'].ids,
                    'account_id': self.company_data['default_account_expense'].id,
                },
                {
                    'product_id': product_non_billable_amounts.id,
                    'tax_ids': [],
                    'account_id': product_non_billable_line_account.id,
                },
            ]

        move = create_move_from_document()
        product_non_billable_amounts = self.env.ref('l10n_cl_edi.product_product_non_billable_amounts')

        self.assertEqual(move.name, 'FAC 000001')
        self.assertEqual(move.partner_id, self.env['res.partner'])
        self.assertEqual(move.date, fields.Date.from_string('2019-11-23'))
        self.assertEqual(move.invoice_date, fields.Date.from_string('2019-10-23'))
        self.assertEqual(move.invoice_date_due, fields.Date.from_string('2019-10-23'))
        self.assertEqual(move.journal_id.type, 'purchase')
        self.assertEqual(move.l10n_latam_document_number, '000001')
        self.assertEqual(move.l10n_cl_dte_acceptation_status, 'received')
        self.assertEqual(move.invoice_source_email, from_address)
        self.assertEqual(move.l10n_latam_document_type_id.code, '33')
        self.assertEqual(move.company_id, self.company_data['company'])
        # The expense account is set on the product (non billable amount)
        self.assertRecordValues(move.invoice_line_ids, get_expected_lines(product_non_billable_amounts.property_account_expense_id))
        self.assertEqual(move.currency_id.name, 'CLP')
        self.assertEqual(move.amount_total, 350390)
        self.assertEqual(move.amount_tax, 56104)

        # let's remove the expense account from the product
        product_non_billable_amounts.property_account_expense_id = False
        self.env.cr.cache.pop('account_product_accounts', None)
        move = create_move_from_document()

        # Now it should be the purchase journal default account
        self.assertRecordValues(move.invoice_line_ids, get_expected_lines(self.company_data['default_journal_purchase'].default_account_id))

    def test_create_invoice_work_without_default_latam_journal(self):
        """ Ensure no error when processing DTE XML without a 'use document' purchase journal """
        att_name = 'incoming_invoice_33.xml'
        from_address = 'incoming_dte@test.com'

        self.env['account.journal'].search([
            ('type', '=', 'purchase'),
            ('l10n_latam_use_documents', '=', True),
        ]).write({'l10n_latam_use_documents': False})
        with file_open(f'l10n_cl_edi/tests/fetchmail_dtes/{att_name}', 'rb', filter_ext=('.xml',)) as f:
            content = f.read()
            file_data = {'name': att_name, 'raw': content, 'xml_tree': etree.fromstring(content)}
        moves = self.env['fetchmail.server']._process_incoming_supplier_document(
            file_data, from_address, self.company_data['company'].id
        )

        self.assertEqual(len(moves), 1)
        move = moves[0]
        self.assertEqual(move.journal_id.type, 'purchase')
        self.assertEqual(move.journal_id.l10n_latam_use_documents, False)

    @freeze_time('2019-11-23')
    def test_duplicate_invoice_33_from_attachment(self):
        """DTE with known partner twice to trigger the "already exist" message."""

        partner_sii_same_company = self.env['res.partner'].create({
            'name': 'Other Partner SII Same Company',
            # Same company as the receiver on the XML
            'company_id': self.company_data['company'].id,
            # Same VAT as in the invoice XML
            'vat': '76086428-1',  # Invalid VAT works as there is no country_id
        })

        att_name = 'incoming_invoice_33.xml'
        from_address = 'incoming_dte@test.com'
        with file_open(f'l10n_cl_edi/tests/fetchmail_dtes/{att_name}', 'rb', filter_ext=('.xml',)) as f:
            content = f.read()
            file_data = {'name': att_name, 'raw': content, 'xml_tree': etree.fromstring(content)}
        move = self.env['fetchmail.server']._process_incoming_supplier_document(
            file_data, from_address, self.company_data['company'].id
        )
        self.assertEqual(move.partner_id, partner_sii_same_company)

        move_2 = self.env['fetchmail.server']._process_incoming_supplier_document(
            file_data, from_address, self.company_data['company'].id
        )
        self.assertFalse(move_2, "A duplicated invoice has been created")

    @freeze_time('2019-11-23 18:00:00')
    def test_create_invoice_33_from_attachment_with_exempt_lines(self):
        """DTE with lines exempted of taxes"""
        att_name = 'incoming_invoice_33_with_exempt_lines.xml'
        from_address = 'incoming_dte@test.com'
        with file_open(f'l10n_cl_edi/tests/fetchmail_dtes/{att_name}', 'rb', filter_ext=('.xml',)) as f:
            content = f.read()
            file_data = {'name': att_name, 'raw': content, 'xml_tree': etree.fromstring(content)}
        move = self.env['fetchmail.server']._process_incoming_supplier_document(
            file_data, from_address, self.company_data['company'].id
        )

        self.assertEqual(move.name, 'FAC 000001')
        self.assertEqual(len(move.invoice_line_ids), 4)
        self.assertEqual(move.currency_id.name, 'CLP')
        self.assertEqual(move.amount_total, 351340)
        self.assertEqual(move.amount_tax, 56104)

        line1 = move.invoice_line_ids[0]
        self.assertEqual(line1.price_unit, 2391)
        self.assertEqual(line1.price_subtotal, 2391 * 26)

        line2 = move.invoice_line_ids[1]
        self.assertEqual(line2.price_unit, 2914)
        self.assertEqual(line2.price_subtotal, 2914 * 80)

        line3 = move.invoice_line_ids[2]
        self.assertEqual(line3.quantity, 1)
        self.assertEqual(line3.price_unit, -150)
        self.assertEqual(line3.price_subtotal, -150)
        self.assertEqual(line3.discount, 0)

        line4 = move.invoice_line_ids[3]
        self.assertEqual(line4.quantity, 1)
        self.assertEqual(line4.price_unit, 100)
        self.assertEqual(line4.price_subtotal, 100)
        self.assertEqual(line4.discount, 0)

    @freeze_time('2019-11-23 18:00:00')
    def test_create_invoice_33_from_attachment_with_discounts(self):
        """DTE with discounts """
        att_name = 'incoming_invoice_33_with_discount.xml'
        from_address = 'incoming_dte@test.com'
        with file_open(f'l10n_cl_edi/tests/fetchmail_dtes/{att_name}', 'rb', filter_ext=('.xml',)) as f:
            content = f.read()
            file_data = {'name': att_name, 'raw': content, 'xml_tree': etree.fromstring(content)}
        moves = self.env['fetchmail.server']._process_incoming_supplier_document(
            file_data, from_address, self.company_data['company'].id)

        self.assertEqual(len(moves), 1)

        move = moves[0]
        self.assertEqual(move.name, 'FAC 002033')
        self.assertEqual(move.partner_id, self.env['res.partner'])
        self.assertEqual(move.date, fields.Date.from_string('2019-11-23'))
        self.assertEqual(move.invoice_date, fields.Date.from_string('2019-11-23'))
        self.assertEqual(move.invoice_date_due, fields.Date.from_string('2019-11-23'))
        self.assertEqual(move.journal_id.type, 'purchase')
        self.assertEqual(move.l10n_latam_document_number, '002033')
        self.assertEqual(move.l10n_cl_dte_acceptation_status, 'received')
        self.assertEqual(move.invoice_source_email, from_address)
        self.assertEqual(move.l10n_latam_document_type_id.code, '33')
        self.assertEqual(move.company_id, self.company_data['company'])
        self.assertEqual(len(move.invoice_line_ids), 2)
        self.assertEqual(move.invoice_line_ids[0].price_subtotal, 251146)
        self.assertEqual(move.invoice_line_ids[1].price_subtotal, 92054)
        self.assertEqual(move.currency_id.name, 'CLP')
        self.assertEqual(move.amount_untaxed, 343200)

    @freeze_time('2019-11-23 18:00:00')
    def test_create_invoice_33_from_attachment_with_discount_tax_incl(self):
        """DTE with discounts tax included"""
        att_name = 'incoming_invoice_33_with_discount_tax_incl.xml'
        with file_open(f'l10n_cl_edi/tests/fetchmail_dtes/{att_name}', 'rb', filter_ext=('.xml',)) as f:
            content = f.read()
            file_data = {'name': att_name, 'raw': content, 'xml_tree': etree.fromstring(content)}

        # Process the XML file
        moves = self.env['fetchmail.server']._process_incoming_supplier_document(
            file_data, 'incoming_dte@test.com', self.company_data['company'].id)

        # Retrieve the created invoice
        move = moves[0]

        # Check the invoice details
        self.assertEqual(move.name, 'FAC 002034')
        self.assertEqual(move.date, fields.Date.from_string('2019-11-23'))
        self.assertEqual(move.invoice_date, fields.Date.from_string('2019-11-23'))
        self.assertEqual(move.invoice_date_due, fields.Date.from_string('2019-11-23'))
        self.assertEqual(move.journal_id.type, 'purchase')
        self.assertEqual(move.move_type, 'in_invoice')
        self.assertEqual(move.l10n_latam_document_type_id.code, '33')
        self.assertEqual(move.l10n_latam_document_number, '002034')
        self.assertEqual(len(move.invoice_line_ids), 2)

        # Check the first invoice line
        line1 = move.invoice_line_ids[0]
        self.assertEqual(line1.product_id, self.product_a)
        self.assertEqual(line1.quantity, 1)
        self.assertEqual(line1.price_unit, 250894)
        self.assertEqual(line1.price_subtotal, 250894)
        self.assertEqual(line1.discount, 0)

        # Check the second invoice line
        line2 = move.invoice_line_ids[1]
        self.assertEqual(line2.product_id, self.product_b)
        self.assertEqual(line2.quantity, 2)
        self.assertEqual(line2.price_unit, 46011)
        self.assertEqual(line2.price_subtotal, 46011 * 2)
        self.assertEqual(line2.discount, 0)

        # Check the invoice status
        self.assertEqual(move.l10n_cl_dte_acceptation_status, 'received')

    def test_create_invoice_33_from_attachment_with_sending_partner_defined_on_other_company(self):
        """DTE with unknown partner for the receiving company, but known partner for
        another company. Make sure we don't match with a partner the company associated
        with the invoice can't access.
        """

        other_company_partner = self.env['res.partner'].create({
            'name': 'Other Partner SII Other Company',
            # Different company from the receiver on the XML (which is self.company_data['company'])
            'company_id': self.company_data_2['company'].id,
            # Same VAT as in the invoice XML
            'vat': '76086428-1',
        })

        att_name = 'incoming_invoice_33.xml'
        from_address = 'incoming_dte@test.com'
        with file_open(f'l10n_cl_edi/tests/fetchmail_dtes/{att_name}', 'rb', filter_ext=('.xml',)) as f:
            content = f.read()
            file_data = {'name': att_name, 'raw': content, 'xml_tree': etree.fromstring(content)}

        # Sudo to run like when OdooBot does the fetching. If we use a normal user,
        # `_get_invoice_form` will override `allowed_company_ids` in the context,
        # overriding anything we might set here. We want the user to be able to
        # access both company 1 (which is associated with the invoice) and company 2
        # (which is associated with the partner we just created) to trigger the
        # issue
        moves = self.env['fetchmail.server'].sudo()._process_incoming_supplier_document(
            file_data, from_address, self.company_data['company'].id)

        self.assertEqual(len(moves), 1)
        move = moves[0]
        # The existing partner is not valid, so it should not be assigned
        self.assertNotEqual(move.partner_id, other_company_partner)
        self.assertEqual(move.company_id, self.company_data['company'])

    def test_create_invoice_33_from_attachment_with_sending_partner_defined_on_two_companies(self):
        """DTE with known partner for the receiving company and another company.
        Make sure the one from the receiving company gets picked, because otherwise
        there will be an access rights issue where the user accessing the invoice won't
        be able to access the partner.
        """

        self.env['res.partner'].create({
            'name': 'Other Partner SII Other Company',
            # Different company from the receiver on the XML (which is self.company_data['company'])
            'company_id': self.company_data_2['company'].id,
            # Same VAT as in the invoice XML
            'vat': '76086428-1',  # Invalid VAT works as there is no country_id
        })

        partner_sii_same_company = self.env['res.partner'].create({
            'name': 'Other Partner SII Same Company',
            # Same company as the receiver on the XML
            'company_id': self.company_data['company'].id,
            # Same VAT as in the invoice XML
            'vat': '76086428-1',  # Invalid VAT works as there is no country_id
        })

        att_name = 'incoming_invoice_33.xml'
        from_address = 'incoming_dte@test.com'
        with file_open(f'l10n_cl_edi/tests/fetchmail_dtes/{att_name}', 'rb', filter_ext=('.xml',)) as f:
            content = f.read()
            file_data = {'name': att_name, 'raw': content, 'xml_tree': etree.fromstring(content)}

        # Sudo to run like when OdooBot does the fetching. If we use a normal user,
        # `_get_invoice_form` will override `allowed_company_ids` in the context,
        # overriding anything we might set here. We want the user to be able to
        # access both company 1 (which is associated with the invoice and
        # one of the partners we created) and company 2 (which is associated with
        # the other partner we created) to trigger the issue
        moves = self.env['fetchmail.server'].sudo()._process_incoming_supplier_document(
            file_data, from_address, self.company_data['company'].id
        )

        self.assertEqual(len(moves), 1)
        move = moves[0]
        self.assertEqual(move.partner_id, partner_sii_same_company)
        self.assertEqual(move.company_id, self.company_data['company'])

    def test_create_invoice_33_from_attachment_in_multi_company_setup(self):
        """DTE with unknown products in a multi-company setup. Make sure the default purchase tax
        is selected from the receiving company when we rely on the `account.chart.template`. This happens
        when the company doesn't have a default purchase tax explicitly set up by the user.
        """

        self.company_data_2['company'].account_purchase_tax_id = False
        self.company_data_2['company'].vat = self.company_data['company'].vat
        att_name = 'incoming_invoice_33.xml'
        from_address = 'incoming_dte@test.com'
        with file_open(f'l10n_cl_edi/tests/fetchmail_dtes/{att_name}', 'rb', filter_ext=('.xml',)) as f:
            content = f.read()
            file_data = {'name': att_name, 'raw': content, 'xml_tree': etree.fromstring(content)}

        # Sudo to run like when OdooBot does the fetching. If we use a normal user,
        # `_get_invoice_form` will override `allowed_company_ids` in the context,
        # overriding anything we might set here. We want the user to be able to
        # access both company 1 and company 2 to trigger the issue.
        moves = self.env['fetchmail.server'].sudo()._process_incoming_supplier_document(
            file_data, from_address, self.company_data_2['company'].id)

        self.assertEqual(len(moves), 1)
        move = moves[0]
        # The tax should belong to the receiving company.
        self.assertEqual(move.company_id, move.line_ids[0].tax_ids[0].company_id)

    def test_create_invoice_33_from_attachment_other_currency(self):
        """DTE with other currency """
        att_name = 'incoming_invoice_33_with_other_currency.xml'
        from_address = 'incoming_dte@test.com'
        with file_open(f'l10n_cl_edi/tests/fetchmail_dtes/{att_name}', 'rb', filter_ext=('.xml',)) as f:
            content = f.read()
            file_data = {'name': att_name, 'raw': content, 'xml_tree': etree.fromstring(content)}

        moves = self.env['fetchmail.server'].sudo()._process_incoming_supplier_document(
          file_data, from_address, self.company_data['company'].id)
        move = moves[0]
        self.assertEqual(move.amount_total, 119.0)
        self.assertEqual(move.currency_id, self.env.ref('l10n_cl.UF'))
        self.assertEqual(move.invoice_line_ids.price_unit, 100.0)
        self.assertEqual(move.invoice_line_ids.price_total, 119.0)

    def test_create_invoice_33_other_currency_no_header_total(self):
        """DTE with line-level Moneda but without the total MntTotOtrMnda"""
        att_name = 'incoming_invoice_33_other_currency_no_header_total.xml'
        from_address = 'incoming_dte@test.com'
        with file_open(f'l10n_cl_edi/tests/fetchmail_dtes/{att_name}', 'rb', filter_ext=('.xml',)) as f:
            content = f.read()
            file_data = {'name': att_name, 'raw': content, 'xml_tree': etree.fromstring(content)}

        move = self.env['fetchmail.server']._process_incoming_supplier_document(
            file_data, from_address, self.company_data['company'].id
        )
        self.assertEqual(move.currency_id, self.env.ref('l10n_cl.UF'))
        self.assertEqual(move.invoice_line_ids.price_unit, 100.0)
        self.assertEqual(move.amount_total, 119.0)

    def test_create_invoice_34_from_attachment(self):
        """Include Invoice Reference"""
        att_name = 'incoming_invoice_34.xml'
        from_address = 'incoming_dte@test.com'
        with file_open(f'l10n_cl_edi/tests/fetchmail_dtes/{att_name}', 'rb', filter_ext=('.xml',)) as f:
            content = f.read()
            file_data = {'name': att_name, 'raw': content, 'xml_tree': etree.fromstring(content)}
        moves = self.env['fetchmail.server']._process_incoming_supplier_document(
            file_data, from_address, self.company_data['company'].id
        )

        self.assertEqual(len(moves), 1)

        move = moves[0]
        self.assertEqual(move.name, 'FNA 000100')
        self.assertEqual(move.partner_id, self.partner_sii)
        self.assertEqual(move.journal_id.type, 'purchase')
        self.assertEqual(move.l10n_latam_document_number, '000100')
        self.assertEqual(move.l10n_cl_dte_acceptation_status, 'received')
        self.assertEqual(move.invoice_source_email, from_address)
        self.assertEqual(move.l10n_latam_document_type_id.code, '34')
        self.assertEqual(move.company_id, self.company_data['company'])
        self.assertEqual(len(move.invoice_line_ids), 2)
        self.assertEqual(move.currency_id.name, 'CLP')
        self.assertEqual(move.amount_total, 295286)
        self.assertEqual(move.amount_tax, 0)
        self.assertEqual(len(move.l10n_cl_reference_ids), 2)
        self.assertEqual(move.l10n_cl_reference_ids.mapped('origin_doc_number'), ['996327', 'A349010'])
        self.assertIn(
            '52', ' '.join(move.l10n_cl_reference_ids.l10n_cl_reference_doc_type_id.mapped('code')),
            'The reference code 52 is not present.')
        self.assertEqual(move.l10n_cl_reference_ids.mapped('reason'), ['Test', 'HHA: Test Hoja de horas hombre'])

    def test_create_invoice_33_with_holding_taxes_from_attachment(self):
        """Include Invoice Reference"""
        att_name = 'incoming_invoice_33_with_holding_taxes.xml'
        from_address = 'incoming_dte@test.com'
        with file_open(f'l10n_cl_edi/tests/fetchmail_dtes/{att_name}', 'rb', filter_ext=('.xml',)) as f:
            content = f.read()
            file_data = {'name': att_name, 'raw': content, 'xml_tree': etree.fromstring(content)}
        moves = self.env['fetchmail.server']._process_incoming_supplier_document(
            file_data, from_address, self.company_data['company'].id
        )

        self.assertEqual(len(moves), 1)

        move = moves[0]
        self.assertEqual(move.name, 'FAC 000001')
        self.assertEqual(move.partner_id, self.partner_sii)
        self.assertEqual(move.journal_id.type, 'purchase')
        self.assertEqual(move.l10n_latam_document_number, '000001')
        self.assertEqual(move.l10n_cl_dte_acceptation_status, 'received')
        self.assertEqual(move.invoice_source_email, from_address)
        self.assertEqual(move.l10n_latam_document_type_id.code, '33')
        self.assertEqual(move.company_id, self.company_data['company'])
        self.assertEqual(len(move.invoice_line_ids), 7)
        self.assertEqual(move.currency_id.name, 'CLP')
        self.assertEqual(move.amount_total, 231119)
        self.assertEqual(move.amount_tax, 63670)
        self.assertEqual(len(move.l10n_cl_reference_ids), 0)

    def test_create_invoice_34_unknown_product_from_attachment(self):
        att_name = 'incoming_invoice_34_unknown_product.xml'
        from_address = 'incoming_dte@test.com'
        with file_open(f'l10n_cl_edi/tests/fetchmail_dtes/{att_name}', 'rb', filter_ext=('.xml',)) as f:
            content = f.read()
            file_data = {'name': att_name, 'raw': content, 'xml_tree': etree.fromstring(content)}
        moves = self.env['fetchmail.server']._process_incoming_supplier_document(
            file_data, from_address, self.company_data['company'].id
        )

        self.assertEqual(len(moves), 1)

        move = moves[0]
        self.assertEqual(move.name, 'FNA 000100')
        self.assertEqual(move.partner_id, self.partner_sii)
        self.assertEqual(move.journal_id.type, 'purchase')
        self.assertEqual(move.l10n_latam_document_number, '000100')
        self.assertEqual(move.l10n_cl_dte_acceptation_status, 'received')
        self.assertEqual(move.invoice_source_email, from_address)
        self.assertEqual(move.l10n_latam_document_type_id.code, '34')
        self.assertEqual(move.company_id, self.company_data['company'])
        self.assertEqual(move.currency_id.name, 'CLP')
        self.assertEqual(move.amount_total, 329800)
        self.assertEqual(move.amount_tax, 0)
        self.assertEqual(len(move.invoice_line_ids), 1)
        self.assertEqual(move.invoice_line_ids.product_id, self.env['product.product'])
        self.assertEqual(move.invoice_line_ids.name, 'Unknown Product')
        self.assertEqual(move.invoice_line_ids.price_unit, 32980.0)

    def test_create_credit_note_61_from_attachment(self):
        att_name = 'incoming_credit_note_61.xml'
        from_address = 'incoming_dte@test.com'
        with file_open(f'l10n_cl_edi/tests/fetchmail_dtes/{att_name}', 'rb', filter_ext=('.xml',)) as f:
            content = f.read()
            file_data = {'name': att_name, 'raw': content, 'xml_tree': etree.fromstring(content)}
        moves = self.env['fetchmail.server']._process_incoming_supplier_document(
            file_data, from_address, self.company_data['company'].id)

        self.assertEqual(len(moves), 1)

        move = moves[0]
        self.assertEqual(move.name, 'N/C 1072252')
        self.assertEqual(move.move_type, 'in_refund')
        self.assertEqual(move.partner_id, self.partner_dte_2)
        self.assertEqual(move.journal_id.type, 'purchase')
        self.assertEqual(move.l10n_latam_document_number, '1072252')
        self.assertEqual(move.l10n_cl_dte_acceptation_status, 'received')
        self.assertEqual(move.invoice_source_email, from_address)
        self.assertEqual(move.l10n_latam_document_type_id.code, '61')
        self.assertEqual(move.company_id, self.company_data['company'])
        self.assertEqual(len(move.invoice_line_ids), 1)
        self.assertEqual(move.invoice_line_ids.product_id, self.env['product.product'])
        self.assertEqual(move.invoice_line_ids.name, 'CORREA ALTERN P.47 HDI 163HP/EXPRT 2.0 HDI 6PK1245')
        self.assertEqual(move.invoice_line_ids.price_unit, 8303.0)

    def test_process_incoming_customer_claim_move_not_found(self):
        att_name = 'incoming_acknowledge.xml'
        with file_open(f'l10n_cl_edi/tests/fetchmail_dtes/{att_name}', 'rb', filter_ext=('.xml',)) as f:
            content = f.read()
            file_data = {'name': att_name, 'raw': content, 'xml_tree': etree.fromstring(content)}
        l10n_latam_document_type = self.env['l10n_latam.document.type'].search([
            ('code', '=', '34'),
            ('country_id.code', '=', 'CL')
        ])
        with patch('logging.Logger.warning') as logger:
            self.env['fetchmail.server']._process_incoming_customer_claim(
                self.company_data['company'].id, file_data, origin_type='incoming_acknowledge'
            )
            logger.assert_called_with(
                'Move not found with partners: %s, document_number: %s, l10n_latam_document_type: %s, company_id: %s',
                    self.partner_sii.ids, '254', l10n_latam_document_type.id, self.company_data['company'].id)

    def test_process_incoming_customer_claim_acknowledge(self):
        l10n_latam_document_type = self.env['l10n_latam.document.type'].search([
            ('code', '=', '34'),
            ('country_id.code', '=', 'CL')
        ])
        with Form(self.env['account.move'].with_context(default_move_type='out_invoice')) as invoice_form:
            invoice_form.partner_id = self.partner_sii
            invoice_form.l10n_latam_document_number = '00254'
            invoice_form.l10n_latam_document_type_id = l10n_latam_document_type
            with invoice_form.invoice_line_ids.new() as invoice_line_form:
                invoice_line_form.product_id = self.product_a
                invoice_line_form.quantity = 1
                invoice_line_form.price_unit = 79
                invoice_line_form.tax_ids.clear()

        move = invoice_form.save()
        move.l10n_cl_dte_status = 'accepted'
        # Since the new creation of the account move name, the name must by force to avoid errors
        move.name = 'FNA 000254'

        att_name = 'incoming_acknowledge.xml'
        with file_open(f'l10n_cl_edi/tests/fetchmail_dtes/{att_name}', 'rb', filter_ext=('.xml',)) as f:
            content = f.read()
            file_data = {'name': att_name, 'raw': content, 'xml_tree': etree.fromstring(content)}

        self.env['fetchmail.server']._process_incoming_customer_claim(
            self.company_data['company'].id, file_data, origin_type='incoming_acknowledge')

        self.assertEqual(move.l10n_cl_dte_acceptation_status, 'received')

    def test_process_incoming_customer_claim_acknowledge_when_partner_has_invoice_child(self):
        """Make sure that we search for an existing invoice for all possible partners when multiple share the
        the same VAT number. For instance, this can happen when a parent partner has a child invoice contact.
        """

        self.env['res.partner'].create([{
            'name': 'Invoice child',
            'parent_id': self.partner_sii.id,
            'vat':  self.partner_sii.vat,
            'type': 'invoice',
            'is_company': True,
            'company_id': self.partner_sii.company_id.id,
        }])
        tax_exempt_invoice_type = self.env['l10n_latam.document.type'].search([
            ('code', '=', '34'),
            ('country_id.code', '=', 'CL'),
        ])

        move = self._create_invoice_one_line(
            partner_id=self.partner_sii,
            product_id=self.product_a,
            price_unit=79,
            move_name='FNA 000254',
            l10n_latam_document_number='00254',
            l10n_latam_document_type_id=tax_exempt_invoice_type,
            l10n_cl_dte_status='accepted',
        )

        att_name = 'incoming_acknowledge.xml'
        with file_open(f'l10n_cl_edi/tests/fetchmail_dtes/{att_name}', 'rb', filter_ext=('.xml',)) as f:
            content = f.read()
            file_data = {'name': att_name, 'raw': content, 'xml_tree': etree.fromstring(content)}

        self.env['fetchmail.server']._process_incoming_customer_claim(
            self.company_data['company'].id, file_data, origin_type='incoming_acknowledge')

        self.assertEqual(move.l10n_cl_dte_acceptation_status, 'received')

    @patch('odoo.addons.l10n_cl_edi.models.l10n_cl_edi_util.L10n_ClEdiUtil._get_cl_current_strftime')
    def test_process_incoming_customer_claim_accepted(self, get_cl_current_strftime):
        get_cl_current_strftime.return_value = '2019-10-24T20:00:00'
        l10n_latam_document_type = self.env['l10n_latam.document.type'].search([
            ('code', '=', '33'),
            ('country_id.code', '=', 'CL')
        ])
        with Form(self.env['account.move'].with_context(default_move_type='out_invoice')) as invoice_form:
            invoice_form.partner_id = self.partner_sii
            invoice_form.l10n_latam_document_number = '0301'
            invoice_form.l10n_latam_document_type_id = l10n_latam_document_type
            invoice_form.invoice_date = '2019-10-23'
            with invoice_form.invoice_line_ids.new() as invoice_line_form:
                invoice_line_form.product_id = self.product_a
                invoice_line_form.quantity = 1
                invoice_line_form.price_unit = 518732.7731

        move = invoice_form.save()
        # Since the new creation of the account move name, the name must by force to avoid errors
        move.name = 'FAC 000301'
        move._post(soft=False)
        move.l10n_cl_dte_status = 'accepted'

        att_name = 'incoming_commercial_accept.xml'
        with file_open(f'l10n_cl_edi/tests/fetchmail_dtes/{att_name}', 'rb', filter_ext=('.xml',)) as f:
            content = f.read()
            file_data = {'name': att_name, 'raw': content, 'xml_tree': etree.fromstring(content)}

        self.env['fetchmail.server']._process_incoming_customer_claim(
            self.company_data['company'].id, file_data, origin_type='incoming_commercial_accept')

        self.assertEqual(move.l10n_cl_dte_acceptation_status, 'accepted')

    @patch('odoo.addons.l10n_cl_edi.models.l10n_cl_edi_util.L10n_ClEdiUtil._get_cl_current_strftime')
    def test_process_incoming_customer_claim_rejected(self, get_cl_current_strftime):
        get_cl_current_strftime.return_value = '2019-10-24T20:00:00'
        l10n_latam_document_type = self.env['l10n_latam.document.type'].search([
            ('code', '=', '34'),
            ('country_id.code', '=', 'CL')
        ])
        with Form(self.env['account.move'].with_context(default_move_type='out_invoice')) as invoice_form:
            invoice_form.partner_id = self.partner_sii
            invoice_form.l10n_latam_document_number = '254'
            invoice_form.l10n_latam_document_type_id = l10n_latam_document_type
            invoice_form.invoice_date = '2019-10-23'
            with invoice_form.invoice_line_ids.new() as invoice_line_form:
                invoice_line_form.product_id = self.product_a
                invoice_line_form.quantity = 1
                invoice_line_form.price_unit = 2398053.78
                invoice_line_form.tax_ids.clear() # there shouldn't be any taxes applied for document type 34

        move = invoice_form.save()
        # Since the new creation of the account move name, the name must by force to avoid errors
        move.name = 'FNA 000254'
        move._post(soft=False)
        move.l10n_cl_dte_status = 'accepted'

        att_name = 'incoming_commercial_reject.xml'
        with file_open(f'l10n_cl_edi/tests/fetchmail_dtes/{att_name}', 'rb', filter_ext=('.xml',)) as f:
            content = f.read()
            file_data = {'name': att_name, 'raw': content, 'xml_tree': etree.fromstring(content)}

        self.env['fetchmail.server']._process_incoming_customer_claim(
            self.company_data['company'].id, file_data, origin_type='incoming_commercial_reject')

        self.assertEqual(move.l10n_cl_dte_acceptation_status, 'claimed')

    def test_process_incoming_customer_claim_rejected_missing_partner_vat(self):
        att_name = 'incoming_commercial_reject_missing_partner_vat.xml'
        with file_open(f'l10n_cl_edi/tests/fetchmail_dtes/{att_name}', 'rb', filter_ext=('.xml',)) as f:
            content = f.read()
            file_data = {'name': att_name, 'raw': content, 'xml_tree': etree.fromstring(content)}

        with self.assertLogs(level='WARNING'):
            self.env['fetchmail.server']._process_incoming_customer_claim(
                self.company_data['company'].id,
                file_data,
                origin_type='incoming_commercial_reject',
            )

    def test_process_incoming_invoice_currency_code(self):
        att_name = 'incoming_invoice_33_currency_code.xml'
        from_address = 'incoming_dte@test.com'
        with file_open(f'l10n_cl_edi/tests/fetchmail_dtes/{att_name}', 'rb', filter_ext=('.xml',)) as f:
            content = f.read()
            file_data = {'name': att_name, 'raw': content, 'xml_tree': etree.fromstring(content)}
        move = self.env['fetchmail.server']._process_incoming_supplier_document(
            file_data, from_address, self.company_data['company'].id
        )
        self.assertEqual(move.currency_id.name, 'USD')

    def test_processing_incoming_customer_claim_batched(self):
        """ Test processing of batched DTEs in a single xml """
        att_name = 'incoming_supplier_dte_batched.xml'
        from_address = 'incoming_dte@test.com'
        with file_open(f'l10n_cl_edi/tests/fetchmail_dtes/{att_name}', 'rb') as f:
            content = f.read()
        file_data = {'name': att_name, 'raw': content, 'xml_tree': etree.fromstring(content)}
        moves = self.env['fetchmail.server']._process_incoming_supplier_document(
            file_data, from_address, self.company_data['company'].id
        )
        self.assertEqual(len(moves), 2)

        self.assertRecordValues(moves, [
            {'l10n_latam_document_number': '001050', 'amount_total': 45196.0},
            {'l10n_latam_document_number': '001051', 'amount_total': 45196.0},
        ])
        for move in moves:
            self.assertEqual(len(move.invoice_line_ids), 1)
            self.assertEqual(len(move.l10n_cl_reference_ids), 1)

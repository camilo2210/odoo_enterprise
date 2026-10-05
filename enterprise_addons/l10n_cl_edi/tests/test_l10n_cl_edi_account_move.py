# -*- coding: utf-8 -*-
import os

from freezegun import freeze_time
from lxml import etree
from unittest.mock import patch

from odoo import Command
from odoo.addons.l10n_cl_edi.models.account_move import XML_NAMESPACES
from odoo.tools import file_open, misc
from odoo.tests import tagged
from .common import TestL10nClEdiCommon, _check_with_xsd_patch, _is_valid_certificate


@tagged('post_install_l10n', 'post_install', '-at_install')
@patch('odoo.tools.xml_utils._check_with_xsd', _check_with_xsd_patch)
@patch('odoo.addons.certificate.models.certificate.CertificateCertificate._compute_is_valid', _is_valid_certificate)
class TestL10nClDte(TestL10nClEdiCommon):
    """
    Summary of the document types to test:
        - 33:
            - A invoice with tax in each line
            - A invoice with references_ids and tax in each line
            - A invoice with holding taxes
            - A invoice with discounts
        - 34:
            - A invoice with two lines
        - 56:
            - A  invoice with line discounts
        - 110:
            - An exportation invoice for services
    """
    _test_user_groups = None  # FIXME list needed groups

    @patch('odoo.addons.l10n_cl_edi.models.l10n_cl_edi_util.L10n_ClEdiUtil._get_cl_current_strftime')
    def test_l10n_cl_dte_39(self, get_cl_current_strftime):
        get_cl_current_strftime.return_value = '2019-10-24T20:00:00'

        self.tax_19 = self.env['account.tax'].search([
            ('name', '=', '19% VAT'),
            ('type_tax_use', '=', 'sale'),
            ('company_id', '=', self.company_data['company'].id),
        ])
        invoice = self.env['account.move'].with_context(default_move_type='out_invoice').create({
            'partner_id': self.partner_anonimo.id,
            'move_type': 'out_invoice',
            'invoice_date': '2019-10-23',
            'currency_id': self.env.ref('base.CLP').id,
            'journal_id': self.sale_journal.id,
            'l10n_latam_document_type_id': self.env.ref('l10n_cl.dc_b_f_dte').id,
            'company_id': self.company_data['company'].id,
            'invoice_line_ids': [
                Command.create({
                    'name': 'Regla De Anchura De Grietas',
                    'product_id': self.product_a.id,
                    'product_uom_id': self.product_a.uom_id.id,
                    'quantity': 1,
                    'price_unit': 10694.70,
                    'tax_ids': [self.tax_19.id],
                }),
                Command.create({
                    'name': 'Despacho Chilexpress',
                    'product_id': self.product_a.id,
                    'product_uom_id': self.product_a.uom_id.id,
                    'quantity': 1,
                    'price_unit': 6000.0,
                    'tax_ids': [self.tax_19.id],
                }),
            ],
        })

        invoice.action_post()

        self.assertEqual(invoice.state, 'posted')
        self.assertEqual(invoice.l10n_cl_dte_status, 'not_sent')

        xml_expected_dte = misc.file_open('l10n_cl_edi/tests/expected_dtes/dte_39.xml').read()

        self.assertXmlTreeEqual(
            self.get_xml_tree_from_attachment(invoice.sudo().l10n_cl_sii_send_file),
            self.get_xml_tree_from_string(xml_expected_dte.encode()),
        )

    def test_analyze_sii_result_ask_for_status_1(self):
        """ Test 'ask_for_status' status when (detail_rep_rech == None) """
        invoice = self.env['account.move'].create({
            'partner_id': self.partner_anonimo.id,
            'move_type': 'out_invoice',
            'l10n_latam_document_type_id': self.env.ref('l10n_cl.dc_b_f_dte').id,
        })
        sii_result = {
            'rut_emisor': '11111111-1',
            'rut_envia': '22222222-0',
            'trackid': '12345678',
            'fecha_recepcion': '26/03/2024 10:00:00',
            'estado': 'REC',
            'estadistica': None,
            'detalle_rep_rech': None,
        }
        self.assertEqual(invoice._analyze_sii_result_rest(sii_result), 'ask_for_status')

    def test_analyze_sii_result_ask_for_status_2(self):
        """ Test 'ask_for_status' status when (estado == 'SOK' and estadistica == []) """
        invoice = self.env['account.move'].create({
            'partner_id': self.partner_anonimo.id,
            'move_type': 'out_invoice',
            'l10n_latam_document_type_id': self.env.ref('l10n_cl.dc_b_f_dte').id,
        })
        sii_result = {
            'rut_emisor': '11111111-1',
            'rut_envia': '22222222-0',
            'trackid': '12345678',
            'fecha_recepcion': '26/03/2024 10:00:00',
            'estado': 'SOK',
            'estadistica': [],
            'detalle_rep_rech': [],
        }
        self.assertEqual(invoice._analyze_sii_result_rest(sii_result), 'ask_for_status')

    def test_analyze_sii_result_accepted(self):
        """ Test 'accepted' status when (estadistica['informados'] == estadistica['aceptados']) """
        invoice = self.env['account.move'].create({
            'partner_id': self.partner_anonimo.id,
            'move_type': 'out_invoice',
            'l10n_latam_document_type_id': self.env.ref('l10n_cl.dc_b_f_dte').id,
        })
        sii_result = {
            'rut_emisor': '11111111-1',
            'rut_envia': '22222222-0',
            'trackid': '12345678',
            'fecha_recepcion': '26/03/2024 10:00:00',
            'estado': 'EPR',
            'estadistica': [{'tipo': 39, 'informados': 1, 'aceptados': 1, 'rechazados': 0, 'reparos': 0}],
            'detalle_rep_rech': [],
        }
        self.assertEqual(invoice._analyze_sii_result_rest(sii_result), 'accepted')

    @freeze_time('2019-10-24T20:00:00', tz_offset=3)
    def test_l10n_cl_dte_33(self):
        self.tax_19 = self.env['account.tax'].search([
            ('name', '=', '19% VAT'),
            ('type_tax_use', '=', 'sale'),
            ('company_id', '=', self.company_data['company'].id)])
        invoice = self.env['account.move'].with_context(default_move_type='out_invoice').create({
            'partner_id': self.partner_sii.id,
            'move_type': 'out_invoice',
            'invoice_date_due': '2019-10-23',
            'invoice_date': '2019-10-23',
            'currency_id': self.env.ref('base.CLP').id,
            'journal_id': self.sale_journal.id,
            'l10n_latam_document_type_id': self.env.ref('l10n_cl.dc_a_f_dte').id,
            'company_id': self.company_data['company'].id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Tapa Ranurada UL FM 300 6"',
                'product_id': self.product_a.id,
                'product_uom_id': self.product_a.uom_id.id,
                'quantity': 26,
                'price_unit': 2391.0,
                'tax_ids': [self.tax_19.id],
            }), (0, 0, {
                'name': 'Copla Flexible 1NS 6"',
                'product_id': self.product_a.id,
                'product_uom_id': self.product_a.uom_id.id,
                'quantity': 80,
                'price_unit': 2914.0,
                'tax_ids': [self.tax_19.id],
            })],
        })

        invoice.action_post()
        self.assertEqual(invoice.state, 'posted')
        self.assertEqual(invoice.l10n_cl_dte_status, 'not_sent')
        xml_expected_dte = misc.file_open(os.path.join(
            'l10n_cl_edi', 'tests', 'expected_dtes', 'dte_33.xml')).read()

        self.assertXmlTreeEqual(
            self.get_xml_tree_from_attachment(invoice.sudo().l10n_cl_sii_send_file),
            self.get_xml_tree_from_string(xml_expected_dte.encode())
        )

    @freeze_time('2019-10-24T20:00:00', tz_offset=3)
    def test_l10n_cl_dte_33_with_reference_ids(self):
        self.tax_19 = self.env['account.tax'].search([
            ('name', '=', '19% VAT'),
            ('type_tax_use', '=', 'sale'),
            ('company_id', '=', self.company_data['company'].id)])
        invoice = self.env['account.move'].with_context(default_move_type='out_invoice').create({
            'partner_id': self.partner_sii.id,
            'move_type': 'out_invoice',
            'invoice_date': '2019-10-23',
            'invoice_date_due': '2019-10-23',
            'currency_id': self.env.ref('base.CLP').id,
            'journal_id': self.sale_journal.id,
            'l10n_latam_document_type_id': self.env.ref('l10n_cl.dc_a_f_dte').id,
            'company_id': self.company_data['company'].id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Tapa Ranurada UL FM 300 6"',
                'product_id': self.product_a.id,
                'product_uom_id': self.product_a.uom_id.id,
                'quantity': 26,
                'price_unit': 2391.0,
                'tax_ids': [self.tax_19.id],
            }), (0, 0, {
                'name': 'Copla Flexible 1NS 6"',
                'product_id': self.product_a.id,
                'product_uom_id': self.product_a.uom_id.id,
                'quantity': 80,
                'price_unit': 2914.0,
                'tax_ids': [self.tax_19.id],
            })],
        })
        invoice.write({
            'l10n_cl_reference_ids': [(0, 0, {
                'origin_doc_number': 'PO00273',
                'l10n_cl_reference_doc_type_id': self.env.ref('l10n_cl.dc_odc').id,
                'reason': 'Test',
                'move_id': invoice.id,
                'date': '2019-10-18'
            }), (0, 0, {
                'origin_doc_number': '996327',
                'l10n_cl_reference_doc_type_id': self.env.ref('l10n_cl.dc_gd_dte').id,
                'reason': 'Test',
                'move_id': invoice.id,
                'date': '2019-10-18'
            })],
        })

        invoice._post()

        self.assertEqual(invoice.state, 'posted')
        self.assertEqual(invoice.l10n_cl_dte_status, 'not_sent')

        xml_expected_dte = misc.file_open(os.path.join(
            'l10n_cl_edi', 'tests', 'expected_dtes', 'dte_33_with_reference_ids.xml')).read()

        self.assertXmlTreeEqual(
            self.get_xml_tree_from_attachment(invoice.sudo().l10n_cl_sii_send_file),
            self.get_xml_tree_from_string(xml_expected_dte.encode()),
        )

    @freeze_time('2019-10-24T20:00:00', tz_offset=3)
    def test_l10n_cl_dte_33_withholding_taxes(self):
        self.tax_19 = self.env['account.tax'].search([
            ('name', '=', '19% VAT'),
            ('type_tax_use', '=', 'sale'),
            ('company_id', '=', self.company_data['company'].id)])
        self.tax_205 = self.env['account.tax'].search([
            ('name', '=', '20.5% ILA'),
            ('type_tax_use', '=', 'sale'),
            ('company_id', '=', self.company_data['company'].id)])
        self.tax_100 = self.env['account.tax'].search([
            ('name', '=', '10% ILA'),
            ('type_tax_use', '=', 'sale'),
            ('company_id', '=', self.company_data['company'].id)])

        invoice = self.env['account.move'].with_context(default_move_type='out_invoice').create({
            'partner_id': self.partner_sii.id,
            'move_type': 'out_invoice',
            'invoice_date': '2019-10-23',
            'invoice_date_due': '2019-10-23',
            'currency_id': self.env.ref('base.CLP').id,
            'journal_id': self.sale_journal.id,
            'l10n_latam_document_type_id': self.env.ref('l10n_cl.dc_a_f_dte').id,
            'company_id': self.company_data['company'].id,
            'invoice_line_ids': [(0, 0, {
                'name': 'FALERNIA CABERNET SAUVIGNON RESERVA 2018 750ML 14',
                'product_id': self.product_a.id,
                'product_uom_id': self.product_a.uom_id.id,
                'quantity': 1,
                'price_unit': 31110.0,
                'tax_ids': [self.tax_19.id, self.tax_205.id],
            }), (0, 0, {
                'name': 'FALERNIA CARMENERE 2017 RESERVA 14 750ML',
                'product_id': self.product_a.id,
                'product_uom_id': self.product_a.uom_id.id,
                'quantity': 1,
                'price_unit': 31110.0,
                'tax_ids': [self.tax_19.id, self.tax_205.id],
            }), (0, 0, {
                'name': 'FAL CARMENERE 2017 375CC',
                'product_id': self.product_a.id,
                'product_uom_id': self.product_a.uom_id.id,
                'quantity': 1,
                'price_unit': 36210.0,
                'tax_ids': [self.tax_19.id, self.tax_205.id],
            }), (0, 0, {
                'name': 'FALERNIA CARMENERE GRAN RESERVA 2016 750ML 15',
                'product_id': self.product_a.id,
                'product_uom_id': self.product_a.uom_id.id,
                'quantity': 1,
                'price_unit': 26138.0,
                'tax_ids': [self.tax_19.id, self.tax_205.id],
            }), (0, 0, {
                'name': 'FALERNIA C. SAUVIGNON GR.RESERVA 2017 750ML 14,5',
                'product_id': self.product_a.id,
                'product_uom_id': self.product_a.uom_id.id,
                'quantity': 1,
                'price_unit': 26138.0,
                'tax_ids': [self.tax_19.id, self.tax_205.id],
            }), (0, 0, {
                'name': 'COCA COLA NO RETORNABLE 2L',
                'product_id': self.product_a.id,
                'product_uom_id': self.product_a.uom_id.id,
                'quantity': 12,
                'price_unit': 800.0,
                'tax_ids': [self.tax_19.id, self.tax_100.id],
            }), (0, 0, {
                'name': 'COSTO LOGISTICO',
                'product_id': self.product_a.id,
                'product_uom_id': self.product_a.uom_id.id,
                'quantity': 1,
                'price_unit': 7143.0,
                'tax_ids': [self.tax_19.id],
            }), ],
        })

        invoice.action_post()

        self.assertEqual(invoice.state, 'posted')
        self.assertEqual(invoice.l10n_cl_dte_status, 'not_sent')

        xml_expected_dte = misc.file_open(os.path.join(
            'l10n_cl_edi', 'tests', 'expected_dtes', 'dte_33_with_holding_taxes.xml')).read()

        self.assertXmlTreeEqual(
            self.get_xml_tree_from_attachment(invoice.sudo().l10n_cl_sii_send_file),
            self.get_xml_tree_from_string(xml_expected_dte.encode()),
        )

    @freeze_time('2019-10-24T20:00:00', tz_offset=3)
    def test_l10n_cl_dte_33_with_discounts(self):
        self.tax_19 = self.env['account.tax'].search([
            ('name', '=', '19% VAT'),
            ('type_tax_use', '=', 'sale'),
            ('company_id', '=', self.company_data['company'].id)])
        invoice = self.env['account.move'].with_context(default_move_type='out_invoice').create({
            'partner_id': self.partner_sii.id,
            'move_type': 'out_invoice',
            'invoice_date': '2019-10-23',
            'invoice_date_due': '2019-10-23',
            'currency_id': self.env.ref('base.CLP').id,
            'journal_id': self.sale_journal.id,
            'l10n_latam_document_type_id': self.env.ref('l10n_cl.dc_a_f_dte').id,
            'company_id': self.company_data['company'].id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Tapa Ranurada UL FM 300 6"',
                'product_id': self.product_a.id,
                'product_uom_id': self.product_a.uom_id.id,
                'quantity': 200,
                'price_unit': 5.0,
                'discount': 5.99,
                'tax_ids': [self.tax_19.id],
            }), (0, 0, {
                'name': 'Copla Flexible 1NS 6"',
                'product_id': self.product_a.id,
                'product_uom_id': self.product_a.uom_id.id,
                'quantity': 300,
                'price_unit': 800.0,
                'discount': 9.77,
                'tax_ids': [self.tax_19.id],
            }), (0, 0, {
                'name': 'Desk Combination',
                'product_id': self.product_a.id,
                'product_uom_id': self.product_a.uom_id.id,
                'quantity': 5,
                'price_unit': 40000.0,
                'discount': 10.00,
                'tax_ids': [self.tax_19.id],
            })],
        })

        invoice.action_post()

        self.assertEqual(invoice.state, 'posted')
        self.assertEqual(invoice.l10n_cl_dte_status, 'not_sent')

        xml_expected_dte = misc.file_open(os.path.join(
            'l10n_cl_edi', 'tests', 'expected_dtes', 'dte_33_with_discounts.xml')).read()
        self.assertXmlTreeEqual(
            self.get_xml_tree_from_attachment(invoice.sudo().l10n_cl_sii_send_file),
            self.get_xml_tree_from_string(xml_expected_dte.encode()),
        )

    @freeze_time('2022-11-24T12:45:37', tz_offset=3)
    def test_l10n_cl_dte_33_usd_with_discounts(self):
        self.tax_19 = self.env['account.tax'].search([
            ('name', '=', '19% VAT'),
            ('type_tax_use', '=', 'sale'),
            ('company_id', '=', self.company_data['company'].id)])
        currency_usd = self.env.ref('base.USD')
        currency_usd.active = True
        self.env['res.currency.rate'].create({
            'name': '2022-11-23',
            'company_id': self.company_data['company'].id,
            'currency_id': currency_usd.id,
            'rate': 0.001069187097})
        invoice = self.env['account.move'].with_context(default_move_type='out_invoice').create({
            'partner_id': self.partner_sii.id,
            'move_type': 'out_invoice',
            'invoice_date': '2022-11-24',
            'currency_id': self.env.ref('base.USD').id,
            'journal_id': self.sale_journal.id,
            'l10n_latam_document_type_id': self.env.ref('l10n_cl.dc_a_f_dte').id,
            'company_id': self.company_data['company'].id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Tapa Ranurada UL FM 300 6"',
                'product_id': self.product_a.id,
                'product_uom_id': self.product_a.uom_id.id,
                'quantity': 2,
                'price_unit': 123.45,
                'discount': 10,
                'tax_ids': [self.tax_19.id],
            }), (0, 0, {
                'name': 'Copla Flexible 1NS 6"',
                'product_id': self.product_a.id,
                'product_uom_id': self.product_a.uom_id.id,
                'quantity': 1,
                'price_unit': 12.31,
                'discount': 5,
                'tax_ids': [self.tax_19.id],
            })],
        })

        invoice.action_post()

        self.assertEqual(invoice.state, 'posted')
        self.assertEqual(invoice.l10n_cl_dte_status, 'not_sent')

        xml_expected_dte = misc.file_open('l10n_cl_edi/tests/expected_dtes/dte_33_usd_with_discounts.xml').read()
        self.assertXmlTreeEqual(
            self.get_xml_tree_from_attachment(invoice.sudo().l10n_cl_sii_send_file),
            self.get_xml_tree_from_string(xml_expected_dte.encode()),
        )

    @freeze_time('2019-10-22T20:23:27', tz_offset=3)
    def test_l10n_cl_dte_34(self):
        self.product_a.write({
            'name': 'Desk Combination',
            'default_code': 'FURN_7800'
        })

        invoice = self.env['account.move'].with_context(default_move_type='out_invoice').create({
            'partner_id': self.partner_sii.id,
            'move_type': 'out_invoice',
            'invoice_date': '2019-10-22',
            'invoice_date_due': '2019-10-22',
            'currency_id': self.env.ref('base.CLP').id,
            'journal_id': self.sale_journal.id,
            'l10n_latam_document_type_id': self.env.ref('l10n_cl.dc_y_f_dte').id,
            'company_id': self.company_data['company'].id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Desk Combination',
                'product_id': self.product_a.id,
                'product_uom_id': self.product_a.uom_id.id,
                'quantity': 1,
                'price_unit': 1200000.0,
                'tax_ids': [],
            }), (0, 0, {
                'name': 'Desk Combination',
                'product_id': self.product_a.id,
                'product_uom_id': self.product_a.uom_id.id,
                'quantity': 1,
                'price_unit': 2400000.0,
                'tax_ids': [],
            })],
        })

        invoice.action_post()

        self.assertEqual(invoice.state, 'posted')
        self.assertEqual(invoice.l10n_cl_dte_status, 'not_sent')

        xml_expected_dte = misc.file_open(os.path.join(
            'l10n_cl_edi', 'tests', 'expected_dtes', 'dte_34.xml')).read()

        self.assertXmlTreeEqual(
            self.get_xml_tree_from_attachment(invoice.sudo().l10n_cl_sii_send_file),
            self.get_xml_tree_from_string(xml_expected_dte.encode()),
        )

    @freeze_time('2019-10-24T20:00:00', tz_offset=3)
    def test_l10n_cl_dte_56(self):
        self.tax_19 = self.env['account.tax'].search([
            ('name', '=', '19% VAT'),
            ('type_tax_use', '=', 'sale'),
            ('company_id', '=', self.company_data['company'].id)])

        invoice = self.env['account.move'].with_context(default_move_type='out_invoice').create({
            'partner_id': self.partner_sii.id,
            'move_type': 'out_invoice',
            'invoice_date': '2019-10-23',
            'invoice_date_due': '2019-10-23',
            'currency_id': self.env.ref('base.CLP').id,
            'journal_id': self.sale_journal.id,
            'l10n_latam_document_type_id': self.env.ref('l10n_cl.dc_nd_f_dte').id,
            'l10n_latam_document_number': '122',
            'company_id': self.company_data['company'].id,
            'invoice_line_ids': [(0, 0, {
                'name': '[WUS-0558538] Conjunto De Control Electrónico Ps3.39',
                'product_id': self.product_a.id,
                'product_uom_id': self.product_a.uom_id.id,
                'quantity': 1,
                'discount': 10.00,
                'price_unit': 497804.44,
                'tax_ids': [self.tax_19.id],
            }), (0, 0, {
                'name': '[WUS-0558424A] Vastago Ps 3.39',
                'product_id': self.product_a.id,
                'product_uom_id': self.product_a.uom_id.id,
                'quantity': 1,
                'price_unit': 171375.56,
                'discount': 10.00,
                'tax_ids': [self.tax_19.id],
            }), (0, 0, {
                'name': '[WUS-0555217] Filtro Malla Acero',
                'product_id': self.product_a.id,
                'product_uom_id': self.product_a.uom_id.id,
                'quantity': 1,
                'price_unit': 6801.11,
                'discount': 10.00,
                'tax_ids': [self.tax_19.id],
            }), (0, 0, {
                'name': '[WUS-0524421] Retenedor Wagner 339',
                'product_id': self.product_a.id,
                'product_uom_id': self.product_a.uom_id.id,
                'quantity': 1,
                'price_unit': 19722.22,
                'discount': 10.00,
                'tax_ids': [self.tax_19.id],
            }), (0, 0, {
                'name': '[INSUMO] Insumos Varios',
                'product_id': self.product_a.id,
                'product_uom_id': self.product_a.uom_id.id,
                'quantity': 2,
                'price_unit': 4760.00,
                'tax_ids': [self.tax_19.id],
            }), (0, 0, {
                'name': '[SERVICIO03] Servicio de Reparación Equipo Airless (Fieldlazer, 695-MarkV, PS3.29-3.39)',
                'product_id': self.product_a.id,
                'product_uom_id': self.product_a.uom_id.id,
                'quantity': 1,
                'price_unit': 114250.00,
                'tax_ids': [self.tax_19.id],
            }), (0, 0, {
                'name': '[WUS-0558587] Kit Reparación Ps3 .39',
                'product_id': self.product_a.id,
                'product_uom_id': self.product_a.uom_id.id,
                'quantity': 1,
                'price_unit': 150973.33,
                'discount': 10.00,
                'tax_ids': [self.tax_19.id],
            }), ],
        })

        invoice.write({
            'l10n_cl_reference_ids': [[0, 0, {
                'move_id': invoice.id,
                'origin_doc_number': 1961,
                'l10n_cl_reference_doc_type_id': self.env.ref('l10n_cl.dc_nc_f_dte').id,
                'reference_doc_code': '1',
                'reason': 'Anulación NC por aceptación con reparo (N/C 001961)',
                'date': invoice.invoice_date, }, ], ]
        })

        invoice.action_post()

        self.assertEqual(invoice.state, 'posted')
        self.assertEqual(invoice.l10n_cl_dte_status, 'not_sent')

        xml_expected_dte = misc.file_open(os.path.join(
            'l10n_cl_edi', 'tests', 'expected_dtes', 'dte_56.xml')).read()

        self.assertXmlTreeEqual(
            self.get_xml_tree_from_attachment(invoice.sudo().l10n_cl_dte_file),
            self.get_xml_tree_from_string(xml_expected_dte.encode()),
        )

    def test_demo_certificate_serial_number(self):
        cert = self.env.ref('l10n_cl_edi.l10n_cl_demo_certificate', raise_if_not_found=False)
        if not cert:
            self.skipTest("Demo data not installed: l10n_cl_edi.l10n_cl_demo_certificate")
        self.assertEqual(cert.sudo().subject_serial_number, "23841194-7")

    @freeze_time('2025-12-11T14:00:00', tz_offset=3)
    def test_zero_amount_invoice_in_foreign_currency(self):
        """
        Test that confirming an invoice with zero total in a foreign currency
        does not raise a traceback.
        """
        invoice = self.env['account.move'].create({
            'partner_id': self.partner_sii.id,
            'move_type': 'out_invoice',
            'currency_id': self.env.ref('base.USD').id,
            'journal_id': self.sale_journal.id,
            'invoice_date': '2025-12-11',
            'l10n_latam_document_type_id': self.env.ref('l10n_cl.dc_y_f_dte').id,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product_a.id,
                'quantity': 1,
                'price_unit': 0,
            })]
        })
        invoice.action_post()
        self.assertEqual(invoice.state, 'posted')

    @freeze_time('2019-10-24T20:00:00', tz_offset=3)
    def test_l10n_cl_dte_33_multiple_caf(self):
        """If there are multiple CAFs we want to make sure that the sequence calculation finds
            the right one and is able to properly assign the next number in sequence."""
        self.tax_19 = self.env['account.tax'].search([
            ('name', '=', '19% VAT'),
            ('type_tax_use', '=', 'sale'),
            ('company_id', '=', self.company_data['company'].id)])
        invoice = self.env['account.move'].with_context(default_move_type='out_invoice').create({
            'partner_id': self.partner_sii.id,
            'move_type': 'out_invoice',
            'invoice_date_due': '2019-10-23',
            'invoice_date': '2019-10-23',
            'currency_id': self.env.ref('base.CLP').id,
            'journal_id': self.sale_journal.id,
            'l10n_latam_document_type_id': self.env.ref('l10n_cl.dc_a_f_dte').id,
            'company_id': self.company_data['company'].id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Tapa Ranurada UL FM 300 6"',
                'product_id': self.product_a.id,
                'product_uom_id': self.product_a.uom_id.id,
                'quantity': 26,
                'price_unit': 2391.0,
                'tax_ids': [self.tax_19.id],
            }), (0, 0, {
                'name': 'Copla Flexible 1NS 6"',
                'product_id': self.product_a.id,
                'product_uom_id': self.product_a.uom_id.id,
                'quantity': 80,
                'price_unit': 2914.0,
                'tax_ids': [self.tax_19.id],
            })],
        })
        invoice.action_post()

        copied_invoice = invoice.copy()
        copied_invoice.action_post()
        # Resequence the copied invoice to introduce a gap and make it such that the next invoice
        # is outside of the range of the CAFs.
        copied_invoice.name = 'FAC 000321'

        another_copied_invoice = invoice.copy()
        another_copied_invoice.action_post()
        self.assertEqual(another_copied_invoice.name, 'FAC 000002')

    def test_l10n_cl_import_invoice_sale(self):
        """ Test to make sure drag and dropping xml file into the Sales journal
            will create a partner from the Receptor data defined in the xml
        """
        with file_open('l10n_cl_edi/tests/expected_dtes/dte_33.xml', 'rb') as file:
            dte_content = file.read()
            dte_33_attachment_id = self.env['ir.attachment'].create({
                'name': 'dte_33_attachment.xml',
                'mimetype': 'text/xml',
                'raw': dte_content,
                'res_model': 'account.move'
            })
            dte_33_xml_tree = etree.fromstring(dte_content)
        res_id = self.sale_journal.create_document_from_attachment([dte_33_attachment_id.id])['res_id']
        invoice = self.env['account.move'].browse(res_id)
        partner_vat = dte_33_xml_tree.findtext('.//ns0:RUTRecep', namespaces=XML_NAMESPACES)
        self.assertEqual(invoice.partner_id.vat, partner_vat, 'Partner should be customer from Receptor tag in XML.')

    def test_l10n_cl_import_invoice_purchase(self):
        """ Test to make sure drag and dropping xml file into the Purchase journal
            will create a partner from the Remisor data defined in the xml
        """
        with file_open('l10n_cl_edi/tests/fetchmail_dtes/incoming_supplier_dte.xml', 'rb') as file:
            content = file.read()
            incoming_supplier_dte_attachment_id = self.env['ir.attachment'].create({
                'name': 'incoming_supplier_dte_attachment.xml',
                'mimetype': 'text/xml',
                'raw': content,
                'res_model': 'account.move'
            })
            incoming_supplier_dte_xml_tree = etree.fromstring(content)
        res_id = self.purchase_journal.create_document_from_attachment([incoming_supplier_dte_attachment_id.id])['res_id']
        bill = self.env['account.move'].browse(res_id)
        partner_vat = incoming_supplier_dte_xml_tree.findtext('.//ns0:RUTEmisor', namespaces=XML_NAMESPACES)
        self.assertEqual(bill.partner_id.vat, partner_vat, 'Partner should be the vendor from Emisor tag in XML.')

    def test_l10n_cl_import_credit_note_sale(self):
        """ Test to make sure drag and dropping credit note XML file into the Sale journal
            will have the correct move_type of 'out_refund'
        """
        with file_open('l10n_cl_edi/tests/fetchmail_dtes/outgoing_credit_note_61.xml', 'rb') as file:
            content = file.read()
            outgoing_credit_note_61_attachment_id = self.env['ir.attachment'].create({
                'name': 'outgoing_credit_note_61_attachment.xml',
                'mimetype': 'text/xml',
                'raw': content,
                'res_model': 'account.move'
            })
        res_id = self.sale_journal.create_document_from_attachment([outgoing_credit_note_61_attachment_id.id])['res_id']
        credit_note = self.env['account.move'].browse(res_id)
        self.assertEqual(credit_note.move_type, 'out_refund', 'The move type should be a customer credit note.')

    def test_l10n_cl_import_credit_note_purchase(self):
        """ Test to make sure drag and dropping credit note XML file into the Purchase journal
            will have the correct move_type of 'in_refund'
        """
        with file_open('l10n_cl_edi/tests/fetchmail_dtes/incoming_credit_note_61.xml', 'rb') as file:
            content = file.read()
            incoming_credit_note_61_attachment_id = self.env['ir.attachment'].create({
                'name': 'incoming_credit_note_61_attachment.xml',
                'mimetype': 'text/xml',
                'raw': content,
                'res_model': 'account.move'
            })
        res_id = self.purchase_journal.create_document_from_attachment([incoming_credit_note_61_attachment_id.id])['res_id']
        credit_note = self.env['account.move'].browse(res_id)
        self.assertEqual(credit_note.move_type, 'in_refund', 'The move type should be a vendor credit note.')

    def test_vendor_bill_46_send_to_sii(self):
        """display_send_button must be True and the Send & Print wizard must not raise
        a constraint error for a posted vendor bill (doc type 46) with not_sent status."""
        tax_19 = self.env['account.tax'].search([
            ('name', '=', '19% VAT'),
            ('type_tax_use', '=', 'purchase'),
            ('company_id', '=', self.company_data['company'].id),
        ], limit=1)
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner_sii.id,
            'invoice_date': '2019-10-23',
            'currency_id': self.env.ref('base.CLP').id,
            'journal_id': self.purchase_journal.id,
            'l10n_latam_document_type_id': self.caf_46.l10n_latam_document_type_id.id,
            'company_id': self.company_data['company'].id,
            'invoice_line_ids': [Command.create({
                'name': 'Test product',
                'product_id': self.product_a.id,
                'quantity': 1,
                'price_unit': 10000.0,
                'tax_ids': [Command.set(tax_19.ids)],
            })],
        })
        bill.action_post()

        self.assertEqual(bill.l10n_cl_dte_status, 'not_sent')
        self.assertTrue(bill.display_send_button, 'Send button should be visible on a not_sent vendor bill')
        self.env['account.move.send.wizard'].with_context(
            active_model='account.move',
            active_ids=bill.ids,
        ).create({'move_id': bill.id})

    def test_l10n_cl_create_from_xml_access_right(self):
        """ Test that creating an invoice from XML works with lower access right """
        invoice = self.env['account.move'].with_user(self.simple_accountman).create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_anonimo.id,
        })
        with file_open('l10n_cl_edi/tests/expected_dtes/dte_33.xml', 'rb') as file:
            xml_content = file.read()
        attachment = self.env['ir.attachment'].sudo().create({
            'name': 'test_dte.xml',
            'mimetype': 'text/xml',
            'raw': xml_content,
            'res_model': 'account.move',
            'res_id': invoice.id,
        })
        file_data = invoice._to_files_data(attachment)[0]
        invoice.with_user(self.simple_accountman)._l10n_cl_import_dte(invoice, file_data, new=False)
        self.assertEqual(invoice.amount_untaxed, 295286.0)

from datetime import datetime, timezone, timedelta

from freezegun import freeze_time
from lxml import etree

from odoo.tests import tagged
from odoo.tools.misc import file_open
from .common import TestECDeliveryGuideCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestECDeliveryGuide(TestECDeliveryGuideCommon):

    _test_user_groups = None  # FIXME list needed groups

    @freeze_time('2025-02-24')
    def test_send_delivery_guide_flow(self):
        ''' Test the delivery guide submission + cancellation flow. '''
        with self.mock_zeep_client((
            (
                # First call: send the delivery guide
                'validarComprobante',
                {
                    'xml': file_open('l10n_ec_edi_stock/tests/expected_files/sent_delivery_guide.xml', 'rb').read(),
                },
                {
                    'estado': 'RECIBIDA',
                    'comprobantes': None
                },
            ),
            (
                # Second call: retrieve the status
                'autorizacionComprobante',
                {
                    'claveAccesoComprobante': '2402202506179236683600120010010000000013121521416',
                },
                {
                    'numeroComprobantes': '1',
                    'autorizaciones': {
                        'autorizacion': [{
                            'estado': 'AUTORIZADO',
                            'numeroAutorizacion': '1912202406010364761600110010010001912253121521419',
                            'fechaAutorizacion': datetime(2024, 12, 19, 12, 5, 29, tzinfo=timezone(timedelta(minutes=-5 * 60))),
                            'ambiente': 'PRUEBAS',
                            'comprobante': 'dummy',
                            'mensajes': None,
                        }],
                    },
                },
            ),
            (
                # Third call: retrieve the status
                'autorizacionComprobante',
                {
                    'claveAccesoComprobante': '2402202506179236683600120010010000000013121521416',
                },
                {
                    'numeroComprobantes': '1',
                    'autorizaciones': {
                        'autorizacion': [{
                            'estado': 'CANCELADO',
                            'mensajes': None,
                        }],
                    },
                },
            )
        )):
            # Send the delivery guide
            stock_picking = self.get_stock_picking()
            self.prepare_delivery_guide(stock_picking)

            self.assertRecordValues(stock_picking, [{
                'l10n_ec_edi_status': 'sent',
                'l10n_ec_delivery_guide_error': False,
                'l10n_ec_authorization_date': datetime(2024, 12, 19, 12, 5, 29),
            }])

            # Cancel the delivery guide
            stock_picking.button_action_cancel_delivery_guide()
            stock_picking.l10n_ec_send_delivery_guide_to_cancel()
            self.assertRecordValues(stock_picking, [{
                'l10n_ec_edi_status': 'cancelled',
                'l10n_ec_delivery_guide_error': False,
                'l10n_ec_authorization_date': False,
            }])

    def test_xml_tree_delivery_guide_basic(self):
        '''
        Validates the XML content of a delivery guide
        '''
        with freeze_time(self.frozen_today):
            stock_picking = self.get_stock_picking()
            self.prepare_delivery_guide(stock_picking)
            attachment_id = self.env['ir.attachment'].search([
                ('res_model', '=', 'stock.picking'),
                ('res_id', '=', stock_picking.id),
            ])
            decoded_content = attachment_id.raw.decode('utf-8')
            self.assertXmlTreeEqual(
                etree.fromstring(decoded_content),
                etree.fromstring(L10N_EC_EDI_XML_DELIVERY_GUIDE),
            )

    def test_xml_tree_delivery_guide_provider_vat(self):
        '''
        Validates that the RUC of the selected software provider is reported in the delivery guide XML
        '''
        self.company_data['company'].l10n_ec_edi_provider_id = self.env['res.partner'].create({
            'name': "EC Software Provider",
            'vat': '0453661050001',
        })
        with freeze_time(self.frozen_today):
            stock_picking = self.get_stock_picking()
            self.prepare_delivery_guide(stock_picking)
            attachment_id = self.env['ir.attachment'].search([
                ('res_model', '=', 'stock.picking'),
                ('res_id', '=', stock_picking.id),
            ])
            self.assertXmlTreeEqual(
                etree.fromstring(attachment_id.raw.decode('utf-8')),
                self.with_applied_xpath(
                    etree.fromstring(L10N_EC_EDI_XML_DELIVERY_GUIDE),
                    """
                        <xpath expr="//campoAdicional[@nombre='RUC Proveedor']" position="replace">
                            <campoAdicional nombre="RUC Proveedor">0453661050001</campoAdicional>
                        </xpath>
                    """,
                ),
            )

    def test_delivery_guide_provider_vat_alert(self):
        ''' Test the software provider RUC warning on a delivery guide. '''
        stock_picking = self.get_stock_picking()
        self.company_data['company'].l10n_ec_edi_provider_id = False

        # The warehouse is not configured for delivery guides yet, so nothing is warned about
        self.assertFalse(stock_picking.l10n_ec_edi_alerts)

        self.wh.write({'l10n_ec_entity': '001', 'l10n_ec_emission': '001'})
        self.assertIn('l10n_ec_edi_missing_provider_vat', stock_picking.l10n_ec_edi_alerts or {})

        provider = self.env['res.partner'].create({'name': "EC Software Provider", 'vat': '0453661050'})
        self.company_data['company'].l10n_ec_edi_provider_id = provider
        self.assertIn('l10n_ec_edi_missing_provider_vat', stock_picking.l10n_ec_edi_alerts or {})

        provider.vat = '0453661050001'
        self.assertFalse(stock_picking.l10n_ec_edi_alerts)


L10N_EC_EDI_XML_DELIVERY_GUIDE = """<autorizacion>
    <estado>AUTORIZADO</estado>
    <numeroAutorizacion>2501202206179236683600110010010000000013121521412</numeroAutorizacion>
    <fechaAutorizacion>2022-01-24 00:00:00</fechaAutorizacion>
    <ambiente>PRUEBAS</ambiente>
    <comprobante>
        <guiaRemision id="comprobante" version="1.1.0">
            <infoTributaria>
                <ambiente>1</ambiente>
                <tipoEmision>1</tipoEmision>
                <razonSocial>EC Test Company (official)</razonSocial>
                <ruc>1792366836001</ruc>
                <claveAcceso>2501202206179236683600110010010000000013121521412</claveAcceso>
                <codDoc>06</codDoc>
                <estab>001</estab>
                <ptoEmi>001</ptoEmi>
                <secuencial>000000001</secuencial>
                <dirMatriz>Avenida Machala 42</dirMatriz>
            </infoTributaria>
            <infoGuiaRemision>
                <dirEstablecimiento>Avenida Machala 42</dirEstablecimiento>
                <dirPartida>Avenida Machala 42</dirPartida>
                <razonSocialTransportista>Delivery guide Carrier EC</razonSocialTransportista>
                <tipoIdentificacionTransportista>05</tipoIdentificacionTransportista>
                <rucTransportista>0750032310</rucTransportista>
                <obligadoContabilidad>SI</obligadoContabilidad>
                <fechaIniTransporte>25/01/2022</fechaIniTransporte>
                <fechaFinTransporte>09/02/2022</fechaFinTransporte>
                <placa>OBA1413</placa>
            </infoGuiaRemision>
            <destinatarios>
                <destinatario>
                    <identificacionDestinatario>0453661050152</identificacionDestinatario>
                    <razonSocialDestinatario>EC Test Partner AàÁ³$£€èêÈÊöÔÇç¡⅛&amp;@™</razonSocialDestinatario>
                    <dirDestinatario>Av. Libertador Simón Bolívar 1155 - Quito - Ecuador</dirDestinatario>
                    <motivoTraslado>Goods Dispatch</motivoTraslado>
                    <detalles>
                        <detalle>
                            <codigoInterno>N/A</codigoInterno>
                            <descripcion>Computadora</descripcion>
                            <cantidad>1.0</cantidad>
                        </detalle>
                    </detalles>
                </destinatario>
            </destinatarios>
            <infoAdicional>
                <campoAdicional nombre="RUC Proveedor">1792366836001</campoAdicional>
            </infoAdicional>
        </guiaRemision>
    </comprobante>
</autorizacion>
""".encode()

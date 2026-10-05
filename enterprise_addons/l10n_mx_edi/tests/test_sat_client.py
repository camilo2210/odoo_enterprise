from datetime import timedelta
from lxml import etree
from unittest.mock import MagicMock, patch

from requests.exceptions import (
    ConnectionError as RequestsConnectionError,
    RequestException,
    Timeout as RequestsTimeout,
)

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.l10n_mx_edi.models.l10n_mx_edi_sat_client import (
    L10n_Mx_EdiSatDownloadClient,
    SAT_PACKAGE_DOWNLOAD_URL,
    SAT_REQUEST_DOWNLOAD_URL,
    SAT_UNPROCESSED_CODE_MAP,
)
from odoo.addons.l10n_mx_edi.tests.common_sat_download import (
    DEFAULT_CFDI_UUID,
    DEFAULT_REQUEST_UUID,
    TestCfdiRequestCommon,
)


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestSatDownloadClient(TestCfdiRequestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.expected_signature_xml = """
            <Signature xmlns="http://www.w3.org/2000/09/xmldsig#">
                <SignedInfo>
                    <CanonicalizationMethod Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#"/>
                    <SignatureMethod Algorithm="http://www.w3.org/2000/09/xmldsig#rsa-sha1"/>
                    <Reference URI="#_0">
                        <Transforms>
                            <Transform Algorithm="http://www.w3.org/2000/09/xmldsig#enveloped-signature"/>
                        </Transforms>
                        <DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha1"/>
                        <DigestValue>___ignore___</DigestValue>
                    </Reference>
                </SignedInfo>
                <SignatureValue>___ignore___</SignatureValue>
                <KeyInfo>
                    <X509Data><X509Certificate>___ignore___</X509Certificate></X509Data>
                </KeyInfo>
            </Signature>
        """
        cls.request_rfc = cls.fiel_certificate.company_id.partner_id.commercial_partner_id.vat

    def _assert_request_payload(self, mocked_post, service_url, soap_action, expected_envelope, token=None):
        args, kwargs = mocked_post.call_args
        request_data = {
            'url': args[0] if args else kwargs['service_url'],
            'headers': kwargs['headers'],
            'timeout': kwargs.get('timeout'),
            'envelope': etree.fromstring(kwargs['data']),
        }

        self.assertEqual(request_data['url'], service_url)

        expected_headers = {
            'Content-type': 'text/xml;charset="UTF-8"',
            'Accept': 'text/xml',
            'Cache-Control': 'no-cache',
            'SOAPAction': soap_action,
        }
        if token:
            expected_headers['Authorization'] = f'WRAP access_token="{token}"'
        self.assertDictEqual(request_data['headers'], expected_headers)

        self.assertXmlTreeEqual(
            request_data['envelope'], self.get_xml_tree_from_string(expected_envelope),
        )

    def test_token_renew_if_expired(self):
        fiel = self.fiel_certificate.sudo()
        with self.mx_external_setup(self.frozen_today, certificate=self.fiel_certificate):
            now = fields.Datetime.now()
            fiel.write({
                'l10n_mx_edi_sat_token': 'cached-token',
                'l10n_mx_edi_sat_token_expiry': now + timedelta(seconds=300),
            })
            self.assertEqual(fiel._l10n_mx_edi_get_sat_token(), 'cached-token')

            # Within the 30s safety buffer -> spent, so the getter fetches a new one.
            fiel.l10n_mx_edi_sat_token_expiry = now + timedelta(seconds=20)
            with self.mocked_send_cfdi_request(auth_response=self._build_auth_response(token='renewed-token')):
                self.assertEqual(fiel._l10n_mx_edi_get_sat_token(), 'renewed-token')
            self.assertEqual(fiel.l10n_mx_edi_sat_token, 'renewed-token')

    def test_authenticate_returns_a_token(self):
        """A successful authentication returns SAT token."""
        with self.mx_external_setup(self.frozen_today, certificate=self.fiel_certificate):
            with self.mocked_send_cfdi_request(self._build_auth_response(token='fresh-token')):
                result = self.env['l10n_mx_edi.sat.download.client']._authenticate(self.fiel_certificate)

        self.assertEqual(result['token'], 'fresh-token')

    def test_issued_download_returns_request_uuid(self):
        """An issued download request returns SAT request UUID."""
        with self.mx_external_setup(self.frozen_today, certificate=self.fiel_certificate):
            with self.mocked_send_cfdi_request(self._build_request_download_response(request_type='batch_issued')):
                result = self.env['l10n_mx_edi.sat.download.client']._request_download(
                    self.fiel_certificate,
                    'test-token',
                    request_type='issued',
                    receipt_type='I',
                    date_from='2025-01-01',
                    date_to='2025-01-31',
                )

        self.assertEqual(result['request_uuid'], DEFAULT_REQUEST_UUID)

    def test_folio_download_returns_request_uuid(self):
        """A folio download request returns the SAT request UUID."""
        with self.mx_external_setup(self.frozen_today, certificate=self.fiel_certificate):
            with self.mocked_send_cfdi_request(self._build_request_download_response(request_type='folio')):
                result = self.env['l10n_mx_edi.sat.download.client']._request_download(
                    self.fiel_certificate,
                    'test-token',
                    request_type='folio',
                    cfdi_uuid='8CA06290-4800-4F93-8B1B-25B208BB1AFF',
                )

        self.assertEqual(result['request_uuid'], DEFAULT_REQUEST_UUID)

    def test_verify_then_download_package(self):
        """Verify returns the package list, and downloading returns the package bytes."""
        with self.mx_external_setup(self.frozen_today, certificate=self.fiel_certificate):
            with self.mocked_send_cfdi_request(self._build_verification_response()):
                verify_result = self.env['l10n_mx_edi.sat.download.client']._verify_status(
                    self.fiel_certificate, 'test-token', DEFAULT_REQUEST_UUID,
                )
            self.assertEqual(verify_result['request_status'], '3')
            self.assertEqual(len(verify_result['package_uuids']), 1)

            with self.mocked_send_cfdi_request(self._build_package_download_response(package_zip=self.default_cfdi_package_raw)):
                download_result = self.env['l10n_mx_edi.sat.download.client']._download_package(
                    self.fiel_certificate, 'test-token', 'some-package-uuid',
                )
            self.assertEqual(download_result['package_content'], self.default_cfdi_package_raw)

    def test_request_faulty_response(self):
        with self.mx_external_setup(self.frozen_today, certificate=self.fiel_certificate):
            with self.mocked_send_cfdi_request(self._build_fault_response()):
                with self.assertRaises(UserError):
                    self.env['l10n_mx_edi.sat.download.client']._verify_status(
                        self.fiel_certificate, 'test-token', DEFAULT_REQUEST_UUID,
                    )

    def _request_download(self):
        return self.env['l10n_mx_edi.sat.download.client']._request_download(
            self.fiel_certificate,
            'test-token',
            request_type='issued',
            receipt_type='I',
            date_from='2025-01-01',
            date_to='2025-01-31',
        )

    def test_request_errors(self):
        cases = [
            {'http_status': 401},
            {'http_status': 403},
            {'http_status': 500},
            {'http_status': 429},
            {'http_status': 408},
            {'http_status': 404},
            {'error': RequestsTimeout('slow')},
            {'error': RequestsConnectionError('refused')},
            {'error': RequestException('boom')},
        ]
        with self.mx_external_setup(self.frozen_today, certificate=self.fiel_certificate):
            for mock_kwargs in cases:
                with self.subTest(mock_kwargs=mock_kwargs), \
                     self.mocked_failed_cfdi_request(**mock_kwargs):
                    with self.assertRaises(UserError):
                        self._request_download()

    def test_unprocessed_codes(self):
        """SAT could not read the call, so it never ruled on the criteria."""
        with self.mx_external_setup(self.frozen_today, certificate=self.fiel_certificate):
            for code in SAT_UNPROCESSED_CODE_MAP:
                with self.subTest(code=code), self.mocked_send_cfdi_request(
                    self._build_request_download_response(status_code=code),
                ):
                    with self.assertRaises(UserError):
                        self._request_download()

    def test_invalid_response(self):
        """An empty or unparseable SAT reply is no answer at all."""
        SatDownloadClient = self.env['l10n_mx_edi.sat.download.client']

        for content in (b'', b'not-xml'):
            with self.subTest(content=content):
                response = MagicMock(content=content)
                with self.assertRaises(UserError):
                    SatDownloadClient._process_response(response, './/{*}AutenticaResult')

    def test_invalid_service(self):
        """Test that an invalid service raises an error"""
        with self.assertRaises(UserError):
            self.env['l10n_mx_edi.sat.download.client']._send_request(
                service='not_valid_service',
                request_values={},
                certificate=self.fiel_certificate,
            )

    def test_unknown_request_type_is_rejected(self):
        """Asking for a request type SAT doesn't support fails."""
        with self.assertRaises(UserError):
            self.env['l10n_mx_edi.sat.download.client']._request_download(
                self.fiel_certificate, 'test-token', request_type='not-a-request_type',
            )

    def test_authenticate_envelope(self):
        """The authentication call signs a WS-Security Timestamp and carries no token."""
        uuid = '11111111-2222-3333-4444-555555555555'
        with self.mx_external_setup(self.frozen_today, certificate=self.fiel_certificate), \
             patch(f'{L10n_Mx_EdiSatDownloadClient.__module__}.uuid4', return_value=uuid), \
             self.mocked_send_cfdi_request(self._build_auth_response(token='fresh-token')) as mocked_post:
            self.env['l10n_mx_edi.sat.download.client']._authenticate(self.fiel_certificate)

        expected = f"""
            <s:Envelope xmlns:o="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
                        xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"
                        xmlns:u="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
                <s:Header>
                    <o:Security s:mustUnderstand="1">
                        <u:Timestamp u:Id="_0">
                            <u:Created>2025-06-15T00:00:00.000000Z</u:Created>
                            <u:Expires>2025-06-15T00:10:00.000000Z</u:Expires>
                        </u:Timestamp>
                        <o:BinarySecurityToken u:Id="uuid-{uuid}-4"
                            ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3"
                            EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary">___ignore___</o:BinarySecurityToken>
                        <Signature xmlns="http://www.w3.org/2000/09/xmldsig#">
                            <SignedInfo>
                                <CanonicalizationMethod Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#"/>
                                <SignatureMethod Algorithm="http://www.w3.org/2000/09/xmldsig#rsa-sha1"/>
                                <Reference URI="#_0">
                                    <Transforms>
                                        <Transform Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#"/>
                                    </Transforms>
                                    <DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha1"/>
                                    <DigestValue>___ignore___</DigestValue>
                                </Reference>
                            </SignedInfo>
                            <SignatureValue>___ignore___</SignatureValue>
                            <KeyInfo>
                                <o:SecurityTokenReference>
                                    <o:Reference URI="#uuid-{uuid}-4"
                                        ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3"/>
                                </o:SecurityTokenReference>
                            </KeyInfo>
                        </Signature>
                    </o:Security>
                </s:Header>
                <s:Body>
                    <Autentica xmlns="http://DescargaMasivaTerceros.gob.mx"/>
                </s:Body>
            </s:Envelope>
        """
        self._assert_request_payload(
            mocked_post,
            service_url=f'{SAT_REQUEST_DOWNLOAD_URL}Autenticacion/Autenticacion.svc',
            soap_action='http://DescargaMasivaTerceros.gob.mx/IAutenticacion/Autentica',
            expected_envelope=expected,
        )

    def test_request_download_issued_envelope(self):
        """An issued request asks by RfcEmisor, over whole days."""
        with self.mx_external_setup(self.frozen_today, certificate=self.fiel_certificate), \
             self.mocked_send_cfdi_request(self._build_request_download_response()) as mocked_post:
            self.env['l10n_mx_edi.sat.download.client']._request_download(
                self.fiel_certificate, 'test-token', request_type='issued',
                receipt_type='I', date_from='2025-01-01', date_to='2025-01-31',
            )

        expected = f"""
            <s:Envelope xmlns:des="http://DescargaMasivaTerceros.sat.gob.mx"
                        xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"
                        xmlns:xd="http://www.w3.org/2000/09/xmldsig#">
                <s:Header/>
                <s:Body>
                    <des:SolicitaDescargaEmitidos>
                        <des:solicitud EstadoComprobante="Vigente"
                                       FechaInicial="2025-01-01T00:00:00" FechaFinal="2025-01-31T23:59:59"
                                       RfcEmisor="{self.request_rfc}"
                                       TipoComprobante="I" TipoSolicitud="CFDI">
                            {self.expected_signature_xml}
                        </des:solicitud>
                    </des:SolicitaDescargaEmitidos>
                </s:Body>
            </s:Envelope>
        """
        self._assert_request_payload(
            mocked_post,
            service_url=f'{SAT_REQUEST_DOWNLOAD_URL}SolicitaDescargaService.svc',
            soap_action='http://DescargaMasivaTerceros.sat.gob.mx/ISolicitaDescargaService/SolicitaDescargaEmitidos',
            expected_envelope=expected,
            token='test-token',
        )

    def test_request_download_received_envelope(self):
        """A received request is the issued one, asking by RfcReceptor instead."""
        with self.mx_external_setup(self.frozen_today, certificate=self.fiel_certificate), \
             self.mocked_send_cfdi_request(self._build_request_download_response(request_type='batch_received')) as mocked_post:
            self.env['l10n_mx_edi.sat.download.client']._request_download(
                self.fiel_certificate, 'test-token', request_type='received',
                receipt_type='I', date_from='2025-01-01', date_to='2025-01-31',
            )

        expected = f"""
            <s:Envelope xmlns:des="http://DescargaMasivaTerceros.sat.gob.mx"
                        xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"
                        xmlns:xd="http://www.w3.org/2000/09/xmldsig#">
                <s:Header/>
                <s:Body>
                    <des:SolicitaDescargaRecibidos>
                        <des:solicitud EstadoComprobante="Vigente"
                                       FechaInicial="2025-01-01T00:00:00" FechaFinal="2025-01-31T23:59:59"
                                       TipoComprobante="I" TipoSolicitud="CFDI"
                                       RfcReceptor="{self.request_rfc}">
                            {self.expected_signature_xml}
                        </des:solicitud>
                    </des:SolicitaDescargaRecibidos>
                </s:Body>
            </s:Envelope>
        """
        self._assert_request_payload(
            mocked_post,
            service_url=f'{SAT_REQUEST_DOWNLOAD_URL}SolicitaDescargaService.svc',
            soap_action='http://DescargaMasivaTerceros.sat.gob.mx/ISolicitaDescargaService/SolicitaDescargaRecibidos',
            expected_envelope=expected,
            token='test-token',
        )

    def test_request_download_folio_envelope(self):
        """A folio request carries the fiscal folio and no date range."""
        with self.mx_external_setup(self.frozen_today, certificate=self.fiel_certificate), \
             self.mocked_send_cfdi_request(self._build_request_download_response(request_type='folio')) as mocked_post:
            self.env['l10n_mx_edi.sat.download.client']._request_download(
                self.fiel_certificate, 'test-token', request_type='folio', cfdi_uuid=DEFAULT_CFDI_UUID,
            )

        expected = f"""
            <s:Envelope xmlns:des="http://DescargaMasivaTerceros.sat.gob.mx"
                        xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"
                        xmlns:xd="http://www.w3.org/2000/09/xmldsig#">
                <s:Header/>
                <s:Body>
                    <des:SolicitaDescargaFolio>
                        <des:solicitud Folio="{DEFAULT_CFDI_UUID}" RfcSolicitante="{self.request_rfc}">
                            {self.expected_signature_xml}
                        </des:solicitud>
                    </des:SolicitaDescargaFolio>
                </s:Body>
            </s:Envelope>
        """
        self._assert_request_payload(
            mocked_post,
            service_url=f'{SAT_REQUEST_DOWNLOAD_URL}SolicitaDescargaService.svc',
            soap_action='http://DescargaMasivaTerceros.sat.gob.mx/ISolicitaDescargaService/SolicitaDescargaFolio',
            expected_envelope=expected,
            token='test-token',
        )

    def test_verify_status_envelope(self):
        """Verifying quotes back the request UUID SAT handed out."""
        with self.mx_external_setup(self.frozen_today, certificate=self.fiel_certificate), \
             self.mocked_send_cfdi_request(self._build_verification_response()) as mocked_post:
            self.env['l10n_mx_edi.sat.download.client']._verify_status(
                self.fiel_certificate, 'test-token', DEFAULT_REQUEST_UUID,
            )

        expected = f"""
            <s:Envelope xmlns:des="http://DescargaMasivaTerceros.sat.gob.mx"
                        xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"
                        xmlns:xd="http://www.w3.org/2000/09/xmldsig#">
                <s:Header/>
                <s:Body>
                    <des:VerificaSolicitudDescarga>
                        <des:solicitud IdSolicitud="{DEFAULT_REQUEST_UUID}" RfcSolicitante="{self.request_rfc}">
                            {self.expected_signature_xml}
                        </des:solicitud>
                    </des:VerificaSolicitudDescarga>
                </s:Body>
            </s:Envelope>
        """
        self._assert_request_payload(
            mocked_post,
            service_url=f'{SAT_REQUEST_DOWNLOAD_URL}VerificaSolicitudDescargaService.svc',
            soap_action='http://DescargaMasivaTerceros.sat.gob.mx/IVerificaSolicitudDescargaService/VerificaSolicitudDescarga',
            expected_envelope=expected,
            token='test-token',
        )

    def test_download_package_envelope(self):
        """The package download goes to the other host, and gets a longer timeout."""
        with self.mx_external_setup(self.frozen_today, certificate=self.fiel_certificate), \
             self.mocked_send_cfdi_request(self._build_package_download_response(package_zip=b'zip')) as mocked_post:
            self.env['l10n_mx_edi.sat.download.client']._download_package(
                self.fiel_certificate, 'test-token', 'some-package-uuid',
            )

        expected = f"""
            <s:Envelope xmlns:des="http://DescargaMasivaTerceros.sat.gob.mx"
                        xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"
                        xmlns:xd="http://www.w3.org/2000/09/xmldsig#">
                <s:Header/>
                <s:Body>
                    <des:PeticionDescargaMasivaTercerosEntrada>
                        <des:peticionDescarga IdPaquete="some-package-uuid" RfcSolicitante="{self.request_rfc}">
                            {self.expected_signature_xml}
                        </des:peticionDescarga>
                    </des:PeticionDescargaMasivaTercerosEntrada>
                </s:Body>
            </s:Envelope>
        """
        self._assert_request_payload(
            mocked_post,
            service_url=f'{SAT_PACKAGE_DOWNLOAD_URL}DescargaMasivaService.svc',
            soap_action='http://DescargaMasivaTerceros.sat.gob.mx/IDescargaMasivaTercerosService/Descargar',
            expected_envelope=expected,
            token='test-token',
        )

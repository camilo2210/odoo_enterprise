import base64
import hashlib
import logging
import requests

from copy import deepcopy
from datetime import datetime, time, timedelta, timezone
from lxml import etree
from requests.exceptions import HTTPError, RequestException
from uuid import uuid4

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import cleanup_xml_node, LazyTranslate
from odoo.tools.urls import urljoin

from odoo.addons.l10n_mx_edi.models.l10n_mx_edi_document import CFDI_DATE_FORMAT

_lt = LazyTranslate(__name__)
_logger = logging.getLogger(__name__)

SAT_TOKEN_VALIDITY = 10
SAT_AUTHENTICATION_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

SAT_SUCCESS_STATUS_CODE = '5000'

SAT_REQUEST_DOWNLOAD_URL = "https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/"
SAT_PACKAGE_DOWNLOAD_URL = "https://cfdidescargamasiva.clouda.sat.gob.mx/"

ALLOWED_SAT_SERVICES = frozenset([
    'authenticate',
    'request_download_issued',
    'request_download_received',
    'request_download_folio',
    'verify_status',
    'download_package'
])

SAT_UNPROCESSED_CODE_MAP = {
    '300': _lt("Invalid user."),
    '301': _lt("Malformed XML. The request carries invalid information, such as an unknown RFC."),
    '302': _lt("Malformed seal."),
    '303': _lt("The seal does not match the requesting RFC."),
    '304': _lt("Certificate revoked or expired."),
    '305': _lt("Invalid certificate."),
    '404': _lt("SAT reported an uncontrolled error."),
}

SAT_REQUEST_CODE_MAP = {
    '5001': _lt("Unauthorized third party. You cannot download receipts that do not belong to you."),
    '5002': _lt("Reached lifetime limit for requests for packages with same criteria."),
    '5005': _lt("A request with the same criteria already exists."),
    '5012': _lt("Download of cancelled documents is not allowed."),
}
SAT_VERIFY_CODE_MAP = {
    '5000': _lt("Request Accepted"),
    '5003': _lt("The request exceeds the maximum number of results per request type."),
    '5004': _lt("SAT found no information for this request."),
    '5011': _lt("Reached the daily download limit for this fiscal folio."),
}
SAT_DOWNLOAD_CODE_MAP = {
    '5004': _lt("SAT found no information for the requested package."),
    '5007': _lt("The requested package no longer exists. A package only lives for 72hrs."),
    '5008': _lt("Reached maximum of downloads allowed. A package can only be downloaded twice."),
}


class L10n_Mx_EdiSatDownloadClient(models.AbstractModel):
    """Client for SAT's four CFDI mass-download services.

    The envelopes are built from QWeb templates and signed here, instead of through a WSDL client.
    `zeep` would build the bodies but none of the security material: it implements no
    WS-SecurityPolicy, so the Security header, the Timestamp, the certificate token and the
    signature stay ours either way, and the code would not get any simpler. It would also fetch each
    service's contract on every call, and for the package download there is no contract to fetch, so
    we would still need to build and maintain a WSDL ourselves. A few small templates and no extra
    dependency is a better trade.
    """
    _name = 'l10n_mx_edi.sat.download.client'
    _description = "SAT CFDI Mass Download - SOAP Transport"

    @api.model
    def _get_sat_token_timestamps(self):
        """Generate timestamps for SAT authentication token.
        :return: A tuple with the timestamps as datetime objects and string in UTC timezone
        """
        create_date_utc = datetime.now(timezone.utc)
        expire_date_utc = create_date_utc + timedelta(minutes=SAT_TOKEN_VALIDITY)
        create_date_str = create_date_utc.strftime(SAT_AUTHENTICATION_DATE_FORMAT)
        expire_date_str = expire_date_utc.strftime(SAT_AUTHENTICATION_DATE_FORMAT)
        return create_date_utc, expire_date_utc, create_date_str, expire_date_str

    @api.model
    def _authenticate(self, certificate):
        """Authenticate against the SAT authentication service.

        Fetch token required to use other services from SAT Massive Download Service.

        :param certificate: certificate.certificate record (FIEL) used to sign the envelope.
        :return: The token string.
        """
        _create_date_utc, expire_date_utc, create_date_str, expire_date_str = self._get_sat_token_timestamps()
        request_values = {
            'create_date_str': create_date_str,
            'expire_date_str': expire_date_str,
            'uuid': f'uuid-{uuid4()}-4',
            'is_auth': True,
        }

        response = self._send_request(service='authenticate', request_values=request_values, certificate=certificate)

        result_node = etree.fromstring(response['result']['content'])
        if not result_node.text:
            raise UserError(_("SAT answered without a token."))
        return {'token': result_node.text, 'expiry_date': expire_date_utc}

    @api.model
    def _request_download(self, certificate, token, *, request_type, receipt_type=None, date_from=None, date_to=None, cfdi_uuid=None):
        """Submit a CFDI download request to the SAT request-download service.

        :param certificate: certificate.certificate record (FIEL) used to sign the envelope.
        :param token: SAT auth token string.
        :param request_type: 'issued', 'received', or 'folio'.
        :param receipt_type: 'I'/'E' (required for 'issued'/'received').
        :param date_from: Date, or ISO date string (required for 'issued'/'received').
        :param date_to: Date, or ISO date string (required for 'issued'/'received').
        :param cfdi_uuid: Fiscal folio (required for 'folio').
        :return: {'code_status': str|None, 'request_uuid': str|None, 'message': str|None}
        """
        if request_type not in ('folio', 'issued', 'received'):
            raise UserError(
                _('SAT service only allows requests for a single Fiscal Folio or Issued/Received documents.'),
            )

        if request_type == 'folio':
            request_values = {'service_type': 'folio', 'cfdi_uuid': cfdi_uuid}
        else:
            date_from = fields.Date.to_date(date_from)
            date_to = fields.Date.to_date(date_to)
            request_values = {
                'service_type': request_type,
                'receipt_state': 'Vigente',
                'receipt_type': receipt_type,
                'request_type': 'CFDI',
                'emission_date_from': date_from and datetime.combine(date_from, time.min).strftime(CFDI_DATE_FORMAT),
                'emission_date_to': date_to and datetime.combine(date_to, time(23, 59, 59)).strftime(CFDI_DATE_FORMAT),
            }

        response = self._send_request(
            service='request_download_' + request_type,
            request_values=request_values,
            certificate=certificate,
            token=token,
        )

        result_data = response['result']['data']
        code_status = result_data.get('CodEstatus')
        service_message = result_data.get('Mensaje')
        request_uuid = result_data.get('IdSolicitud')
        if code_status in SAT_UNPROCESSED_CODE_MAP:
            raise UserError(SAT_UNPROCESSED_CODE_MAP[code_status])
        if code_status == SAT_SUCCESS_STATUS_CODE and not request_uuid:
            raise UserError(_(
                "SAT returned a success code but no request UUID. Service responded with: %s",
                service_message
            ))

        return {
            'code_status': code_status,
            'request_uuid': request_uuid,
            'message': SAT_REQUEST_CODE_MAP.get(code_status) or service_message,
        }

    @api.model
    def _verify_status(self, certificate, token, request_uuid):
        """Verify the status of a pending SAT download request.

        :param certificate: certificate.certificate record (FIEL) used to sign the envelope.
        :param token: SAT auth token string.
        :param request_uuid: The SAT request UUID to verify.
        :return: {'request_status': str|None, 'code_status': str|None,
                  'code_request_status': str|None, 'message': str|None, 'package_uuids': list[str]}
        """
        response = self._send_request(
            service='verify_status',
            request_values={'request_uuid': request_uuid},
            certificate=certificate,
            token=token,
        )

        result_data = response['result']['data']
        request_status = result_data.get('EstadoSolicitud')
        code_status = result_data.get('CodEstatus')
        code_request_status = result_data.get('CodigoEstadoSolicitud')
        service_message = result_data.get('Mensaje')
        # Verification response returns two codes that can contain information of
        # the verification situation. We process both.
        if code_status in SAT_UNPROCESSED_CODE_MAP:
            raise UserError(SAT_UNPROCESSED_CODE_MAP[code_status])
        if code_request_status in SAT_UNPROCESSED_CODE_MAP:
            raise UserError(SAT_UNPROCESSED_CODE_MAP[code_request_status])
        no_info_message = _('No information available')
        details = []
        if code_status:
            info = SAT_VERIFY_CODE_MAP.get(code_status, no_info_message)
            details.append(_("- Request Status %(code)s: %(info)s", code=code_status, info=info))
        if code_request_status:
            info = SAT_VERIFY_CODE_MAP.get(code_request_status, no_info_message)
            details.append(_("- Verification Status %(code)s: %(info)s", code=code_request_status, info=info))
        if service_message:
            details.append(_("- Extra details: %(message)s", message=service_message or no_info_message))

        # package ids are outside the result node
        response_node = etree.fromstring(response['content'])
        return {
            'request_status': request_status,
            'code_status': code_status,
            'code_request_status': code_request_status,
            'message': _(
                "SAT Verification Service responded with status %(request_status)s: \n%(details)s",
                request_status=request_status, status_message='', details='\n'.join(details) or no_info_message,
            ),
            'package_uuids': [node.text for node in response_node.xpath('.//*[local-name()="IdsPaquetes"]')],
        }

    @api.model
    def _download_package(self, certificate, token, package_uuid):
        """Download a ready package from the SAT package-download service.

        :param certificate: certificate.certificate record (FIEL) used to sign the envelope.
        :param token: SAT auth token string.
        :param package_uuid: The SAT package UUID to download.
        :return: {'code_status': str|None, 'message': str|None, 'package_content': bytes|None}
        """
        response = self._send_request(
            service='download_package',
            request_values={'package_uuid': package_uuid},
            certificate=certificate,
            token=token,
            timeout=150,
        )

        result_data = response['result']['data']
        code_status = result_data.get('CodEstatus')
        message = result_data.get('Mensaje')
        if code_status in SAT_UNPROCESSED_CODE_MAP:
            raise UserError(SAT_UNPROCESSED_CODE_MAP[code_status])

        package_node = etree.fromstring(response['content']).find('.//{*}Paquete')
        package_content = base64.b64decode(package_node.text) if package_node is not None and package_node.text else None
        return {
            'code_status': code_status,
            'message': SAT_DOWNLOAD_CODE_MAP.get(code_status) or message,
            'package_content': package_content,
        }

    @api.model
    def _get_request_headers(self, soap_action, token=None):
        """Build HTTP headers for a SAT service request.

        :param soap_action: SOAP action of the SAT service.
        :param token: Optional token in case of a non-authentication request.
        :return: A dict containing the headers for the SAT service request.
        """
        headers = {
            "Content-type": 'text/xml;charset="UTF-8"',
            "Accept": "text/xml",
            "Cache-Control": "no-cache",
        }

        if token:
            headers['Authorization'] = f'WRAP access_token="{token}"'
            headers['SOAPAction'] = f"http://DescargaMasivaTerceros.sat.gob.mx/{soap_action}"
        else:
            headers['SOAPAction'] = f"http://DescargaMasivaTerceros.gob.mx/{soap_action}"

        return headers

    @api.model
    def _get_signed_envelope(self, qweb_template, digest_xpath, request_values, certificate):
        """Build and sign the SOAP envelope using the FIEL certificate.

        :param qweb_template: xml_id of the template used to generate the SOAP envelope.
        :param digest_xpath: envelope path used to compute the digest.
        :param request_values: The values required to build the SOAP envelope.
        :param certificate: certificate.certificate record used to sign the envelope.
        :return: The signed envelope bytes.
        """
        values = {
            **request_values,
            'certificate_values': {
                'x509_certificate': certificate.sudo()._get_der_certificate_bytes(formatting='base64').decode(),
                'request_rfc': certificate.sudo().company_id.partner_id.commercial_partner_id.vat,
            },
        }
        envelope = self.env["ir.qweb"]._render(qweb_template, values=values)

        envelope_etree = cleanup_xml_node(envelope, remove_blank_nodes=False)

        # Copy envelope and remove Signature node so digest is computed on clean content.
        envelope_copy = deepcopy(envelope_etree)
        signature_node = envelope_copy.find(".//{*}Signature")
        signature_node.getparent().remove(signature_node)

        # Generate and set digest (SHA1 hash of canonicalized element).
        digest_node = envelope_copy.find(digest_xpath)
        digest_str = etree.tostring(digest_node, method="c14n", exclusive=True)
        digest_value = base64.b64encode(hashlib.sha1(digest_str).digest())
        envelope_etree.find(".//{*}DigestValue").text = digest_value

        # Sign envelope (SHA1 signature of canonicalized SignedInfo).
        signed_info_node = envelope_etree.find(".//{*}SignedInfo")
        signature_str = etree.tostring(signed_info_node, method="c14n", exclusive=True)
        signature_value = certificate.sudo()._sign(
            signature_str, hashing_algorithm="sha1", formatting="base64"
        )
        envelope_etree.find(".//{*}SignatureValue").text = signature_value
        return etree.tostring(envelope_etree, encoding="UTF-8")

    @api.model
    def _get_service_values(self, service):
        if service not in ALLOWED_SAT_SERVICES:
            raise UserError(_("Service %s is not valid.", service))

        service_values = {
            'authenticate': {
                'service_url': urljoin(SAT_REQUEST_DOWNLOAD_URL, 'Autenticacion/Autenticacion.svc'),
                'qweb_template': 'l10n_mx_edi.l10n_mx_sat_authentification_template',
                'digest_xpath': './/{*}Timestamp',
                'soap_action': 'IAutenticacion/Autentica',
                'result_xpath': './/{*}AutenticaResult',
            },
            'request_download_issued': {
                'service_url': urljoin(SAT_REQUEST_DOWNLOAD_URL, 'SolicitaDescargaService.svc'),
                'qweb_template': 'l10n_mx_edi.l10n_mx_sat_download_request_template',
                'digest_xpath': './/{*}SolicitaDescargaEmitidos',
                'soap_action': 'ISolicitaDescargaService/SolicitaDescargaEmitidos',
                'result_xpath': './/{*}SolicitaDescargaEmitidosResult',
            },
            'request_download_received': {
                'service_url': urljoin(SAT_REQUEST_DOWNLOAD_URL, 'SolicitaDescargaService.svc'),
                'qweb_template': 'l10n_mx_edi.l10n_mx_sat_download_request_template',
                'digest_xpath': './/{*}SolicitaDescargaRecibidos',
                'soap_action': 'ISolicitaDescargaService/SolicitaDescargaRecibidos',
                'result_xpath': './/{*}SolicitaDescargaRecibidosResult',
            },
            'request_download_folio': {
                'service_url': urljoin(SAT_REQUEST_DOWNLOAD_URL, 'SolicitaDescargaService.svc'),
                'qweb_template': 'l10n_mx_edi.l10n_mx_sat_download_request_template',
                'digest_xpath': './/{*}SolicitaDescargaFolio',
                'soap_action': 'ISolicitaDescargaService/SolicitaDescargaFolio',
                'result_xpath': './/{*}SolicitaDescargaFolioResult',
            },
            'verify_status': {
                'service_url': urljoin(SAT_REQUEST_DOWNLOAD_URL, 'VerificaSolicitudDescargaService.svc'),
                'qweb_template': 'l10n_mx_edi.l10n_mx_sat_download_verification_template',
                'digest_xpath': './/{*}VerificaSolicitudDescarga',
                'soap_action': 'IVerificaSolicitudDescargaService/VerificaSolicitudDescarga',
                'result_xpath': './/{*}VerificaSolicitudDescargaResult',
            },
            'download_package': {
                'service_url': urljoin(SAT_PACKAGE_DOWNLOAD_URL, 'DescargaMasivaService.svc'),
                'qweb_template': 'l10n_mx_edi.l10n_mx_sat_download_package_template',
                'digest_xpath': './/{*}PeticionDescargaMasivaTercerosEntrada',
                'soap_action': 'IDescargaMasivaTercerosService/Descargar',
                'result_xpath': './/{*}respuesta',
            },
        }

        return service_values[service]

    @api.model
    def _send_request(self, service, request_values, certificate, token=None, timeout=60):
        service_values = self._get_service_values(service)
        data = self._get_signed_envelope(service_values['qweb_template'], service_values['digest_xpath'], request_values, certificate)
        headers = self._get_request_headers(service_values['soap_action'], token=token)

        try:
            response = requests.post(service_values['service_url'], data=data, headers=headers, timeout=timeout)
            response.raise_for_status()
        except HTTPError as err:
            status_code = err.response.status_code if err.response is not None else None
            _logger.warning('Request to SAT service failed with code %s. Error: %s', status_code, err)
            if status_code in (401, 403):
                raise UserError(_(
                    'SAT refused the credentials. Check that your e.firma certificate is valid '
                    'for your RFC.'
                )) from err
            raise UserError(
                _('SAT answered with an unexpected error: \n%s', str(err)),
            ) from err
        except RequestException as err:
            _logger.warning('Could not reach SAT service %s: %s', service_values['service_url'], err)
            raise UserError(_(
                'SAT could not be reached. Try again later, and contact your administrator if it '
                'keeps happening.'
            )) from err

        return self._process_response(response, service_values['result_xpath'])

    @api.model
    def _process_response(self, soap_response, result_xpath):
        """Process a SAT service response and handle generic errors.

        :param soap_response: requests.Response from a SAT SOAP call.
        :param result_xpath: path to the node the calling service answers with.
        :return: {'response_tree': etree, 'result_node': etree}
        """
        if soap_response is None or not soap_response.content:
            raise UserError(_('SAT returned an empty response.'))

        try:
            response_tree = etree.fromstring(soap_response.content)
        except etree.XMLSyntaxError as err:
            raise UserError(_('SAT response could not be decoded: %s', soap_response.content)) from err

        errors = []
        error_code = response_tree.findtext(".//{*}ErrorCode")
        if error_code is not None:
            error_msg = response_tree.findtext(".//{*}ErrorMessage")
            errors.append(_("Response Error - Code: %(code)s %(msg)s", code=error_code, msg=error_msg or ""))
        fault_string = response_tree.findtext(".//{*}faultstring")
        if fault_string is not None:
            errors.append(_("Fault Error - %(msg)s", msg=fault_string))

        if errors:
            raise UserError(_(
                'SAT answered with the following errors\n: - %s', '\n - '.join(errors)
            ))

        result_node = response_tree.find(result_xpath)
        if result_node is None:
            raise UserError(_(
                'SAT answered without the expected result: \n%s',
                etree.tostring(response_tree, pretty_print=True),
            ))
        result_data = {
            'content': etree.tostring(result_node, encoding="UTF-8"),
            'data': dict(result_node.attrib),
        }
        return {"content": soap_response.content, "result": result_data}

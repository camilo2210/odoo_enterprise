import base64
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from tempfile import NamedTemporaryFile

import requests
import xmlsec
from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding
from lxml import etree

from odoo.tools import zeep
from odoo.tools.zeep import Client, ns, wsse, wsa

DIGIPOORT_HOST = 'dgp2.procesinfrastructuur.nl'
DIGIPOORT_PREPROD_HOST = 'preprod-dgp2.procesinfrastructuur.nl'
DIGIPOORT_SERVICE_BASE = 'wus.digipoort.logius.nl'
DIGIPOORT_PREPROD_SERVICE_BASE = 'wus.preproductie.digipoort.logius.nl'
REPORT_TYPE_CONFIG = {
    'tax_report': ('Omzetbelasting', 'TaxReport.xbrl'),
    'tax_correction': ('OBSUP', 'TaxReport.xbrl'),
    'ec_sales_list': ('ICP', 'ICPReport.xbrl'),
}


@contextmanager
def temporary_certificate_files(server_root_certificate, certificate, private_key):
    with (
        NamedTemporaryFile() as server_root_file,
        NamedTemporaryFile() as client_cert_file,
        NamedTemporaryFile() as client_pkey_file,
    ):
        for temporary_file, content in (
            (server_root_file, server_root_certificate),
            (client_cert_file, certificate),
            (client_pkey_file, private_key),
        ):
            temporary_file.write(content)
            temporary_file.flush()
        yield server_root_file.name, client_cert_file.name, client_pkey_file.name


def get_digipoort_service_base(is_test):
    return DIGIPOORT_PREPROD_SERVICE_BASE if is_test else DIGIPOORT_SERVICE_BASE


def get_digipoort_host(is_test):
    return DIGIPOORT_PREPROD_HOST if is_test else DIGIPOORT_HOST


def extract_fault_description(fault):
    if fault.detail is None:
        return str(fault)
    fault_descriptions = [
        description.text
        for description in fault.detail.xpath('.//*[local-name() = "foutbeschrijving"]')
        if description.text
    ]
    return '\n'.join(fault_descriptions) if fault_descriptions else str(fault)


def _get_aanlever_kwargs(report_type, report_file, vat, factory):
    berichtsoort, bestandsnaam = REPORT_TYPE_CONFIG[report_type]
    vat_number = vat.removeprefix('NL') if isinstance(vat, str) else vat
    report_payload = report_file.encode() if isinstance(report_file, str) else report_file
    return {
        'berichtsoort': berichtsoort,
        'aanleverkenmerk': wsse.utils.get_unique_id(),
        'identiteitBelanghebbende': factory.identiteitType(
            nummer=vat_number,
            type='BTW',
        ),
        'rolBelanghebbende': 'Bedrijf',
        'berichtInhoud': factory.berichtInhoudType(
            mimeType='application/xml',
            bestandsnaam=bestandsnaam,
            inhoud=report_payload,
        ),
        'autorisatieAdres': 'http://geenausp.nl',
    }


def _get_aanlever_operation_name(delivery_service):
    return 'aanlever' if hasattr(delivery_service, 'aanlever') else 'aanleveren'


def prepare_signed_xbrl_envelope(report_type, report_file, vat, certificate, private_key, server_root_certificate, is_test):
    with temporary_certificate_files(server_root_certificate, certificate, private_key) as (
        server_root_file, client_cert_file, client_pkey_file,
    ):
        wsdl = f'https://{get_digipoort_host(is_test)}/wus/2.0/aanleverservice/1.2?wsdl'
        service_address = f'https://{get_digipoort_service_base(is_test)}/wus/2.0/aanleverservice/1.2'
        delivery_client, delivery_service, raw_delivery_service = create_soap_client_logius(
            wsdl_address=wsdl,
            root_cert_file=server_root_file,
            client_cert_file=client_cert_file,
            client_pkey_file=client_pkey_file,
            client_cert=certificate,
            client_pkey=private_key,
            service_address=service_address,
            binary_security_token_index=0,
            return_raw_service=True,
        )
        factory = delivery_client.type_factory('ns0')
        operation_name = _get_aanlever_operation_name(delivery_service)
        envelope, http_headers = raw_delivery_service._binding._create(
            operation_name,
            (),
            _get_aanlever_kwargs(report_type, report_file, vat, factory),
            client=delivery_client._Client__obj,
            options=raw_delivery_service._binding_options,
        )
        return {
            'soap_envelope': base64.b64encode(etree.tostring(envelope)).decode(),
            'soap_action': http_headers.get('SOAPAction'),
        }


def create_soap_client_logius(
    wsdl_address,
    root_cert_file,
    client_cert_file,
    client_pkey_file,
    client_cert,
    client_pkey,
    service_address,
    binary_security_token_index=1,
    return_raw_service=False,
):
    session = requests.Session()
    session.cert = (client_cert_file, client_pkey_file)
    session.verify = root_cert_file
    signature = BinarySignatureTimestamp(
        client_pkey,
        client_cert,
        binary_security_token_index=binary_security_token_index,
    )
    client = Client(wsdl_address, wsse=signature, session=session, plugins=[WsaSBR()])
    service = next(iter(client._Client__obj.wsdl.services.values()))
    port = next(iter(service.ports.values()))
    service_proxy = client.create_service(port.binding.name, service_address)
    if return_raw_service:
        raw_service_proxy = client._Client__obj.create_service(port.binding.name, service_address)
        return client, service_proxy, raw_service_proxy
    return client, service_proxy


def _signature_prepare(envelope, key):
    soap_env = wsse.signature.detect_soap_env(envelope)
    signature = xmlsec.template.create(
        envelope,
        xmlsec.Transform.EXCL_C14N,
        xmlsec.Transform.RSA_SHA1,
    )

    key_info = xmlsec.template.ensure_key_info(signature)
    x509_data = xmlsec.template.add_x509_data(key_info)
    xmlsec.template.x509_data_add_issuer_serial(x509_data)
    xmlsec.template.x509_data_add_certificate(x509_data)

    security = wsse.utils.get_security_header(envelope)
    security.insert(0, signature)

    ctx = xmlsec.SignatureContext()
    ctx.key = key
    header = envelope.find(etree.QName(soap_env, 'Header'))
    for target in (
        envelope.find(etree.QName(soap_env, 'Body')),
        security.find(etree.QName(ns.WSU, 'Timestamp')),
        header.find(etree.QName(ns.WSA, 'Action')),
        header.find(etree.QName(ns.WSA, 'MessageID')),
        header.find(etree.QName(ns.WSA, 'To')),
        header.find(etree.QName(ns.WSA, 'ReplyTo')),
    ):
        wsse.signature._sign_node(ctx, signature, target)
    ctx.sign(signature)

    sec_token_ref = etree.SubElement(key_info, etree.QName(ns.WSSE, 'SecurityTokenReference'))
    return security, sec_token_ref, x509_data


def _sign_envelope_with_key_binary(envelope, key, cert_data, binary_security_token_index=1):
    security, sec_token_ref, x509_data = _signature_prepare(envelope, key)
    value_type_ns = 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3'
    encoding_type_ns = 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary'
    ref = etree.SubElement(
        sec_token_ref,
        etree.QName(ns.WSSE, 'Reference'),
        {'ValueType': value_type_ns},
    )
    ref_id = wsse.utils.get_unique_id()
    ref.set('URI', '#' + ref_id)
    bintok = etree.Element(
        etree.QName(ns.WSSE, 'BinarySecurityToken'),
        {etree.QName(ns.WSU, 'Id'): ref_id, 'ValueType': value_type_ns, 'EncodingType': encoding_type_ns},
    )
    x509_certificate = x509_data.find(etree.QName(ns.DS, 'X509Certificate'))
    if x509_certificate is not None and x509_certificate.text:
        bintok.text = x509_certificate.text
    else:
        certificate_der = x509.load_pem_x509_certificate(cert_data).public_bytes(Encoding.DER)
        bintok.text = base64.b64encode(certificate_der).decode()
    security.insert(binary_security_token_index, bintok)
    x509_data.getparent().remove(x509_data)


class BinarySignatureTimestamp(wsse.signature.MemorySignature):
    def __init__(
        self,
        key_data,
        cert_data,
        password=None,
        signature_method=None,
        digest_method=None,
        binary_security_token_index=1,
    ):
        super().__init__(key_data, cert_data, password, signature_method, digest_method)
        self._binary_security_token_index = binary_security_token_index

    def apply(self, envelope, headers):
        security = wsse.utils.get_security_header(envelope)
        created = datetime.now(timezone.utc).replace(tzinfo=None)
        expired = created + timedelta(seconds=10 * 60)

        timestamp = wsse.utils.WSU('Timestamp')
        timestamp.append(wsse.utils.WSU('Created', created.isoformat() + 'Z'))
        timestamp.append(wsse.utils.WSU('Expires', expired.isoformat() + 'Z'))
        security.append(timestamp)

        key = wsse.signature._make_sign_key(self.key_data, self.cert_data, self.password)
        _sign_envelope_with_key_binary(envelope, key, self.cert_data, self._binary_security_token_index)
        return envelope, headers


class WsaSBR(wsa.WsAddressingPlugin):
    _DIGIPOORT_ACTIONS = {
        'aanlever': 'http://logius.nl/digipoort/wus/2.0/aanleverservice/1.2/AanleverService/aanleverenRequest',
        'getStatussenProces': 'http://logius.nl/digipoort/wus/2.0/statusinformatieservice/1.2/StatusinformatieService/getStatussenProcesRequest',
    }

    def egress(self, envelope, http_headers, operation, binding_options):
        senvelope, shttp_headers = super().egress(envelope, http_headers, operation, binding_options)
        action = senvelope.xpath('//*[local-name() = "Action" and namespace-uri() = "%s"]' % ns.WSA)
        if action and not (action[0].text or '').strip() and operation.name in self._DIGIPOORT_ACTIONS:
            action[0].text = self._DIGIPOORT_ACTIONS[operation.name]
            shttp_headers['SOAPAction'] = f'"{action[0].text}"'
        header = zeep.wsdl.utils.get_or_create_header(senvelope)
        header.extend([wsa.WSA.ReplyTo(wsa.WSA.Address('http://www.w3.org/2005/08/addressing/anonymous'))])
        return senvelope, shttp_headers

import base64
from collections import Counter
import io
import requests
import zipfile

from contextlib import contextmanager
from datetime import datetime, timedelta
from freezegun import freeze_time
from lxml import etree
from unittest.mock import MagicMock, patch

from odoo import fields, Command
from odoo.tools import mute_logger

from odoo.addons.l10n_mx_edi.models.certificate_certificate import CertificateCertificate
from odoo.addons.l10n_mx_edi.models.l10n_mx_edi_sat_client import L10n_Mx_EdiSatDownloadClient
from odoo.addons.l10n_mx_edi.tests.common import TestMxEdiCommon

DEFAULT_REQUEST_UUID = '511789b3-0077-4e94-8401-8c96a5300073'
DEFAULT_CFDI_UUID = '8CA06290-4800-4F93-8B1B-25B208BB1AFF'
DEFAULT_CFDI_SAMPLE = 'cfdi_sample.xml'


class TestCfdiRequestCommon(TestMxEdiCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        with freeze_time(cls.frozen_today):
            cls.fiel_certificate = cls.env['certificate.certificate'].create({
                'name': 'Test FIEL',
                'content': cls.file_read('l10n_mx_edi/demo/pac_credentials/certificate.cer'),
                'private_key_id': cls.private_key.id,
                'scope': 'e_firma',
            })

        cls.fiel_certificate.write({
            'date_start': '2016-01-01',
            'date_end': '2018-01-01',
        })
        cls.company_data['company'].write({
            'l10n_mx_edi_certificate_ids': [Command.link(cls.fiel_certificate.id)],
        })

        cls.default_cfdi_package_raw = cls._create_sat_package_zip()
        cls.company_cron = cls.env.ref('l10n_mx_edi.ir_cron_l10n_mx_edi_create_company_request')
        cls.verify_cron = cls.env.ref('l10n_mx_edi.ir_cron_l10n_mx_edi_verify_requests')
        cls.download_cron = cls.env.ref('l10n_mx_edi.ir_cron_l10n_mx_edi_download_packages')
        cls.unpack_cron = cls.env.ref('l10n_mx_edi.ir_cron_l10n_mx_edi_unpack_packages')
        cls.import_cron = cls.env.ref('l10n_mx_edi.ir_cron_l10n_mx_edi_create_records_from_documents')

    @classmethod
    def _create_sat_package_zip(cls, data=None, emisor_rfc=None, receptor_rfc=None):
        """ZIP raw bytes mimicking a SAT mass-download CFDI payload."""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            files_content_list = cls._create_cfdi_samples(data, emisor_rfc=emisor_rfc, receptor_rfc=receptor_rfc)
            assert bool(files_content_list), "Expected a list of raw cfdi content"
            for file_content in files_content_list:
                zinfo = zipfile.ZipInfo(file_content['file_name'])
                zinfo.compress_type = zipfile.ZIP_DEFLATED
                zf.writestr(file_content['file_name'], file_content['raw_bytes'])

        return buffer.getvalue()

    @classmethod
    def _create_cfdi_samples(cls, data, file_name=DEFAULT_CFDI_SAMPLE, emisor_rfc=None, receptor_rfc=None):
        cfdi_sample = cls.file_read(f'{cls.test_module}/tests/test_files/samples/{file_name}').content
        if not data:
            return [{'raw_bytes': cfdi_sample, 'file_name': f'{DEFAULT_CFDI_UUID}.xml'}]

        assert all(isinstance(d, tuple) and len(d) == 2 for d in data), "Expected a list of tuples with the UUID and receipt type to use"
        root = etree.fromstring(cfdi_sample)  # cfdi:Comprobante root node
        fiscal_sign_node = root.find('.//{*}TimbreFiscalDigital')
        assert root is not None and fiscal_sign_node is not None, "Expected a valid signed cfdi"
        if emisor_rfc:
            root.find('.//{*}Emisor').set('Rfc', emisor_rfc)
        if receptor_rfc:
            root.find('.//{*}Receptor').set('Rfc', receptor_rfc)
        cfdi_samples = []
        same_name_count = Counter()
        for d in data:
            uuid, receipt_type = d
            root.set('TipoDeComprobante', receipt_type)
            fiscal_sign_node.set('UUID', uuid)
            # avoid duplicate name user warning when creating zip
            name = f'{uuid + (f'({same_name_count[uuid]})' if same_name_count[uuid] > 0 else '')}.xml'
            same_name_count[uuid] += 1
            cfdi_samples.append({'raw_bytes': etree.tostring(root), 'file_name': name})
        return cfdi_samples

    @classmethod
    def _mx_today(cls):
        """Today in the company CFDI timezone - the same reference the date constraint uses."""
        company = cls.company_data['company']
        tz = company.partner_id.commercial_partner_id._l10n_mx_edi_get_cfdi_timezone()
        return datetime.now(tz).date()

    @classmethod
    def _create_new_request(cls, request_type='batch_issued', state='in_process_at_sat', **kwargs):
        company = cls.company_data['company']
        vals = {
            'request_type': request_type,
            'state': state,
            'company_id': company.id,
        }
        if request_type == 'folio':
            vals['cfdi_uuid'] = kwargs.pop('cfdi_uuid', DEFAULT_CFDI_UUID)
        else:
            tz = company.partner_id.commercial_partner_id._l10n_mx_edi_get_cfdi_timezone()
            mx_today = datetime.now(tz).date()
            vals['emission_date_from'] = kwargs.pop('emission_date_from', mx_today - timedelta(days=31))
            vals['emission_date_to'] = kwargs.pop('emission_date_to', mx_today - timedelta(days=1))
            vals.setdefault('receipt_type', 'I')
        if state not in ('rejected', 'expired'):
            vals.setdefault('request_uuid', DEFAULT_REQUEST_UUID)
        if state == 'in_download':
            vals.setdefault('ready_at', fields.Datetime.now())
        vals.update(kwargs)
        request = cls.env['l10n_mx_edi.cfdi.request'].create(vals)
        cls.env.flush_all()
        return request

    def _create_request_attachment(self, raw, request=None):
        attachment_args = {
            'res_model': 'l10n_mx_edi.cfdi.request',
            'res_field': 'attachment_id',
            'res_id': request.id if request else False,
            'name': 'test.zip',
            'raw': raw,
            'mimetype': 'application/zip',
        }
        return self.env['ir.attachment'].create(attachment_args)

    def _build_auth_response(self, token=None):
        """Build a SAT authentication SOAP response.

        Returns a successful response containing the token, or a SOAP fault when token is None.
        """
        response_str = (
            f'<h:AutenticaResult xmlns:h="http://xmlns.jcp.org/jsf/html">{token}</h:AutenticaResult>'
            if token else
            '<s:Fault><faultstring>Authentication failed</faultstring></s:Fault>'
        )
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
            '<s:Body>'
            f'{response_str}'
            '</s:Body>'
            '</s:Envelope>'
        ).encode()

    def _build_request_download_response(self, request_uuid=DEFAULT_REQUEST_UUID, request_type='batch_issued', status_code=None):
        """Build a SAT request-download SOAP response.

        status_code=None → success (CodEstatus="5000" with IdSolicitud).
        Any other code → error response without IdSolicitud.
        """
        if request_type == 'batch_issued':
            result_tag = 'SolicitaDescargaEmitidosResult'
        elif request_type == 'batch_received':
            result_tag = 'SolicitaDescargaRecibidosResult'
        else:
            result_tag = 'SolicitaDescargaFolioResult'

        if status_code:
            result_attrs = f'CodEstatus="{status_code}" Mensaje="Error"'
        else:
            result_attrs = f'CodEstatus="5000" Mensaje="Ok" IdSolicitud="{request_uuid}"'

        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"'
            ' xmlns:h="http://DescargaMasivaTerceros.sat.gob.mx">'
            '<s:Body>'
            f'<h:{result_tag} {result_attrs}/>'
            '</s:Body>'
            '</s:Envelope>'
        ).encode()

    def _build_verification_response(self, n_uuids=1, request_uuid=DEFAULT_REQUEST_UUID, request_status=3, status_code=5000, code_status=None):
        """Build a SAT verification SOAP response."""
        packages = ''
        if request_status == 3:
            packages = ''.join(
                f'<h:IdsPaquetes>{request_uuid}_{i + 1:02d}</h:IdsPaquetes>'
                for i in range(n_uuids)
            )
        codes = ''
        if status_code is not None:
            codes += f' CodigoEstadoSolicitud="{status_code}"'
        if code_status is not None:
            codes += f' CodEstatus="{code_status}"'

        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"'
            ' xmlns:h="http://DescargaMasivaTerceros.sat.gob.mx">'
            '<s:Body>'
            f'<h:VerificaSolicitudDescargaResult'
            # SAT verification response always returns message Solicitud Aceptada for a reason
            f' EstadoSolicitud="{request_status}"{codes} Mensaje="Solicitud Aceptada">'
            f'{packages}'
            f'</h:VerificaSolicitudDescargaResult>'
            '</s:Body>'
            '</s:Envelope>'
        ).encode()

    def _build_package_download_response(self, status_code=5000, package_zip=None):
        """Build a SAT package-download SOAP response."""
        if status_code != 5000:
            return (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"'
                ' xmlns:h="http://DescargaMasivaTerceros.sat.gob.mx">'
                '<s:Body>'
                f'<h:respuesta CodEstatus="{status_code}" Mensaje="Error"/>'
                '</s:Body>'
                '</s:Envelope>'
            ).encode()

        paquete_xml = (
            f'<h:Paquete>{base64.b64encode(package_zip).decode()}</h:Paquete>'
            if package_zip else ''
        )
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"'
            ' xmlns:h="http://DescargaMasivaTerceros.sat.gob.mx">'
            '<s:Body>'
            f'<h:respuesta CodEstatus="{status_code}" Mensaje="OK"/>'
            f'{paquete_xml}'
            '</s:Body>'
            '</s:Envelope>'
        ).encode()

    def _build_fault_response(self, content='Service Unavailable'):
        return (
            '<?xml version="1.0"?>'
            '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body>'
            f'<s:Fault><faultstring>{content}</faultstring></s:Fault>'
            '</s:Body></s:Envelope>'
        ).encode()

    def _http_error_response_mock(self, status_code):
        """A fake ``requests`` response whose ``raise_for_status`` raises an ``HTTPError``."""
        m = MagicMock()
        m.content = b''
        error = requests.exceptions.HTTPError(f'HTTP {status_code}')
        error.response = MagicMock(status_code=status_code)
        m.raise_for_status.side_effect = error
        return m

    def _trigger_cron(self, cron):
        """Trigger `cron` in test registry mode"""
        with self.enter_registry_test_mode(), mute_logger('odoo.addons.base.models.ir_cron'):
            cron.method_direct_trigger()

    @contextmanager
    def mx_frozen_now(self, ref_datetime, certificate=None):
        with self.mx_external_setup(ref_datetime, certificate=certificate):
            self.patch(self.env.cr, 'now', lambda: ref_datetime)
            yield

    @contextmanager
    def mocked_cfdi_requests(self, mock_kwargs_list=None):
        """Mock SAT authentication + SOAP calls for a sequence of CFDI request steps.

        One entry per step, each handed a token unless it says otherwise. What its ``requests.post``
        does:
        - ``{'response': <bytes>}``: returns it.
        - ``{'error': <exception>}``: raises it.
        - ``{'http_status': <int>}``: returns a response whose ``raise_for_status`` raises an ``HTTPError``.

        Adding ``{'auth_response': <bytes>}`` to a step to mock SAT response from auth on that step.

        Yields the patched ``requests.post`` mock.
        """
        def _make_mock(content):
            m = MagicMock()
            m.content = content
            m.raise_for_status.return_value = None
            return m

        mock_kwargs_list = mock_kwargs_list or []
        token_side_effects = []
        post_side_effects = []
        for kw in mock_kwargs_list:
            if kw.get('auth_response'):
                token_side_effects.append('authenticate')
                post_side_effects.append(_make_mock(kw['auth_response']))
            else:
                token_side_effects.append('test-token')
            if kw.get('error') is not None:
                post_side_effects.append(kw['error'])
            elif 'http_status' in kw:
                post_side_effects.append(self._http_error_response_mock(kw['http_status']))
            elif 'response' in kw:
                post_side_effects.append(_make_mock(kw['response']))

        get_token = CertificateCertificate._l10n_mx_edi_get_sat_token
        tokens = iter(token_side_effects)

        def _mocked_get_token(certificate):
            token = next(tokens)
            return get_token(certificate) if token == 'authenticate' else token

        with patch.object(CertificateCertificate, '_l10n_mx_edi_get_sat_token', _mocked_get_token), \
             patch(f'{L10n_Mx_EdiSatDownloadClient.__module__}.requests.post', side_effect=post_side_effects) as mocked_post, \
             mute_logger('odoo.addons.l10n_mx_edi'):
            yield mocked_post

    @contextmanager
    def mocked_send_cfdi_request(self, response=None, auth_response=None):
        """Context manager to mock a single successful CFDI request step."""
        with self.mocked_cfdi_requests([{'response': response, 'auth_response': auth_response}]) as mocked_post:
            yield mocked_post

    @contextmanager
    def mocked_failed_cfdi_request(self, error=None, http_status=None):
        """Context manager to mock a single failing CFDI request step."""
        error = {'error': error} if error is not None else {'http_status': http_status}
        with self.mocked_cfdi_requests([error]) as mocked_post:
            yield mocked_post

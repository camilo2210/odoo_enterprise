from unittest.mock import Mock

import requests

from odoo import tools

PATCH_POST_TARGET = 'odoo.addons.l10n_do_edi.models.account_move.requests.post'
PATCH_GET_TARGET = 'odoo.addons.l10n_do_edi.models.account_move.requests.get'
PATCH_SEND_SESSION_TARGET = 'odoo.addons.l10n_do_edi.models.account_move_send.requests.Session'


def mock_response(status_code=200, json_data=None, content=b''):
    mock_resp = Mock(spec=requests.Response)
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data or {}
    mock_resp.content = content
    mock_resp.raise_for_status.return_value = None
    return mock_resp


def mock_login_response():
    return mock_response(200, {'token': 'test_token_123'})


def mock_ecf_success_response(i):

    return mock_response(200, {
        'fecha': '2026-01-15T10:00:00-04:00',
        'resultado': True,
        'descripcion': 'Comprobante Emitido',
        'ambiente': 'testecf',
        'solicitud_id': f"REQ-{i}",
        'rnc_emisor': '123456789',
        'rnc_comprador': '987654321',
        'identificador_unico': '',
        'encf': 'E31%010d' % i,
        'trackid': f'TRACK-{i}',
        'codigo_seguridad': 'ABC123',
        'secuencia_utilizada': True,
        'cantidad_errores': 0,
        'errores': [],
        'url_pdf': 'https://fe-webservice-test.infile.com.do/pdf?formato=pdf',
        'url_qr_consulta_dgii': 'https://dgii.gov.do/qr/test',
    })


def mock_ecf_rejected_response():
    return mock_response(400, {
        'fecha': '2026-01-15T10:00:00-04:00',
        'resultado': False,
        'descripcion': 'Existen errores en el documento',
        'ambiente': 'testecf',
        'solicitud_id': 'REQ-001',
        'rnc_emisor': '',
        'rnc_comprador': '',
        'identificador_unico': '',
        'encf': '',
        'trackid': '',
        'codigo_seguridad': '',
        'secuencia_utilizada': '',
        'cantidad_errores': 1,
        'errores': [{'descripcion': 'Fecha de vencimiento de secuencia inválida.'}],
        'url_pdf': '',
        'url_qr_consulta_dgii': '',
    })


def mock_signed_xml_response():
    with tools.file_open('l10n_do_edi/tests/mock_signed_xml_response.xml', 'rb') as f:
        return mock_response(200, content=f.read())


def mock_dgii_accepted_response():
    return mock_response(200, {
        'fecha': '2026-03-25T14:04:52-04:00',
        'resultado': True,
        'descripcion': 'Consulta de documento realizado con éxito',
        'ambiente': 'testecf',
        'consulta': {
            'encf': 'E310000000001',
            'rnc_emisor': '123456789',
            'rnc_comprador': '987654321',
            'estado': 'Aceptado',
            'trackid': 'TRACK-001',
            'codigo_seguridad': 'ABC123',
            'correo_comprador': '',
            'estado_acuse_recibo': False,
            'estado_aprobacion_comercial': False,
            'fase_documento': 'Pruebas',
            'fecha_recepcion': '2026-03-25T14:04:26-04:00',
            'tipo_ecf': 31,
            'respuesta_dgii_autoriazacion': [
                {'descripcion': '{"codigo":1,"estado":"Aceptado","mensajes":null,"encf":"E320000000835","secuenciaUtilizada":true}', 'fecha': '2026-03-25T14:04:26-04:00'},
            ],
            'consulta_dgii_codigo': '1',
            'consulta_dgii_estado': 'Aceptado',
            'consulta_dgii_rnc': '123456789',
            'consulta_dgii_secuencia_utilizada': True,
            'consulta_dgii_fecha_recepcion': '3/25/2026 2:04:26 PM',
            'consulta_dgii_respuesta': [
                {'valor': '', 'codigo': 0},
            ],
            'ruta_xml': 'https://fe-webservice-test.infile.com.do/pdf?formato=xml',
            'ruta_pdf': 'https://fe-webservice-test.infile.com.do/pdf?formato=pdf',
        },
    })


def mock_dgii_rejected_response():
    return mock_response(200, {
        'fecha': '2026-03-25T14:04:52-04:00',
        'resultado': True,
        'descripcion': 'Consulta de documento realizado con éxito',
        'ambiente': 'testecf',
        'consulta': {
            'encf': 'E310000000001',
            'rnc_emisor': '123456789',
            'rnc_comprador': '987654321',
            'estado': 'Aceptado',
            'trackid': 'TRACK-001',
            'codigo_seguridad': 'ABC123',
            'correo_comprador': '',
            'estado_acuse_recibo': False,
            'estado_aprobacion_comercial': False,
            'fase_documento': 'Pruebas',
            'fecha_recepcion': '2026-03-25T14:04:26-04:00',
            'tipo_ecf': 31,
            'respuesta_dgii_autoriazacion': [
                {'descripcion': '{"trackId":"TRACk-001","error":null,"mensaje":null}', 'fecha': '2026-03-25T14:04:26-04:00'},
            ],
            'consulta_dgii_codigo': '2',
            'consulta_dgii_estado': 'Rechazado',
            'consulta_dgii_rnc': '123456789',
            'consulta_dgii_secuencia_utilizada': False,
            'consulta_dgii_fecha_recepcion': '3/25/2026 2:04:26 PM',
            'consulta_dgii_respuesta': [
                {'valor': 'Fecha de vencimiento de secuencia inválida.', 'codigo': 145},
            ],
            'ruta_xml': 'https://fe-webservice-test.infile.com.do/pdf?formato=xml',
            'ruta_pdf': 'https://fe-webservice-test.infile.com.do/pdf?formato=pdf',
        },
    })

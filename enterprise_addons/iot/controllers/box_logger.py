import logging

from odoo import http
from odoo.http import request, Response
from .main import _search_box

_logger = logging.getLogger(__name__)
_logger.setLevel(logging.DEBUG)


def _sanitize_log_batch(batch: bytes) -> list[bytes]:
    """Split logs batch on <log/> separator and keep only
    well-formed log lines."""
    separator = b'<log/>\n'
    batch = batch.removesuffix(separator)  # Remove trailing separator to avoid empty element in list
    return batch.split(separator)


class IotLoggerController(http.Controller):
    @http.route('/iot/log', type='http', auth='public', csrf=False)
    def receive_iot_log(self):
        # Authenticate the IoT Box using the Bearer token
        auth_header = request.httprequest.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return Response(status=401)

        iot_box = _search_box(token=auth_header.removeprefix('Bearer ').strip())
        if not iot_box:
            return Response(status=401)

        # Parse and log the received logs batch
        logs_batch = _sanitize_log_batch(request.httprequest.get_data())
        if len(logs_batch) < 2:
            return Response(status=200)

        box_logger = _logger.getChild(iot_box.identifier)

        # TODO: remove when v19 is deprecated (line is sent by IoT Box for compat. w/ older dbs)
        if logs_batch and logs_batch[0].startswith(b'identifier '):
            logs_batch.pop(0)

        for log in logs_batch:
            level_no, line = log.split(b',', 1)
            box_logger.info("Emitted log by IOT box (level %d):\n%s", int(level_no), line.decode(errors="ignore"))

        return Response(status=200)

import logging

from werkzeug.exceptions import NotFound

from odoo import http
from odoo.http import request
from odoo.tools import consteq

_logger = logging.getLogger(__name__)


def _check_obox_access(serial_number, token):
    box = (
        request.env["obox.obox"]
        .sudo()
        .with_context(active_test=False)
        .search([("serial_number", "=", serial_number)], limit=1)
    )
    if not box or not consteq(box.token, token):
        raise NotFound
    return box


class OboxController(http.Controller):
    @http.route("/obox/connect", auth="public", type="jsonrpc")
    def obox_connect(self, serial_number, token, local_ip, services):
        box = _check_obox_access(serial_number, token)
        box.state = "02_paired"
        box.local_ip = local_ip
        box.services = services
        box._send_obox_updated_notification()
        if box._discover_devices_on_connect():
            box.action_discover_devices()

    @http.route("/obox/ping", auth="public", type="jsonrpc")
    def obox_ping(self, serial_number, token):
        box = _check_obox_access(serial_number, token)
        box._send_internal_websocket_message("PING", {"token": token})

    @http.route("/obox/get_next_actions", auth="public", type="jsonrpc")
    def get_next_action(self, serial_number, token):
        box = _check_obox_access(serial_number, token)
        return box.get_next_actions()

    @http.route("/obox/action_result", auth="public", type="jsonrpc")
    def obox_action_result(self, serial_number, token, action_uuid, result=False):
        _check_obox_access(serial_number, token)
        action = (
            request.env["obox.queue"].sudo().search([("uuid", "=", action_uuid)], limit=1)
        )
        if not action:
            raise NotFound

        _logger.info(
            "Received result for action %s from Obox %s: %s",
            action_uuid,
            serial_number,
            result,
        )
        action.handle_obox_response(result)

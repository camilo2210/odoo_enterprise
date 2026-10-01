import json
import logging

from werkzeug.exceptions import Forbidden

from odoo import http
from odoo.http import request, Response
from odoo.tools import verify_hash_signed

from odoo.addons.voip.models.phone_service_api import CLIENT_SECRET_PARAM, CLIENT_UUID_PARAM
from odoo.addons.voip.models.phone_service_event import HANDLED_EVENTS

_logger = logging.getLogger(__name__)

# Wire contract with the signer; see phone_service/utils/webhook.py.
WEBHOOK_TOKEN_SCOPE = "phone_service_webhook"
TENANT_RECOVERY_TOKEN_SCOPE = "phone_service_tenant_recovery"


def _decode_phone_service_token(env, scope, token, client_secret):
    try:
        return verify_hash_signed(
            env(su=True), scope, token,
            secret=env["iap.account"]._hash_iap_token(client_secret))
    except ValueError:
        return None


def decode_phone_service_event(env, token, client_secret):
    return _decode_phone_service_token(
        env, WEBHOOK_TOKEN_SCOPE, token, client_secret,
    )


class PhoneServiceApiController(http.Controller):
    @http.route("/voip/api/phone_service/tenant_recovery", type="json2", auth="public",
                methods=["POST"], save_session=False, readonly=True)
    def get_tenant_recovery_payload(self, token=None):
        if not isinstance(token, str):
            _logger.warning("Rejected phone_service tenant recovery request: missing or malformed token")
            raise Forbidden()

        parameters = request.env["ir.config_parameter"].sudo()
        client_secret = parameters.get_str(CLIENT_SECRET_PARAM)
        client_uuid = parameters.get_str(CLIENT_UUID_PARAM)
        if not client_secret or not client_uuid:
            _logger.warning("Rejected phone_service tenant recovery request: client credentials are not configured")
            raise Forbidden()

        envelope = _decode_phone_service_token(
            request.env, TENANT_RECOVERY_TOKEN_SCOPE, token, client_secret,
        )
        if envelope != {"client_uuid": client_uuid}:
            _logger.warning("Rejected phone_service tenant recovery request: invalid or expired token")
            raise Forbidden()
        return request.env["voip.pbx.service"]._get_tenant_recovery_payload()

    @http.route("/voip/api/phone_service/event", type="json2", auth="public",
                methods=["POST"], save_session=False)
    def on_phone_service_event(self, token=None):
        if not isinstance(token, str):
            _logger.warning("Rejected phone_service webhook: missing or malformed token")
            raise Forbidden()

        client_secret = request.env["ir.config_parameter"].sudo().get_str(CLIENT_SECRET_PARAM)
        if not client_secret:
            _logger.warning(
                "Rejected phone_service webhook: %s is not configured on this database",
                CLIENT_SECRET_PARAM)
            raise Forbidden()

        envelope = decode_phone_service_event(request.env, token, client_secret)
        if envelope is None:
            _logger.warning(
                "Rejected phone_service webhook: invalid or expired token (check %s)",
                CLIENT_SECRET_PARAM)
            raise Forbidden()

        data = envelope["data"]
        event_type = data.get("event_type", "")
        event_id = data.get("id", "missing id")
        _logger.info("Received phone_service event %s (%s)", event_type, event_id)
        if _logger.isEnabledFor(logging.DEBUG):
            _logger.debug(
                "phone_service event %s (%s):\n%s",
                event_type,
                event_id,
                json.dumps(data, indent=2, sort_keys=True, default=str),
            )
        if event_type not in HANDLED_EVENTS:
            return Response(status=200)
        if not all(field in data for field in ("id", "payload", "occurred_at")):
            _logger.warning(
                "Discarding malformed phone_service %s event: missing required fields", event_type)
            return Response(status=200)
        return request.env["voip.phone.service.event"]._ack_then_process(
            data, request.db, request.env.uid)

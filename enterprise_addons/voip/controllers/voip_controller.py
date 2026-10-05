import logging
import re
from werkzeug.exceptions import BadRequest, Forbidden, UnsupportedMediaType

from odoo import http
from odoo.exceptions import UserError
from odoo.http import Response, request
from odoo.tools import config, consteq, verify_hash_signed

from odoo.addons.phone_validation.tools.phone_validation import phone_format
from odoo.addons.voip.models.utils import extract_country_code
from odoo.addons.voip.tools.linphone import (
    PROVISIONING_KEY_HEADER,
    PROVISIONING_KIND_BOOTSTRAP,
    PROVISIONING_KIND_REFRESH,
    PROVISIONING_MAX_DEVICES,
    PROVISIONING_TOKEN_SCOPE,
    build_provisioning_config,
    is_linphone_provisioning_request,
    new_provisioning_key,
    provisioning_key_hash,
)

_logger = logging.getLogger(__name__)

ALLOWED_ARTIFACT_FIELDS = frozenset({"voip_call_id", "discuss_call_history_id", "start_ms", "end_ms"})
RECORDING_EXTENSIONS = {
    "audio/aac": "aac",
    "audio/mpeg": "mp3",
    "audio/mp4": "m4a",
    "audio/ogg": "ogg",
    "audio/wav": "wav",
    "audio/webm": "webm",
}


class VoipController(http.Controller):

    def _get_allowed_artifact_fields(self):
        return ALLOWED_ARTIFACT_FIELDS

    @http.route("/voip/parse_phone_number", type="jsonrpc", auth="user", methods=["POST"])
    def parse_phone_number(self, data):
        """ Parse the phone number to extract country code and validate it.

        :param data: dict with 'phone_number', optional 'iso' and 'itu'
        :return: dict with 'iso', 'itu', 'phone_number' and 'isValid'
        """
        phone_number = data["phone_number"]
        country_code = extract_country_code(phone_number)
        iso = country_code["iso"] or data.get("iso")
        itu = country_code["itu"] or data.get("itu")
        is_valid = False
        if iso and itu:
            try:
                phone_number = phone_format(phone_number, iso.upper(), int(itu))
                is_valid = True
            except UserError:
                is_valid = False
        # Re-parse the final number so the returned country matches the actual
        # formatted output (e.g., formatting with BE can still produce a US number).
        formatted_country_code = extract_country_code(phone_number)
        iso = formatted_country_code["iso"] or iso
        return {
            **request.env["res.country"]._get_country_by_country_code(iso),
            "phone_number": phone_number,
            "isValid": is_valid,
        }

    @http.route("/voip/update_country_code", type="jsonrpc", auth="user", methods=["POST"])
    def update_country_code(self, data, target_country_data):
        """ Update the phone number to match the target country code.
        We first format the number to national format based on the current country
        code to remove the country prefix, then we format it back to international
        format based on the target country code.

        :param data: dict with 'phone_number', optional 'iso' and 'itu'
        :param target_country_data: dict with 'iso' and 'itu'
        :return: dict with 'phone_number' and 'isValid'
        """
        phone_number = data["phone_number"]
        current_iso = data.get("iso")
        current_itu = data.get("itu")
        if not current_iso or not current_itu:
            national_number = re.sub(r"\D", "", phone_number)
        else:
            try:
                national_number = phone_format(phone_number, current_iso, current_itu, force_format="NATIONAL")
                national_number = re.sub(r"\D", "", national_number)
            except UserError:
                national_number = phone_number.removeprefix(f"+{current_itu}")
                national_number = re.sub(r"\D", "", national_number)

        iso = target_country_data["iso"]
        itu = target_country_data["itu"]
        try:
            phone_number = phone_format(national_number, iso, itu)
            is_valid = True
        except UserError:
            phone_number = "+" + str(itu) + national_number
            is_valid = False

        return {
            "phone_number": phone_number,
            "isValid": is_valid,
        }

    def _create_artifact(self, vals, **kwargs):
        """Create a mail.call.artifact record for the recording."""
        safe_vals = {k: v for k, v in vals.items() if k in self._get_allowed_artifact_fields()}
        return request.env["mail.call.artifact"].sudo().create(safe_vals).sudo(False)

    def _is_cloud_storage_configured(self):
        return bool(request.env["ir.config_parameter"].sudo().get_str("cloud_storage_provider"))

    def _is_cloud_storage_required(self, call_sudo, **kwargs):
        return call_sudo.is_production

    @http.route("/voip/decline_incoming_call", type="jsonrpc", auth="user", methods=["POST"])
    def decline_incoming_call(self, call_id):
        """Decline an incoming call server-side via the PBX.

        Used by the service worker when a call is declined from a push
        notification and no browser SIP session is open to reject the INVITE.
        """
        call = request.env["voip.call"].browse(int(call_id)).exists()
        if not call:
            raise Forbidden()
        if call.reject_call()["success"]:
            # The user's other devices are still ringing this call, and nothing
            # else will tell them: the cancel push that follows finds the call
            # already settled and stays silent so it cannot downgrade this
            # rejection to a miss.
            call._notify_devices()
        if not config["test_enable"]:
            request.env.cr.commit()
        call._decline_via_pbx()
        return {"success": True}

    @http.route("/voip/upload_recording/<int:call_id>", type="http", auth="user", methods=["POST"], csrf=True)
    def upload_recording(self, call_id, ufile, start_ms=0, end_ms=0, **kwargs):
        if not ufile:
            raise BadRequest()
        if not ufile.content_type.startswith("audio/"):
            raise UnsupportedMediaType()
        call_sudo = request.env["voip.call"].sudo().browse(call_id)
        if not call_sudo.exists():
            raise BadRequest()
        if request.env.user != call_sudo.user_id:
            raise Forbidden()

        client_requested_cloud_storage = kwargs.get("cloud_storage") == "true"
        cloud_configured = self._is_cloud_storage_configured()
        is_cloud_storage_required = self._is_cloud_storage_required(call_sudo, **kwargs)

        if call_sudo.is_production:
            if is_cloud_storage_required and not cloud_configured:
                raise BadRequest("Configure cloud storage to use persistent recordings.")
            if is_cloud_storage_required and not client_requested_cloud_storage:
                raise BadRequest("Persistent recordings must be stored on the cloud.")
        else:
            if (int(end_ms) - int(start_ms)) > 3 * 60 * 1000:
                raise BadRequest("Demo recordings are limited to 3 minutes.")
            if client_requested_cloud_storage:
                raise Forbidden("Demo recordings cannot be stored in cloud storage.")

        artifact = self._create_artifact({
            "voip_call_id": call_sudo.id,
            "start_ms": int(start_ms),
            "end_ms": int(end_ms),
        }, **kwargs)

        mimetype = ufile.content_type.split(";", 1)[0]
        extension = RECORDING_EXTENSIONS.get(mimetype, "bin")
        filename = f"call_{call_sudo.id}_artifact_{artifact.id}_{start_ms}_{end_ms}.{extension}"

        attachment_sudo = (
            request.env["ir.attachment"]
            .sudo()
            ._upload_file(ufile, {
                "name": filename,
                "mimetype": ufile.content_type or "audio/webm",
                "res_model": "mail.call.artifact",
                "res_id": artifact.id,
            })
        )

        if client_requested_cloud_storage:
            attachment_sudo._post_add_create(cloud_storage=True)

        call_sudo.update_activity_message()

        if client_requested_cloud_storage:
            upload_info = attachment_sudo._generate_cloud_storage_upload_info()
            return request.make_json_response({"upload_info": upload_info, "attachment_id": attachment_sudo.id})

        return Response(status=200)

    @http.route("/voip/audio/message/<int:message_id>", type="http", auth="user", methods=["GET"], readonly=True)
    def audio_message(self, message_id, v=None):
        message = request.env["voip.sound"].browse(message_id).exists()
        if not message or not message.data:
            raise request.not_found()
        stream = request.env["ir.binary"]._get_stream_from(
            message,
            "data",
            filename_field="data_filename",
        )
        return stream.get_response(as_attachment=False)

    @http.route("/voip/voicemail/message/<int:message_id>", type="http", auth="user", methods=["GET"], readonly=True)
    def voicemail_message(self, message_id, v=None):
        message = request.env["voip.voicemail.message"].browse(message_id).exists()
        if not message or not message.recording:
            raise request.not_found()
        stream = request.env["ir.binary"]._get_stream_from(
            message,
            "recording",
            filename_field="recording_filename",
        )
        return stream.get_response(as_attachment=False)

    @http.route("/voip/linphone_provisioning/<string:token>", type="http", auth="public", methods=["GET"])
    def linphone_provisioning(self, token):
        if not is_linphone_provisioning_request(request.httprequest.headers):
            _logger.info(
                "Rejecting Linphone provisioning request from %s: not a Linphone client",
                request.httprequest.remote_addr,
            )
            raise request.not_found()
        try:
            payload = verify_hash_signed(request.env(su=True), PROVISIONING_TOKEN_SCOPE, token)
        except ValueError:
            payload = None
        if not payload:
            raise Forbidden()
        kind = payload[0] if len(payload) >= 2 else None
        if kind not in (PROVISIONING_KIND_BOOTSTRAP, PROVISIONING_KIND_REFRESH):
            raise request.not_found()

        user = request.env["res.users"].sudo().browse(payload[1]).exists()
        settings = user.res_users_settings_id
        if not user.active or not user.uses_odoo_provider or not settings.voip_username or not settings.voip_secret:
            raise request.not_found()
        bootstrap_kwargs = {}

        # Bootstrap path, single-use: once consumed the QR code is invalidated and the phone must fetch a new one to re-provision.
        if kind == PROVISIONING_KIND_BOOTSTRAP:
            if len(payload) != 3 or payload[2] != settings.voip_linphone_provisioning_serial:
                raise request.not_found()
            provisioning_key = new_provisioning_key()
            known = settings.voip_linphone_provisioning_key_hashes or []
            settings.sudo().write({
                "voip_linphone_provisioning_serial": settings.voip_linphone_provisioning_serial + 1,
                # Oldest first, capped: the digest of the phone provisioned longest ago
                # falls off instead of staying valid forever. Assigned as a new list.
                "voip_linphone_provisioning_key_hashes": [
                    *known[-(PROVISIONING_MAX_DEVICES - 1):],
                    provisioning_key_hash(request.env, provisioning_key),
                ],
            })
            # Every code and link issued before this write is now invalid, so
            # the form showing them has to be told rather than left displaying
            # a code no phone can use.
            user._bus_send("voip.linphone_provisioning/rotated", {})
            bootstrap_kwargs = {
                "refresh_url": user._get_linphone_refresh_url(),
                "provisioning_key": provisioning_key,
            }

        # Refresh path, multi-use: the phone fetches this at every core start to re-provision itself with the latest settings.
        else:
            # The URL carries no secret; the key does, in a header liblinphone
            # re-sends from its own configuration. consteq compares digests, of
            # fixed length, and the loop length depends on the number of
            # provisioned phones, never on the presented key.
            presented = (request.httprequest.headers.get(PROVISIONING_KEY_HEADER) or "").strip()
            digest = provisioning_key_hash(request.env, presented) if presented else ""
            known = settings.voip_linphone_provisioning_key_hashes or []
            if not digest or not any(consteq(digest, known_digest) for known_digest in known):
                _logger.info(
                    "Rejecting Linphone provisioning refresh for user %s from %s: unknown device key",
                    user.id,
                    request.httprequest.remote_addr,
                )
                raise request.not_found()
        provisioning_config = build_provisioning_config(
            user_display_name=user.name,
            username=settings.voip_username,
            password=settings.voip_secret,
            domain=user.voip_provider_id.pbx_ip,
            **bootstrap_kwargs,
        )
        return request.make_response(provisioning_config, headers=[
            ("Content-Type", "application/xml"),
            ("Cache-Control", "no-store"),
        ])

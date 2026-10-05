import base64
import logging
from urllib.parse import urlsplit

import requests

from odoo.exceptions import AccessError, UserError
from odoo.modules import module
from odoo.tools.urls import urljoin

_logger = logging.getLogger(__name__)

MAX_PHONE_NUMBERS_PER_REQUEST = 50

REQUEST_TIMEOUT = 15

PHONE_SERVICE_NAME = "phone_service"

WEBHOOK_EVENT_URL_SYNC_PENDING_PARAM = "voip.phone_service_webhook_event_url_sync_pending"
CLIENT_UUID_PARAM = "voip.client_uuid"
CLIENT_SECRET_PARAM = "voip.client_secret"
ENDPOINT_PARAM = "phone_service.endpoint"
DEFAULT_ENDPOINT = "https://phone-service.api.odoo.com"

# Only these schemes/hosts may ever be contacted as the Odoo Phone Service
# endpoint. Enforced both when `phone_service.endpoint` is configured (see
# ir_config_parameter.py) and again right before every call, since the two
# moments can drift (config changed concurrently, stale cached value, ...).
ALLOWED_ENDPOINT_SCHEMES = {"https"}
ALLOWED_ENDPOINT_HOSTS = {"odoo.com"}
ALLOWED_ENDPOINT_HOST_SUFFIXES = (".odoo.com",)
# DEV ONLY: a locally-run phone_service instance has no TLS certificate, so
# plain HTTP is allowed for loopback hosts only. Never reachable from outside
# the machine, so this doesn't extend the allowlist to any real endpoint.
DEV_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}

# For each pbx sync route, the response ids the server echoes back from the
# request when the caller already holds them (update path): response key →
# request param. Demo mode and the test PBX mock apply the same echo.
PBX_SYNC_ECHO_IDS = {
    "sync_user": {"user_id": "user_id", "user_uuid": "user_uuid", "line_id": "line_id"},
    "sync_user_extension": {"user_id": "user_id", "line_id": "line_id",
                            "extension_id": "extension_id"},
    "sync_group": {"group_id": "group_id", "group_uuid": "group_uuid"},
    "sync_group_extension": {"extension_id": "extension_id"},
    "sync_queue": {"queue_id": "queue_id"},
    "sync_queue_extension": {"extension_id": "extension_id"},
    "sync_ivr": {"ivr_id": "ivr_id"},
    "sync_agent": {"agent_id": "agent_id"},
    "sync_voicemail": {"voicemail_id": "voicemail_id"},
    "sync_incall": {"incall_id": "incall_id", "extension_id": "incall_extension_id"},
    "sync_moh": {"moh_uuid": "moh_uuid", "moh_name": "moh_name"},
}


def _is_allowed_endpoint_host(hostname):
    hostname = (hostname or "").lower()
    return hostname in ALLOWED_ENDPOINT_HOSTS or hostname.endswith(ALLOWED_ENDPOINT_HOST_SUFFIXES)


def validate_phone_service_endpoint(env, url):
    """Reject a phone_service endpoint whose scheme or host is not an
    allowed Odoo IAP target, and return the validated hostname.

    Called both when ``phone_service.endpoint`` is configured (see
    ir_config_parameter.py) and again right before every call.
    """
    parts = urlsplit(url or "")
    hostname = (parts.hostname or "").lower()
    if not hostname:
        raise UserError(env._("The Phone Service endpoint must be a valid HTTPS URL."))
    if hostname in DEV_LOOPBACK_HOSTS:
        if parts.scheme not in ("http", "https"):
            raise UserError(env._("The Phone Service endpoint must be a valid HTTPS URL."))
        return hostname
    if parts.scheme not in ALLOWED_ENDPOINT_SCHEMES:
        raise UserError(env._("The Phone Service endpoint must be a valid HTTPS URL."))
    if not _is_allowed_endpoint_host(hostname):
        raise UserError(
            env._(
                "The Phone Service endpoint host %(host)s is not an allowed Odoo host.",
                host=hostname,
            )
        )
    return hostname


def _phone_number_detail_lines(env, details):
    missing_numbers = (details or {}).get("missing_numbers")
    if not missing_numbers:
        return ""
    return "• " + env._(
        "Pricing expired for: %(numbers)s", numbers=", ".join(missing_numbers),
    )


def _invalid_address_lines(env, invalid_fields):
    """Per-field messages for the semantic address-rejection fields returned by
    the phone service (`invalid_address_fields`)."""
    msg_by_field = {
        "address": env._("The address is invalid."),
        "country_code": env._("The country code is invalid."),
        "city": env._("The city is invalid."),
        "neighborhood": env._("The neighborhood is invalid."),
        "administrative_area": env._("The state or region is invalid."),
        "postal_code": env._("The postal code is invalid."),
        "borough": env._("The borough is invalid."),
        "street_address": env._("The street address is invalid."),
        "house_number": env._("The house number is invalid."),
        "extended_address": env._("The extended address is invalid."),
        "service_area_mismatch": env._("The service address does not match the expected area."),
    }
    return [f"• {msg_by_field[field]}" for field in invalid_fields if field in msg_by_field]


def _phone_service_error_message(env, error_key, details=None):
    default_msg = env._("The Odoo Phone Service is temporarily unavailable. Please try again later.")
    error_by_key = {
        "file_too_large": env._("The uploaded document is too large."),
        "authentication_failed": env._(
            "Could not authenticate with the Odoo Phone Service. Please try again later."
        ),
        "pbx_authentication_failed": env._(
            "The Odoo Phone Service could not authenticate with the PBX."
            " Please contact Odoo support if the problem persists."
        ),
        "forbidden": env._(
            "This resource is not associated with your database."
        ),
        "invalid_subscription": env._(
            "Your Odoo subscription does not allow this operation."
        ),
        "insufficient_credits": env._(
            "You do not have enough credits to complete this operation."
        ),
        "invalid_update": env._("The requested update is invalid for the current resource state."),
        "bad_request": env._("The request sent to the Odoo Phone Service is invalid."),
        "missing_payload": env._("The request sent to the Odoo Phone Service is incomplete."),
        "not_found": env._(
            "The requested PBX resource was not found. It may have been deleted already."
        ),
        "pbx_operation_failed": env._(
            "The PBX operation could not be completed. Please try again later."
        ),
        "extension_number_taken": env._("This extension number is already taken."),
        "invalid_pbx_name": env._(
            "This name contains characters that are not supported by the phone system"
            " (such as quotation marks). Please remove them and try again."
        ),
        "phone_number_not_releasable": env._(
            "This phone number cannot be released in its current state."
        ),
        "pricing_expired": env._(
            "Phone number pricing has expired. Please search for available numbers again."
        ),
        "service_temporarily_unavailable": default_msg,
        "no_coverage_found": env._(
            "No coverage found in the selected country based on the provided search parameters."
            " Please try a different country or search criteria."
        ),
        "no_numbers_found": env._(
            "No numbers found based on the provided search parameters."
            " Please try different search criteria."
        ),
        "invalid_document_type": env._(
            "The document could not be uploaded. Please check that the file is a supported format (PDF, JPEG, or PNG)."
        ),
        "rate_limit_exceeded": env._(
            "Too many text-to-speech requests were made recently. Please try again in a few minutes."
        ),
        "text_too_long": env._("The text is too long to be converted to speech."),
    }
    if error_key in error_by_key:
        message = error_by_key[error_key]
        detail_lines = _phone_number_detail_lines(env, details)
        return f"{message}\n\n{detail_lines}" if detail_lines else message
    if error_key == "invalid_address":
        lines = _invalid_address_lines(env, (details or {}).get("invalid_address_fields") or [])
        if lines:
            return "\n".join(lines)
        return env._("The address could not be saved. Please verify that all fields are correct.")
    return default_msg


class PhoneServiceError(UserError):
    """An error from the Odoo Phone Service carrying the stable ``error_key``.

    Callers can inspect ``error_key`` to branch on specific failure modes
    (e.g. ``"not_found"`` to clear stale PBX ids) rather than parsing the
    user-facing message.
    """

    def __init__(self, message, error_key=None):
        super().__init__(message)
        self.error_key = error_key


class PhoneServiceAPI:
    def __init__(self, env, request_timeout=REQUEST_TIMEOUT):
        if not env.su and not env.user.has_group("voip.group_voip_admin"):
            raise AccessError(
                env._("Only VoIP administrators can reach the Odoo Phone Service.")
            )
        self.env = env
        self.request_timeout = request_timeout

    def _call_phone_service(self, route, params, retry_registration=True):
        unreachable_msg = self.env._(
            "Could not reach the Odoo Phone Service. Please try again later."
        )
        if not route.startswith("/") or urlsplit(route).scheme or urlsplit(route).netloc:
            _logger.error("Refusing to call unsafe phone_service route: %r", route)
            raise UserError(unreachable_msg)
        original_params = dict(params)
        icp = self.env["ir.config_parameter"].sudo()
        endpoint = icp.get_str(ENDPOINT_PARAM) or DEFAULT_ENDPOINT
        validate_phone_service_endpoint(self.env, endpoint)
        iap_account = self.env["iap.account"].sudo().get(PHONE_SERVICE_NAME)
        client_uuid, client_secret = icp._voip_get_client_credentials()
        params = {
            **original_params,
            "account_token": iap_account.account_token,
            "client_uuid": client_uuid,
            "client_secret": client_secret,
            "db_uuid": icp.get_str("database.uuid"),
        }
        if route not in (
            "/api/phone_service/1/register_client",
            "/api/phone_service/1/update_client",
        ):
            self._retry_pending_webhook_event_url_sync()
        url = urljoin(endpoint, route)
        try:
            res = requests.post(url, json=params, timeout=self.request_timeout, allow_redirects=False)
        except requests.exceptions.RequestException as exc:
            _logger.warning("phone_service request failed for %s: %s", route, exc)
            raise PhoneServiceError(
                unreachable_msg,
                error_key="service_temporarily_unavailable",
            ) from exc
        try:
            result = res.json()
        except ValueError as exc:
            _logger.warning("phone_service returned a malformed response for %s: %s", route, exc)
            raise PhoneServiceError(
                unreachable_msg,
                error_key="service_temporarily_unavailable",
            ) from exc
        if not result.get("success"):
            error_key = result.get("error")
            if (
                retry_registration
                and route != "/api/phone_service/1/register_client"
                and error_key == "authentication_failed"
            ):
                self.register_client()
                return self._call_phone_service(route, original_params, retry_registration=False)
            raise PhoneServiceError(
                _phone_service_error_message(
                    self.env,
                    error_key,
                    details=result.get("details"),
                ),
                error_key=error_key,
            )
        return result

    # -- Clients --

    def register_client(self):
        """Register this database's VoIP client with phone_service."""
        # Registration is the recovery path, so do not let it recursively retry itself.
        return self._call_phone_service(
            "/api/phone_service/1/register_client",
            {"webhook_event_url": self._get_webhook_event_url()},
            retry_registration=False,
        )

    def _get_webhook_event_url(self):
        return urljoin(self.env["ir.config_parameter"].sudo().get_base_url(), "/voip/api/phone_service/event")

    def _retry_pending_webhook_event_url_sync(self):
        if module.current_test:
            # Do not call phone_service during tests.
            return
        icp = self.env["ir.config_parameter"].sudo()
        if not icp.get_bool(WEBHOOK_EVENT_URL_SYNC_PENDING_PARAM):
            return
        try:
            self.sync_webhook_event_url()
        except UserError:
            _logger.warning(
                "Could not sync pending VoIP webhook URL with phone_service.",
                exc_info=True,
            )

    def sync_webhook_event_url(self):
        result = self._call_phone_service(
            "/api/phone_service/1/update_client",
            {"updates": {"webhook_event_url": self._get_webhook_event_url()}},
        )
        self.env["ir.config_parameter"].sudo().set_bool(
            WEBHOOK_EVENT_URL_SYNC_PENDING_PARAM, False
        )
        return result

    # -- Phone numbers --

    def search_available_phone_numbers(self, country_code, filters=None):
        payload = dict(filters or {})
        payload["filter[country_code]"] = country_code
        return self._call_phone_service(
            "/api/phone_service/1/search_available_phone_numbers",
            {"payload": payload},
        ).get("data", [])

    def get_all_country_coverage(self):
        data = self._call_phone_service(
            "/api/phone_service/1/get_country_coverage",
            {},
        ).get("data", {})
        return {
            entry["code"]: entry.get("phone_number_type") or []
            for entry in data.values()
            if entry.get("code")
        }

    def get_phone_number_statuses(self, phone_numbers=None):
        return self._call_phone_service(
            "/api/phone_service/1/get_phone_number_statuses",
            {"phone_numbers": phone_numbers or []},
        ).get("data", {})

    def release_phone_number(self, phone_number):
        return self._call_phone_service(
            "/api/phone_service/1/release_phone_number",
            {"phone_number": phone_number},
        ).get("data", {})

    def order_phone_numbers(self, phone_numbers):
        return self._call_phone_service("/api/phone_service/1/order_phone_numbers", {"phone_numbers": phone_numbers}).get("data", {})

    def create_advanced_order(self, **params):
        return self._call_phone_service(
            "/api/phone_service/1/create_advanced_order", params,
        ).get("data", {})

    def create_advanced_order_comment(self, request_uuid, body):
        return self._call_phone_service(
            "/api/phone_service/1/create_advanced_order_comment",
            {"request_uuid": request_uuid, "body": body},
        ).get("data", {})

    def get_number_request_statuses(self, request_uuids):
        return self._call_phone_service(
            "/api/phone_service/1/get_number_request_statuses",
            {"request_uuids": request_uuids},
        ).get("data", {})

    def get_phone_number_comments(self, phone_number):
        return self._call_phone_service(
            "/api/phone_service/1/get_phone_number_comments",
            {"phone_number": phone_number},
        ).get("data", [])

    # -- Requirements --

    def get_requirements(self, country_code, phone_number_type):
        result = self._call_phone_service(
            "/api/phone_service/1/get_requirements",
            {
                "payload": {
                    "filter[country_code]": country_code,
                    "filter[phone_number_type]": phone_number_type,
                    "filter[action]": "ordering",
                },
            },
        )
        return result.get("data", []), result.get("meta", {})

    def generate_requirement_verification_url(
        self, requirement_id, phone_number, first_name, last_name
    ):
        return self._call_phone_service(
            "/api/phone_service/1/generate_requirement_verification_url",
            {
                "requirement_id": requirement_id,
                "phone_number": phone_number,
                "payload": {
                    "requirement": {"first_name": first_name, "last_name": last_name}
                },
            },
        ).get("data", {})

    # -- Requirement groups --

    def create_requirement_group(self, country_code, phone_number_type):
        requirements_data, meta = self.get_requirements(
            country_code, phone_number_type
        )
        if not meta.get("total_results") or not requirements_data:
            return {}, {}
        data = self._call_phone_service(
            "/api/phone_service/1/create_requirement_group",
            {
                "payload": {
                    "country_code": country_code,
                    "phone_number_type": phone_number_type,
                    "action": "ordering",
                },
            },
        ).get("data", {})
        return data, requirements_data[0]

    def fulfill_requirement_group(self, requirement_group_id, requirements, request_uuid=None):
        params = {
            "requirement_group_id": requirement_group_id,
            "payload": {"regulatory_requirements": requirements},
        }
        if request_uuid:
            params["request_uuid"] = request_uuid
        return self._call_phone_service(
            "/api/phone_service/1/fulfill_requirement_group",
            params,
        ).get("data", {})

    def assign_requirement_group(
        self, phone_number, requirement_group_id
    ):
        return self._call_phone_service(
            "/api/phone_service/1/assign_requirement_group",
            {"phone_number": phone_number, "requirement_group_id": requirement_group_id},
        ).get("data", {})

    # -- Addresses --

    def create_address(self, address_data):
        return self._call_phone_service(
            "/api/phone_service/1/create_address",
            {"payload": address_data},
        ).get("data", {})

    def validate_address(self, address_data):
        return self._call_phone_service(
            "/api/phone_service/1/validate_address", {"payload": address_data}
        ).get("data", {})

    # -- Documents --

    def upload_document(self, content, filename):
        return self._call_phone_service(
            "/api/phone_service/1/upload_document",
            {
                "payload": {
                    "file_content_base64": base64.b64encode(content).decode(),
                    "filename": filename,
                }
            },
        ).get("data", {})

    # -- Text-to-speech --

    def get_tts_voices(self):
        return self._call_phone_service(
            "/api/phone_service/1/get_tts_voices",
            {},
        ).get("data", {}).get("voices", [])

    def generate_speech(self, *, text, voice):
        data = self._call_phone_service(
            "/api/phone_service/1/generate_speech",
            {"text": text, "voice": voice},
        ).get("data", {})
        return base64.b64decode(
            data.get("file_content_base64") or "",
            validate=True,
        )

    # -- PBX --

    def pbx_call(self, name, **params):
        return self._call_phone_service(
            f"/api/phone_service/1/pbx/{name}", params,
        ).get("data", {})

    def pbx_upload_voicemail_greeting(self, *, voicemail_id, greeting, content):
        return self.pbx_call(
            "upload_voicemail_greeting",
            voicemail_id=voicemail_id, greeting=greeting,
            file_content_base64=base64.b64encode(content).decode(),
        )

    def pbx_get_voicemail_message_recording(self, *, voicemail_id, message_id):
        data = self.pbx_call(
            "get_voicemail_message_recording",
            voicemail_id=voicemail_id,
            message_id=message_id,
        )
        return {
            **data,
            "content": base64.b64decode(data.get("file_content_base64") or "", validate=True),
        }

    def pbx_upload_sound(self, *, filename, content, sound_format):
        return self.pbx_call(
            "upload_sound",
            filename=filename, sound_format=sound_format,
            file_content_base64=base64.b64encode(content).decode(),
        )

    def pbx_sync_moh(self, *, files, **params):
        return self.pbx_call(
            "sync_moh",
            **params,
            files=[
                {
                    "filename": filename,
                    "file_content_base64": base64.b64encode(content).decode(),
                }
                for filename, content in files
            ],
        )

    def hangup_call(self, call_id):
        return self._call_phone_service(
            "/api/phone_service/1/pbx/hangup_call",
            {"call_id": call_id},
        )

    def decline_call(self, conversation_id, user_uuid):
        return self._call_phone_service(
            "/api/phone_service/1/pbx/decline_call",
            {"conversation_id": conversation_id, "user_uuid": user_uuid},
        )


def get_buy_credits_action(env):
    """Redirect the user to the IAP store to top up phone service ("voip") credits.

    Opened in a new tab so the originating dialog (the buy wizard) survives.
    """
    action = env["iap.account"].get(PHONE_SERVICE_NAME).action_buy_credits()
    action["target"] = "new"
    return action

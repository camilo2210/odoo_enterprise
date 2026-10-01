from unittest.mock import Mock, patch

import requests

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger

from odoo.addons.voip.models.phone_service_api import PhoneServiceAPI
from odoo.addons.voip.tests.common_voip import forbid_phone_service_http


def _phone_service_response(status_code, payload):
    response = Mock()
    response.status_code = status_code
    response.json.return_value = payload
    return response


@tagged("post_install", "-at_install")
class TestPhoneServiceErrors(TransactionCase):
    def setUp(self):
        super().setUp()
        forbid_phone_service_http(self)

    def test_service_temporarily_unavailable_is_translated_client_side(self):
        with patch(
            "odoo.addons.voip.models.phone_service_api.requests.post",
            return_value=_phone_service_response(
                503,
                {
                    "error": "service_temporarily_unavailable",
                    "error_msg": "The phone service is temporarily unavailable. Please try again later.",
                    "error_code": 503,
                },
            ),
        ):
            with self.assertRaisesRegex(UserError, "temporarily unavailable"):
                PhoneServiceAPI(self.env)._call_phone_service("/api/phone_service/1/order_phone_numbers", {})

    def test_file_too_large_is_translated_client_side(self):
        with patch(
            "odoo.addons.voip.models.phone_service_api.requests.post",
            return_value=_phone_service_response(
                413,
                {
                    "error": "file_too_large",
                    "error_msg": "The uploaded file exceeds the maximum allowed size.",
                    "error_code": 413,
                },
            ),
        ):
            with self.assertRaisesRegex(UserError, "uploaded document is too large"):
                PhoneServiceAPI(self.env)._call_phone_service("/api/phone_service/1/order_phone_numbers", {})

    def test_forbidden_is_translated_client_side(self):
        with patch(
            "odoo.addons.voip.models.phone_service_api.requests.post",
            return_value=_phone_service_response(
                403,
                {
                    "error": "forbidden",
                    "error_msg": "You are not allowed to access this resource.",
                    "error_code": 403,
                },
            ),
        ):
            with self.assertRaisesRegex(UserError, "not associated with your database"):
                PhoneServiceAPI(self.env)._call_phone_service("/api/phone_service/1/order_phone_numbers", {})

    def test_invalid_subscription_is_translated_client_side(self):
        with patch(
            "odoo.addons.voip.models.phone_service_api.requests.post",
            return_value=_phone_service_response(
                401,
                {
                    "error": "invalid_subscription",
                    "error_msg": "Odoo database subscription is not valid.",
                    "error_code": 401,
                },
            ),
        ):
            with self.assertRaisesRegex(UserError, "subscription does not allow"):
                PhoneServiceAPI(self.env)._call_phone_service("/api/phone_service/1/order_phone_numbers", {})

    def test_insufficient_credits_is_translated_client_side(self):
        with patch(
            "odoo.addons.voip.models.phone_service_api.requests.post",
            return_value=_phone_service_response(
                402,
                {
                    "error": "insufficient_credits",
                    "error_msg": "Insufficient credits to order phone numbers.",
                    "error_code": 402,
                },
            ),
        ):
            with self.assertRaisesRegex(UserError, "enough credits"):
                PhoneServiceAPI(self.env)._call_phone_service("/api/phone_service/1/order_phone_numbers", {})

    def test_invalid_update_is_translated_client_side(self):
        with patch(
            "odoo.addons.voip.models.phone_service_api.requests.post",
            return_value=_phone_service_response(
                400,
                {
                    "error": "invalid_update",
                    "error_msg": "Update of this resource is not valid.",
                    "error_code": 400,
                },
            ),
        ):
            with self.assertRaisesRegex(UserError, "update is invalid"):
                PhoneServiceAPI(self.env)._call_phone_service("/api/phone_service/1/order_phone_numbers", {})

    def test_bad_request_is_translated_client_side(self):
        with patch(
            "odoo.addons.voip.models.phone_service_api.requests.post",
            return_value=_phone_service_response(
                400,
                {
                    "error": "bad_request",
                    "error_msg": "Invalid request parameters.",
                    "error_code": 400,
                },
            ),
        ):
            with self.assertRaisesRegex(UserError, "request sent to the Odoo Phone Service is invalid"):
                PhoneServiceAPI(self.env)._call_phone_service("/api/phone_service/1/order_phone_numbers", {})

    def test_missing_payload_is_translated_client_side(self):
        with patch(
            "odoo.addons.voip.models.phone_service_api.requests.post",
            return_value=_phone_service_response(
                400,
                {
                    "error": "missing_payload",
                    "error_msg": "Missing required payload in the request.",
                    "error_code": 400,
                },
            ),
        ):
            with self.assertRaisesRegex(UserError, "request sent to the Odoo Phone Service is incomplete"):
                PhoneServiceAPI(self.env)._call_phone_service("/api/phone_service/1/order_phone_numbers", {})

    def test_phone_number_not_releasable_is_translated_client_side(self):
        with patch(
            "odoo.addons.voip.models.phone_service_api.requests.post",
            return_value=_phone_service_response(
                409,
                {
                    "error": "phone_number_not_releasable",
                    "error_msg": "This phone number cannot be released in its current state.",
                    "error_code": 409,
                },
            ),
        ):
            with self.assertRaisesRegex(UserError, "cannot be released in its current state"):
                PhoneServiceAPI(self.env)._call_phone_service("/api/phone_service/1/release_phone_number", {})

    def test_pricing_expired_is_translated_client_side(self):
        with patch(
            "odoo.addons.voip.models.phone_service_api.requests.post",
            return_value=_phone_service_response(
                422,
                {
                    "error": "pricing_expired",
                    "error_msg": "Pricing has expired. Please search for available numbers again.",
                    "error_code": 422,
                },
            ),
        ):
            with self.assertRaisesRegex(UserError, "pricing has expired"):
                PhoneServiceAPI(self.env)._call_phone_service("/api/phone_service/1/order_phone_numbers", {})

    def test_pricing_expired_lists_problematic_numbers_client_side(self):
        with patch(
            "odoo.addons.voip.models.phone_service_api.requests.post",
            return_value=_phone_service_response(
                422,
                {
                    "error": "pricing_expired",
                    "error_msg": "Pricing has expired. Please search for available numbers again.",
                    "error_code": 422,
                    "details": {
                        "missing_numbers": ["+15551234567", "+15559876543"],
                    },
                },
            ),
        ):
            with self.assertRaises(UserError) as cm:
                PhoneServiceAPI(self.env)._call_phone_service("/api/phone_service/1/order_phone_numbers", {})
        message = str(cm.exception)
        self.assertIn("+15551234567", message)
        self.assertIn("+15559876543", message)

    def test_unmapped_error_key_falls_back_to_translated_default(self):
        with patch(
            "odoo.addons.voip.models.phone_service_api.requests.post",
            return_value=_phone_service_response(
                503,
                {
                    "error": "telnyx_rejected",
                    "error_msg": "Telnyx rejected the order.",
                    "error_code": 503,
                },
            ),
        ):
            with self.assertRaises(UserError) as cm:
                PhoneServiceAPI(self.env)._call_phone_service("/api/phone_service/1/order_phone_numbers", {})
        message = str(cm.exception)
        self.assertIn("The Odoo Phone Service is temporarily unavailable", message)
        self.assertNotIn("Telnyx", message)

    @mute_logger("odoo.addons.voip.models.phone_service_api")
    def test_network_failure_is_reported_without_retrying_request(self):
        with patch(
            "odoo.addons.voip.models.phone_service_api.requests.post",
            side_effect=requests.exceptions.Timeout,
        ) as mock_post:
            with self.assertRaisesRegex(UserError, "Could not reach the Odoo Phone Service"):
                PhoneServiceAPI(self.env)._call_phone_service(
                    "/api/phone_service/1/order_phone_numbers",
                    {},
                )

        mock_post.assert_called_once()

    def test_invalid_client_credentials_retries_registration_on_http_error(self):
        with patch(
            "odoo.addons.voip.models.phone_service_api.requests.post",
            side_effect=[
                _phone_service_response(
                    401,
                    {
                        "error": "authentication_failed",
                        "error_msg": "Authentication failed.",
                        "error_code": 401,
                    },
                ),
                _phone_service_response(200, {"success": True}),
                _phone_service_response(200, {"success": True, "data": []}),
            ],
        ) as mock_post:
            result = PhoneServiceAPI(self.env)._call_phone_service(
                "/api/phone_service/1/search_available_phone_numbers",
                {"payload": {"filter[country_code]": "BE"}},
            )

        self.assertEqual(result, {"success": True, "data": []})
        self.assertEqual(mock_post.call_count, 3)
        self.assertIn("account_token", mock_post.call_args_list[0].kwargs["json"])
        self.assertIn("client_uuid", mock_post.call_args_list[0].kwargs["json"])
        self.assertIn("client_secret", mock_post.call_args_list[0].kwargs["json"])
        self.assertIn("/api/phone_service/1/register_client", mock_post.call_args_list[1].args[0])

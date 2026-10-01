# Part of Odoo. See LICENSE file for full copyright and licensing details.

import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta
from pprint import pformat
from urllib.parse import quote_plus

import requests

from odoo import _, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tools import hmac as hmac_tool
from odoo.tools.urls import urljoin

from odoo.addons.sale_tiktok import const

_logger = logging.getLogger(__name__)


# === CUSTOM EXCEPTION CLASSES === #


class TikTokApiError(Exception):
    """Raised when the TikTok API returns an error."""

    def __init__(self, shop, operation, request_id, error_code, error_message):
        super().__init__(
            shop.env._(
                "In TikTok Shop '%(shop_name)s', an error %(error_code)s occurred during the "
                "TikTok API operation '%(operation)s' with request ID '%(request_id)s':"
                "\n%(error_message)s",
                shop_name=shop.name,
                operation=operation,
                request_id=request_id,
                error_code=error_code,
                error_message=error_message,
            )
        )


class TikTokRateLimitError(Exception):
    """Raised when the TikTok API rate limit is reached."""

    def __init__(self, operation):
        self.operation = operation
        super().__init__()


# === ONBOARDING === #


def generate_token(shop):
    shop.ensure_one()
    timestamp = int(fields.Datetime.now().timestamp())
    signature = hmac_tool(shop.env, "tiktok-authorization-request", f"{shop.id}|{timestamp}")
    return {"shop_id": shop.id, "timestamp": timestamp, "signature": signature}


def get_public_sign(shop, path, params=None, body=None):
    """Generate the correct HMAC-SHA256 sign based on TikTok Shop's rules.
    See also: https://partner.tiktokshop.com/docv2/page/sign-your-api-request.

    :param shop: tiktok.shop
    :param path: The API endpoint path (e.g., /authorization/202309/shops)
    :param params: Query parameters dict (excluding 'sign' and 'access_token')
    :param body: JSON-serializable dict (e.g., POST body) or None
    :return: hex digest HMAC-SHA256 signature
    """
    shop.ensure_one()
    if body is None:
        body = {}
    if params is None:
        params = {}

    # Filter and sort query keys except 'sign' and 'access_token'
    filtered_params = {k: v for k, v in params.items() if k not in ["sign", "access_token"]}
    sorted_keys = sorted(filtered_params.keys())

    # Concatenate keys and values then combine with path
    concatenated_params = "".join(f"{k}{filtered_params[k]}" for k in sorted_keys)
    base_string = f"{path}{concatenated_params}"
    # Append JSON body if content-type is not multipart (e.g., if method is POST)
    base_string += json.dumps(body) if body else ""
    # Prepend and append app_secret
    sign_string = f"{shop.app_secret}{base_string}{shop.app_secret}"

    return hmac.new(shop.app_secret.encode(), sign_string.encode(), hashlib.sha256).hexdigest()


# === API COMMUNICATIONS === #


def request_access_token(shop, authorization_code=None):
    """Request the access tokens for a specific shop.

    :param shop: tiktok.shop
    :param str authorization_code: The authorization code to request the access token
    :return: The response content of the request
    :rtype: dict
    :raise: TikTokApiError if the request fails or if the authorization code
        or refresh token is missing
    """
    shop.ensure_one()

    if authorization_code:
        params = {
            "app_key": shop.app_key,
            "app_secret": shop.app_secret,
            "auth_code": authorization_code,
            "grant_type": "authorized_code",
        }
        operation = "get_token"
    elif shop.refresh_token:
        params = {
            "app_key": shop.app_key,
            "app_secret": shop.app_secret,
            "refresh_token": shop.refresh_token,
            "grant_type": "refresh_token",
        }
        operation = "refresh_token"
    else:
        raise UserError(
            _(
                "No authorization code or refresh token found for shop %(shop_name)s.",
                shop_name=shop.name,
            )
        )

    return make_tiktok_api_request(shop, operation, params=params)


def make_tiktok_api_request(
    shop, operation, params=None, path_params=None, body=None
):
    """Send an API request to TikTok Shop.

    :param tiktok.shop shop: The TikTok shop on behalf of which the request is made
    :param str operation: API operation name from const.API_OPERATIONS_MAPPING
    :param dict params: Query parameters
    :param str path_params: Path parameters
    :param dict body: Request body
    :return: The response content of the request
    :rtype: dict
    :raise TikTokApiError: if the request fails or if the access token is missing
    :raise TikTokRateLimitError: if the rate limit is reached
    :raise ValidationError: if the response is not valid JSON
    """
    shop.ensure_one()
    if body is None:
        body = {}
    if params is None:
        params = {}
    headers = {}

    operation_conf = const.API_OPERATIONS_MAPPING[operation]
    api_type = operation_conf["api_type"]
    method = operation_conf.get("method", "GET")
    url_path = operation_conf["url_path"]
    if path_params:
        encoded_path_params = {
            key: quote_plus(str(value)) for key, value in path_params.items()
        }
        url_path = url_path.format_map(encoded_path_params)

    if api_type != "public":  # Require an access token
        # Check token expiration and refresh if needed (1 hour before expiry)
        now = fields.Datetime.now()
        if now > shop.access_token_expire_datetime - timedelta(minutes=5):
            response = request_access_token(shop)
            shop.write({
                "access_token": response["access_token"],
                "access_token_expire_datetime": datetime.fromtimestamp(
                    response["access_token_expire_in"]
                ),
                "refresh_token": response["refresh_token"],
                "refresh_token_expire_datetime": datetime.fromtimestamp(
                    response["refresh_token_expire_in"]
                ),
            })

        timestamp = int(fields.Datetime.now().timestamp())
        params["app_key"] = shop.app_key
        params["timestamp"] = timestamp
        params["sign"] = get_public_sign(shop, url_path, params=params, body=body)
        headers["x-tts-access-token"] = shop.access_token
        url = const.API_ENDPOINTS
    else:
        url = const.AUTH_URL

    try:
        resp = requests.request(
            method=method,
            url=urljoin(url, url_path),
            headers=headers,
            params=params,
            json=body,
            timeout=10,
        )
        response_content = resp.json()
    except requests.exceptions.RequestException as exc:
        error_message = shop.env._("Request exception during TikTok Shop API operation")
        raise TikTokApiError(shop, operation, "N/A", "N/A", error_message) from exc
    except ValueError as exc:
        raise ValidationError(shop.env._("Invalid JSON response received from TikTok.")) from exc
    if response_content.get("code") == const.TIKTOK_API_ERROR_CODES["RATE_LIMIT"]:
        raise TikTokRateLimitError(operation)

    # Anything other than 0 is considered unsucessful
    # Exception when fetching 'package'. Needed in order to keep track of the label status
    if response_content.get("code") != 0 and api_type != "package":
        raise TikTokApiError(
            shop,
            operation,
            "N/A",
            response_content.get("code"),
            response_content.get("message")
        )

    if (
        api_type != "public" and operation != "get_authorized_shop"
    ):  # public API response return access token
        _logger.info("TikTok Operation %s: \n%s", operation, pformat(response_content))

    return response_content.get("data", {})

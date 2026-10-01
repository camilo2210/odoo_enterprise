# Part of Odoo. See LICENSE file for full copyright and licensing details.

import hashlib
import hmac
import logging
from datetime import UTC, datetime, timedelta
from pprint import pformat

import requests

from odoo import fields
from odoo.exceptions import UserError
from odoo.http import request
from odoo.tools import LazyTranslate
from odoo.tools import hmac as hmac_tool
from odoo.tools.urls import urljoin

from odoo.addons.sale_lazada import const

_lt = LazyTranslate(__name__)
_logger = logging.getLogger(__name__)


class LazadaApiError(Exception):
    """Raised when the Lazada API returns an error."""

    def __init__(self, shop, operation, request_id, error_code, error_message):
        super().__init__(
            shop.env._(
                "In Lazada Shop '%(shop_name)s', an error %(error_code)s occurred during the "
                "Lazada API operation '%(operation)s' with request ID '%(request_id)s':"
                "\n%(error_message)s",
                shop_name=shop.name,
                operation=operation,
                request_id=request_id,
                error_code=error_code,
                error_message=error_message,
            )
        )


class LazadaRateLimitError(Exception):
    """Raised when the Lazada API rate limit is reached."""

    def __init__(self, operation):
        self.operation = operation
        super().__init__()


def get_lazada_aggregated_status(statuses):
    """Determine overall delivery status from statuses."""
    unique_statuses = list(set(statuses))
    if len(unique_statuses) == 1:
        return unique_statuses[0]
    return "manual"


def lazada_timestamp_to_datetime(timestamp):
    """Convert Lazada timestamp string to Odoo datetime.

    :param str timestamp: Timestamp in format 'YYYY-MM-DD HH:MM:SS %z'
    :return: Naive datetime in UTC
    :rtype: datetime
    """
    try:
        return (
            datetime
            .strptime(timestamp, "%Y-%m-%d %H:%M:%S %z")
            .astimezone(UTC)
            .replace(tzinfo=None)
        )
    except ValueError:
        return fields.Datetime.now()


def get_public_sign(shop, timestamp):
    """Given the request params, returns the signing string used to sign the request.

    :param shop: lazada.shop record
    :param int timestamp: The timestamp of the request
    :return: The public signing string
    :rtype: str
    """
    shop.ensure_one()
    return hmac_tool(request.env(su=True), "lazada-authorization-request", f"{shop.id}|{timestamp}")


def get_api_sign(shop, operation, params):
    """Generate HMAC signature for authenticated API requests.

    :param shop: lazada.shop record with app_secret
    :param str operation: API operation name
    :param dict params: Parameters to sign
    :return: HMAC-SHA256 signature in uppercase
    """
    shop.ensure_one()
    return (
        hmac
        .new(
            shop.app_secret.encode(),
            _get_request_signing_string(operation, params).encode(),
            hashlib.sha256,
        )
        .hexdigest()
        .upper()
    )


def _get_request_signing_string(operation, params):
    path = f"/{const.API_OPERATIONS_MAPPING[operation]['url_path']}"
    return _get_public_signing_string(path, params)


def _get_public_signing_string(path, params):
    sorted_params = sorted(params)
    signing_string = "".join(f"{key}{params[key]}" for key in sorted_params)
    return f"{path}{signing_string}"


def _get_error_message(response_content):
    message = response_content.get("message", "")
    if response_content.get("result"):
        message += "\n".join(response_content["result"].get("error_msg", ""))
    if response_content.get("detail"):  # For error handling of UpdateSellerQuantity
        for item in response_content["detail"]:
            message += "\n".join(
                f"For product SKU {item.get('sku')}, [{item.get('code')}] - {item.get('message')}"
            )
    return message


def _get_api_endpoint(shop, operation):
    if const.API_OPERATIONS_MAPPING[operation]["api_type"] == "public":
        return const.API_ENDPOINTS["ALL"]
    if shop:
        return shop.api_endpoint
    raise UserError(_lt("Cannot determine the API endpoint for the operation."))


def request_access_token(shop, authorization_code=None):
    """Request or refresh access token from Lazada API.

    :param lazada.shop shop: The Lazada shop for which an access token is requested.
    :param str authorization_code: If provided, requests a new refresh token and access token.
    """
    shop.ensure_one()
    params = {}
    if authorization_code:
        params["code"] = authorization_code
        operation = "GenerateAccessToken"
    elif shop.refresh_token:
        params["refresh_token"] = shop.refresh_token
        operation = "RefreshAccessToken"
    else:
        raise UserError(
            shop.env._(
                "No authorization code or refresh token found for shop %(shop_name)s.",
                shop_name=shop.name,
            )
        )

    return make_lazada_api_request(operation, shop, params=params, method="POST")


def make_lazada_api_request(operation, shop, params=None, method="GET"):
    """Make an authenticated API request to Lazada.

    Automatically handles token refresh, rate limiting, and error handling.

    :param str operation: API operation name from const.API_OPERATIONS_MAPPING
    :param lazada.shop shop: The Lazada shop on behalf of which the request is made
    :param dict params: URL query parameters
    :param str method: HTTP method (GET, POST, etc.)
    :return: Response data from Lazada API
    :raises LazadaRateLimitError: When API rate limit is reached
    :raises LazadaApiError: When API request fails
    :raises UserError: When API request fails
    """
    shop.ensure_one()

    params = params or {}
    api_type = const.API_OPERATIONS_MAPPING[operation]["api_type"]

    if api_type != "public":  # Require an access token
        if (
            not shop.access_token
            or not shop.access_token_expiration_date
            or shop.access_token_expiration_date < fields.Datetime.now() + timedelta(minutes=5)
        ):
            token_data = request_access_token(shop)
            expiration_date = fields.Datetime.now() + timedelta(seconds=token_data["expires_in"])
            refresh_expiration_date = fields.Datetime.now() + timedelta(
                seconds=token_data["refresh_expires_in"]
            )
            shop.write({
                "access_token": token_data["access_token"],
                "access_token_expiration_date": expiration_date,
                "refresh_token": token_data["refresh_token"],
                "refresh_token_expiration_date": refresh_expiration_date,
            })
        params["access_token"] = shop.access_token

    api_endpoint = _get_api_endpoint(shop, operation)
    path = const.API_OPERATIONS_MAPPING[operation]["url_path"]
    timestamp = f"{int(fields.Datetime.now().timestamp())}000"
    signing_params = {
        **params,
        "app_key": shop.app_key,
        "timestamp": timestamp,
        "sign_method": "sha256",
    }
    signed_params = {**signing_params, "sign": get_api_sign(shop, operation, signing_params)}
    resp = requests.request(method, urljoin(api_endpoint, path), params=signed_params, timeout=10)
    if resp.status_code == 429:
        raise LazadaRateLimitError(operation)
    if resp.status_code != 200:
        raise LazadaApiError(shop, operation, "N/A", resp.status_code, resp.text)
    response_content = resp.json()

    # Simple error catching with a clear message on the issue.
    if response_content.get("code") != "0":
        if response_content.get("code") in ["901", "SellerCallLimit"]:
            raise LazadaRateLimitError(operation)

        if response_content.get("code") in ("InvalidAccessToken", "IllegalAccessToken"):
            shop.write({"access_token": None, "access_token_expiration_date": None})

        error_code = response_content.get("code")
        message = _get_error_message(response_content)
        raise LazadaApiError(
            shop, operation, response_content.get("request_id"), error_code, message
        )
    if api_type != "public":  # public API response return access token
        _logger.info("Operation %s: \n%s", operation, pformat(response_content))

    return response_content

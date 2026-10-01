# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
import requests
from typing import Any, Union
from requests.exceptions import RequestException
from urllib.parse import quote

from odoo import _, fields
from odoo.tools.urls import urljoin
from odoo.addons.pos_platform_order.models.platform_order_provider import PlatformOrderProvider
from odoo.addons.pos_platform_order.models.platform_order_entity import PlatformOrderEntity

_logger = logging.getLogger(__name__)


class GrabFoodClient:
    BASE_OAUTH_URL = "https://api.grab.com"
    BASE_API_URL_PROD = "https://partner-api.grab.com/grabfood/"
    BASE_API_URL_SANDBOX = "https://partner-api.grab.com/grabfood-sandbox/"

    TOKEN_ENDPOINT = "/grabid/v1/oauth2/token"
    TOKEN_SCOPE = "food.partner_api"
    GRANT_TYPE = "client_credentials"

    JSON_HEADER = {"Content-Type": "application/json"}

    def __init__(self, store: PlatformOrderEntity):
        self.store = store
        self.provider = store.provider_id
        self.session = requests.Session()
        self._prepare_session()

    @property
    def _api_base_url(self) -> str:
        if self.provider.state == 'enabled':
            return self.BASE_API_URL_PROD
        return self.BASE_API_URL_SANDBOX

    def _prepare_session(self) -> None:
        """
        Validates the current access token and fetches a new one if expired.
        Prepares the request session with the necessary headers.
        """
        access_token = self.provider.grabfood_access_token
        token_expiry = self.provider.grabfood_token_expiry

        if not access_token or not token_expiry or token_expiry <= fields.Datetime.now():
            access_token = self._fetch_and_store_new_token()

        self.session.headers.update(self.JSON_HEADER)
        self.session.headers["Authorization"] = f"Bearer {access_token}"

    def _fetch_and_store_new_token(self) -> str:
        _logger.info("Fetching new GrabFood access token for provider %s.", self.provider.id)
        client_id = self.provider.grabfood_client_id
        client_secret = self.provider.grabfood_client_secret

        response = self._request_access_token(client_id, client_secret)

        if response.status_code == 200:
            response_json = response.json()
            token = response_json['access_token']
            self.provider._grabfood_handle_oauth_response(response_json)
            return token

        _logger.error("Failed to retrieve GrabFood access token: %s %s", response.status_code, response.text)
        response.raise_for_status()
        raise ValueError(_("GrabFood access token retrieval failed."))

    def _make_api_request(self, method: str, endpoint: str, **kwargs: Any) -> Union[dict, list, None]:
        url = urljoin(self._api_base_url, endpoint)

        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else None
        except RequestException as error:
            _logger.warning('Connection Error: %r with the given URL %r', error, url)
            raise

    # --- PUBLIC API METHODS ---

    def update_store_delivery_hours(self, service_hours: dict[str, list]) -> None:
        endpoint = f"partner/v1/merchants/{quote(self.store.external_id)}/store/opening-hours"
        payload = {"openingHour": service_hours, "force": False}
        self._make_api_request("PUT", endpoint, json=payload)

    def request_sync_menu(self) -> None:
        endpoint = "partner/v1/merchant/menu/notification"
        payload = {"merchantID": self.store.external_id}
        self._make_api_request("POST", endpoint, json=payload)

    def batch_update_menu(self, menu_items: list) -> None:
        endpoint = "partner/v1/batch/menu"
        payload = {
            "merchantID": self.store.external_id,
            "field": "ITEM",
            "menuEntities": menu_items,
        }
        self._make_api_request("PUT", endpoint, json=payload)

    def set_food_ready(self, order_ref, order_type) -> None:
        endpoint = "partner/v1/orders/mark"
        payload = {"orderID": order_ref, "markStatus": 2 if order_type == 'dine_in' else 1}
        self._make_api_request("POST", endpoint, json=payload)

    def update_order_state(self, order_ref, state) -> None:
        endpoint = "partner/v1/order/prepare"
        payload = {"orderID": order_ref, "toState": state}
        self._make_api_request("POST", endpoint, json=payload)

    def cancel_order(self, order_ref: str, reason_code: int):
        endpoint = 'partner/v1/order/cancel'
        payload = {"orderID": order_ref, "merchantID": self.store.external_id, "cancelCode": reason_code}
        self._make_api_request("PUT", endpoint, json=payload)

    # --- STATIC AND CLASS METHODS ---

    @classmethod
    def test_connection(cls, provider: PlatformOrderProvider):
        client_id = provider.grabfood_client_id
        client_secret = provider.grabfood_client_secret

        try:
            _logger.info("Testing GrabFood connection for provider ID %s", provider.id)
            response = cls._request_access_token(client_id, client_secret)

            if response.status_code == 200:
                return {'success': True}
            else:
                error_message = f"Failed with status code {response.status_code}."
                try:
                    error_details = response.json()
                    error_message += f" Error: {error_details.get('error_description', error_details.get('error', 'No details'))}"
                except ValueError:
                    error_message += f" Response: {response.text}"
                _logger.warning("GrabFood connection test failed: %s", error_message)
                return {'success': False, 'message': error_message}

        except RequestException as error:
            _logger.error("GrabFood connection test encountered an error: %s", error)
            raise

    @staticmethod
    def _request_access_token(client_id: str, client_secret: str) -> requests.Response:
        url = urljoin(GrabFoodClient.BASE_OAUTH_URL, GrabFoodClient.TOKEN_ENDPOINT)
        payload = {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": GrabFoodClient.GRANT_TYPE,
            "scope": GrabFoodClient.TOKEN_SCOPE,
        }
        try:
            # Use a timeout for all external requests
            response = requests.post(url, headers=GrabFoodClient.JSON_HEADER, json=payload, timeout=10)
            return response
        except RequestException as error:
            _logger.error("GrabFood token request failed due to a network error: %s", error)
            raise

# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
from pprint import pformat
from typing import Literal
from urllib.parse import quote

import requests
from requests.exceptions import RequestException

from odoo.tools.urls import urljoin

from odoo.addons.pos_platform_order.models.platform_order_entity import (
    PlatformOrderEntity,
)
from odoo.addons.pos_platform_order_gofood.utils.typing import GoFoodResponse

_logger = logging.getLogger(__name__)


class GoFoodClient:

    def __init__(self, store: PlatformOrderEntity):
        self.store = store
        self.provider = store.provider_id
        self.base_url = store.env.company.get_base_url()

        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
        })

    def _get_api_url(self):
        return "https://api.gobiz.co.id" if self.store.provider_id.state == 'enabled' else "https://api.partner-sandbox.gobiz.co.id"

    def _get_oauth_url(self):
        return "https://accounts.go-jek.com" if self.store.provider_id.state == 'enabled' else "https://integration-goauth.gojekapi.com"

    def _fetch_access_token(self):
        if 'Authorization' in self.session.headers:
            return

        scopes = 'partner:outlet:read partner:outlet:write gofood:outlet:write gofood:catalog:read gofood:catalog:write gofood:order:read gofood:order:write'
        access_url = urljoin(self._get_oauth_url(), '/oauth2/token')
        appid = self.store.provider_id.gofood_appid
        secret = self.store.provider_id.gofood_secret
        response = self.session.post(access_url, auth=(appid, secret), data={
            'grant_type': 'client_credentials',
            'scope': scopes,
        }, headers={
            'Content-Type': 'application/x-www-form-urlencoded',
        })

        if response.status_code == 200:
            token_data = response.json()
            self.session.headers['Authorization'] = 'Bearer ' + token_data['access_token']
        else:
            _logger.error('Failed to fetch access token: %s', response.text)

    def _make_api_request(self, endpoint, method='POST', data=None, timeout=10) -> GoFoodResponse:
        """
        Make an api call, return response for multiple api requests of gofood.
        """
        self._fetch_access_token()
        url = self._get_api_url() + endpoint

        try:
            response = self.session.request(method, url, json=data, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except RequestException as error:
            _logger.warning('Connection Error: %r with the given URL %r', error, url)
            raise

    def request_sync_menu(self, payload) -> GoFoodResponse:
        """
        Sync menu in GoFood.
        - Sync categories, products, attributes, values and taxes.
        - Note: This will fail to sync menu in localhost because GoFood couldn't fetch the food images.
        """
        self._configure_webhook()
        endpoint = f'/integrations/gofood/outlets/{quote(self.store.external_id)}/v1/catalog'

        return self._make_api_request(endpoint, method='PUT', data=payload, timeout=90)

    def _configure_webhook(self):
        """
        Check and register webhook if the base url is changed.
        """
        endpoint = f"/integrations/partner/outlets/{quote(self.store.external_id)}/v1/notification-subscriptions"
        response_json = self._make_api_request(endpoint, method='GET')

        data = response_json.get('data') or {}
        existing_webhooks = data.get('subscriptions', [])

        base_events = ['awaiting_merchant_acceptance', 'merchant_accepted', 'driver_otw_pickup', 'driver_arrived', 'placed', 'completed', 'cancelled']
        required_events = ['gofood.order.' + event for event in base_events]

        controller_url = urljoin(self.base_url, '/gofood/notification')

        existing_events_map = {webhook.get('event'): webhook for webhook in existing_webhooks if webhook.get('event')}

        for event, webhook in existing_events_map.items():
            url = webhook.get('url')
            if not url or url != controller_url:
                _logger.info("Webhook URL for event %s does not match expected URL %s, updating...", event, controller_url)
                try:
                    self._update_webhook(webhook)
                except RequestException as e:
                    _logger.error("Failed to update webhook for %s: %s", event, e)

        missing_events = [event for event in required_events if event not in existing_events_map]

        if missing_events:
            _logger.info("Missing webhooks found for events: %s. Registering them...", missing_events)
            self._register_webhooks(missing_events)
        else:
            _logger.info("All GoFood webhooks are fully configured.")

    def _register_webhooks(self, events_to_register):
        endpoint = f"/integrations/partner/outlets/{quote(self.store.external_id)}/v1/notification-subscriptions"
        controller_url = urljoin(self.base_url, '/gofood/notification')

        for event in events_to_register:
            payload = {
                'event': event,
                'url': controller_url,
                'active': True,
            }
            try:
                response = self._make_api_request(endpoint, method='POST', data=payload)
                _logger.info("Event (%s) webhook successfully registered. Response: %s", event, pformat(response))
            except RequestException as e:
                _logger.error("Failed to register webhook for event %s: %s", event, e)

    def _update_webhook(self, webhook):
        endpoint = f"/integrations/partner/outlets/{quote(self.store.external_id)}/v1/notification-subscriptions/{webhook['id']}"
        payload = {
            'event': webhook['event'],
            'url': urljoin(self.base_url, '/gofood/notification'),
            'active': True,
        }
        return self._make_api_request(endpoint, method='PUT', data=payload)

    def set_food_ready(self, order_ref):
        endpoint = f'/integrations/gofood/outlets/{quote(self.store.external_id)}/v1/orders/delivery/{order_ref}/food-prepared'
        payload = {
            'country_code': self.store.company_id.country_code,
        }
        return self._make_api_request(endpoint, method='PUT', data=payload)

    def accept_order(self, order_ref):
        endpoint = f'/integrations/gofood/outlets/{quote(self.store.external_id)}/v1/orders/delivery/{order_ref}/accepted'  # Only delivery is supported
        return self._make_api_request(endpoint, method='PUT')

    def reject_order(self, order_ref: str, cancel_reason_code: Literal["HIGH_DEMAND", "RESTAURANT_CLOSED", "ITEMS_OUT_OF_STOCK", "OTHERS"], cancel_reason_description: str):
        endpoint = f'/integrations/gofood/outlets/{self.store.external_id}/v1/orders/delivery/{order_ref}/cancelled'
        payload = {
            "cancel_reason_code": cancel_reason_code,
            "cancel_reason_description": cancel_reason_description,   # Min length = 3
        }
        return self._make_api_request(endpoint, method='PUT', data=payload)

    def batch_update_menu(self, payload):
        endpoint = f'/integrations/gofood/outlets/{quote(self.store.external_id)}/v2/menu_item_stocks'
        return self._make_api_request(endpoint, method='PATCH', data=payload)

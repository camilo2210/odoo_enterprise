# Part of Odoo. See LICENSE file for full copyright and licensing details.

import contextlib
import json
import math
import requests
import time
from urllib.parse import quote

from odoo import _
from odoo.tools import format_duration

from .urbanpiper_translation import get_urbanpiper_translation

URBANPIPER_EVENT_TYPES = ['order_placed', 'store_creation', 'store_action', 'inventory_update', 'item_state_toggle', 'order_status_update', 'rider_status_update']

API_DEVELOPMENT_URL = 'https://pos-int.urbanpiper.com'
API_PRODUCTION_URL = 'https://api.urbanpiper.com'
API_TIMEOUT = 90  # Timeout set higher because menu sync can takes more time for large datasets


class UrbanPiperConnector:
    def __init__(self, store):
        # Initialize utils that will be reused across UrbanPiper operations
        self.store = store
        self.env = store.env
        self.sudo_env = store.sudo().env
        self.pos_config = store.config_id

        # By default all odoo instances are in production mode unless specified
        self.is_production = not self.store.use_test_mode
        self.api_url = API_DEVELOPMENT_URL if not self.is_production else API_PRODUCTION_URL

        user_name = store.sudo().urbanpiper_username
        api_key = store.sudo().urbanpiper_apikey
        self.has_credentials = user_name and api_key
        self.has_demo_credentials = user_name == 'demo' or api_key == 'demo'
        # Use a session to reuse HTTP connections, improve performance and manage settings
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Authorization': f'apikey {user_name}:{api_key}',
        })

    def make_request(self, endpoint, method, data=None):
        """
        Make an api call, return response for multiple api requests of UrbanPiper.
        endpoint: API endpoint to call (string)
        method: HTTP method to use (string: 'GET', 'POST', 'PUT', 'DELETE')
        data: Data to send in the request body (dict)
        """
        log_urbanpiper = self.pos_config.log_urbanpiper

        if not self.has_credentials or self.has_demo_credentials:
            if not self.has_demo_credentials:
                log_urbanpiper('Invalid Credentials for making UrbanPiper API request.', 'Urbanpiper Invalid Credentials', 'info', func='make_request')
            return {}

        try:
            response = self.session.request(method, self.api_url + endpoint, json=data, timeout=API_TIMEOUT)
            response.raise_for_status()
        except requests.exceptions.ConnectionError as error:
            log_urbanpiper(f"Connection Error: {error} with the given URL {self.api_url + endpoint}", 'Urbanpiper Connection Error', func='make_request')
            return {'errors': {'timeout': _('Cannot reach the server. Please try again later.')}}
        except requests.exceptions.HTTPError as error:
            message = error.args[0] if len(error.args) > 0 else f"HTTP {response.status_code} Error"
            with contextlib.suppress(json.decoder.JSONDecodeError):
                message = response.json().get("message")
            log_urbanpiper(f'HTTPError: {message or error}', 'Urbanpiper HTTPError', func='make_request')
            return {'errors': {'HTTPError': message or str(error)}}
        except requests.exceptions.JSONDecodeError as error:
            log_urbanpiper(f'JSONDecodeError: {error}', 'Urbanpiper JSONDecodeError', func='make_request')
            return {'errors': {'JSONDecodeError': _('Failed to parse server response.')}}

        try:
            response_json = response.json()
            log_urbanpiper(f'UrbanPiper {method} Request to {endpoint} succeeded with response: {response_json}', 'Urbanpiper Response', 'info', log_xml=False)
        except json.decoder.JSONDecodeError as error:
            log_urbanpiper(f'JSONDecodeError: {error}', 'Urbanpiper JSONDecodeError', func='make_request')
            return {'errors': {'JSONDecodeError': _('Failed to parse server response.')}}
        return response_json

    def post_webhooks(self):
        """
        Register webhooks in UrbanPiper. This can be done in a batch for multiple event types.
        Doc: https://api-docs.urbanpiper.com/downstream/api/endpoints/setting-up-webhooks

        NOTE: This endpoint is limited to 5 calls per minute, if you exceed this limit, you may
        receive a 429 Too Many Requests response.
        """
        base_url = self.sudo_env['ir.config_parameter'].get_str('web.base.url')
        db_uuid = self.sudo_env['ir.config_parameter'].get_str('database.uuid')
        self.store.is_webhook_register = True
        self.env.cr.commit()

        webhook_url = f'{base_url}/pos_urban_piper/v1/{db_uuid}/'
        if not self.is_production:
            webhook_url = f'{base_url}/pos_urban_piper/v1/dev/'  # To avoid poluting test atlas webhooks
        webhooks = self.env['pos.urban.piper.webhook'].search([
            ('webhook_url', '=', webhook_url),
            ('store_id', '=', self.store.id),
        ])
        existing_event_types = webhooks.mapped('event_name')

        for event_type in URBANPIPER_EVENT_TYPES:
            data = {
                'active': True,
                'event_type': event_type,
                'retrial_interval_units': 'seconds',
                'url': webhook_url,
            }
            request_method = 'POST'
            request_url = '/external/api/v1/webhooks/'

            if event_type in existing_event_types:
                # Only update the already-synced `order_placed` webhook; skip others
                if event_type != 'order_placed':
                    continue
                webhook = webhooks.filtered_domain([('event_name', '=', event_type)])[0]
                data['webhook_id'] = webhook.webhook_id
                request_method = 'PUT'
                request_url = f'/external/api/v1/webhooks/{webhook.webhook_id}/'

            response = self.make_request(request_url, request_method, data=data)
            if response.get('status') == 'success' and response.get('webhook_id'):
                self.env['pos.urban.piper.webhook'].create({
                    'webhook_id': response['webhook_id'],
                    'webhook_url': webhook_url,
                    'event_name': event_type,
                    'store_id': self.store.id
                })
                self.env.cr.commit()  # Commit after each successful webhook registration

            time.sleep(12)  # To avoid hitting rate limits

    def post_stores(self):
        """
        Create stores in UrbanPiper.
        Doc: https://api-docs.urbanpiper.com/downstream/api/endpoints/stores/add-update-stores

        NOTE: This endpoint is limited to 5 calls per minute, if you exceed this limit, you may
        receive a 429 Too Many Requests response.
        """
        name_translations = self.store.get_field_translations('name')
        store_preset = self.store.preset_id
        timings = []
        if store_preset.use_timing:
            WEEKDAY_MAP = dict(enumerate(
                ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            ))
            timings = [{
                'day': WEEKDAY_MAP[int(attendance.dayofweek)],
                'slots': [{
                    'start_time': '23:59:00' if math.isclose(attendance.hour_from, 24.0) else f'{format_duration(attendance.hour_from)}:00',
                    'end_time': '23:59:00' if math.isclose(attendance.hour_to, 24.0) else f'{format_duration(attendance.hour_to)}:00'
                }],
            } for attendance in store_preset.attendance_ids]

        data = {
            'stores': [{
                'name': self.store.name,
                'city': self.store.city,
                'ref_id': self.store.store_identifier,
                'min_pickup_time': self.store.minimum_preparation_time * 60,
                'translations': get_urbanpiper_translation({'name': name_translations}),
                'timings': timings,
            }]
        }
        return self.make_request('/external/api/v1/stores/', 'POST', data=data)

    def post_locations_status(self, status=False, provider_ids=[]):
        """
        Change store status in UrbanPiper.
        Doc: https://api-docs.urbanpiper.com/downstream/api/endpoints/stores/store-toggle

        NOTE: This endpoint is limited to 20 calls per minute, if you exceed this limit, you may
        receive a 429 Too Many Requests response.
        """
        if not provider_ids:
            return False
        providers = self.store.delivery_provider_ids
        platforms = [p.technical_name for p in providers if p.id in provider_ids]
        self.make_request('/hub/api/v1/location/', 'POST', data={
            'location_ref_id': self.store.store_identifier,
            'platforms': platforms,
            'action': (status and 'enable') or 'disable',
        })

    def post_location_inventory(self, flush=False):
        """
        Synchronize POS inventory with UrbanPiper. Products that are not associated with any category are
        mapped to the “Other” category during synchronization.
        Doc: https://api-docs.urbanpiper.com/downstream/api/endpoints/menu/add-update-menu

        NOTE: This endpoint is limited to 12 calls per minute, if you exceed this limit, you may
        receive a 429 Too Many Requests response.
        """
        # Avoid using flush=True on every request - UrbanPiper only accepts
        # product creation in batches of up to 500 records.
        # For larger syncs, forcing flush=True would prevent processing more
        # than 500 products ever.
        master_flush = False  # Master flush clears all existing master data (categories, option groups, taxes, charges)on UrbanPiper
        data = {
            'flush_options': flush,
            'flush_items': flush,
            'flush_categories': master_flush,
            'flush_option_groups': master_flush,
            'flush_taxes': master_flush,
            'flush_charges': master_flush,
            'categories': [],
            'items': [],
            'option_groups': [],
            'options': [],
            'taxes': [],
            'charges': [],
        }

        store_identifier = quote(self.store.store_identifier, safe='')
        endpoint = f'/external/api/v1/inventory/locations/{store_identifier}/'
        products = self.env['product.template'].search([
            ('urbanpiper_store_ids', 'in', self.store.ids),
            ('type', '!=', 'combo'),
            ('available_in_pos', '=', True),
        ])
        if not products:
            return {
                'status': 'warning',
                'message': _('There are no products to sync.')
            }
        is_required_other_category = any(not product.pos_categ_ids for product in products)

        # All models have their own method to prepare data for UrbanPiper
        data['option_groups'] = products._prepare_urbanpiper_option_groups_data(self.store)  # Attribute lines eg. 'Sides'
        data['options'] = products.attribute_line_ids.product_template_value_ids\
            .filtered(lambda ptav: ptav.ptav_active)._prepare_urbanpiper_data(self.store)  # Attribute values eg. 'Fries', 'Salad'
        data['categories'] = products.pos_categ_ids._prepare_urbanpiper_data(self.store, is_required_other_category)
        data['items'] = products._prepare_urbanpiper_data(self.store)
        data['taxes'] = products._prepare_urbanpiper_taxes_data(self.store)
        data['charges'] = products._prepare_urbanpiper_charges_data(self.store)

        response = self.make_request(endpoint, 'POST', data=data)
        if response.get('status') == 'success':
            self.store._update_urbanpiper_synced_json(products)
            # for tracking a date & time of menu syncing
            self.store.message_post(
                body=_('Store menu successfully synced on UrbanPiper (%s products)', len(data['items']))
            )
            self.post_category_timing_groups(products.pos_categ_ids)
        return response

    def post_category_timing_groups(self, pos_categories):
        """
        Sync POS product categories with UrbanPiper category timing groups.
        Doc: https://api-docs.urbanpiper.com/downstream/api/endpoints/menu/category-timing-groups

        NOTE: Limited to 10 requests per minute; exceeding this may raise a 429 response.
        """
        pos_categories = pos_categories.filtered(lambda categ: (categ.hour_until - categ.hour_after) != 0)
        if not pos_categories:
            self.pos_config.log_urbanpiper('UrbanPiper: No POS product categories available for timing group sync', 'UrbanPiper No Category Found', func='post_category_timing_groups')
        week_days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        data = [{
            'title': f'{category.name} Timings',
            'category_ref_ids': [str(category.id)],
            'day_slots': [{
                'day': day,
                'slots': [{
                    'start_time': '23:59' if category.hour_after == 24.0 else format_duration(category.hour_after),
                    'end_time': '23:59' if category.hour_until == 24.0 else format_duration(category.hour_until)
                }]
            } for day in week_days]
        } for category in pos_categories]

        return self.make_request('/external/api/v1/inventory/categories/timing-groups/', 'POST', data={'timing_groups': data})

    def post_hub_item_toggle(self, product_ids, status=False):
        """
        Enable/Disable product on urbanPiper store.
        Doc: https://api-docs.urbanpiper.com/downstream/api/endpoints/menu/menu-toggle

        NOTE: This endpoint is limited to 100 calls per minute, if you exceed this limit, you may
        receive a 429 Too Many Requests response.
        """
        if not product_ids:
            return {}
        response = self.make_request('/hub/api/v1/items/', 'POST', data={
            'location_ref_id': self.store.store_identifier,
            'item_ref_ids': [str(p_id) for p_id in product_ids],
            'option_ref_ids': [],
            'action': 'enable' if status else 'disable'
        })
        if response.get('status') == 'success':
            self.pos_config._notify('PRODUCT_UP_STATUS_CHANGED', {
                'product_ids': product_ids,
                'status': status,
            })
        return response

    def post_hub_option_toggle(self, value_ids=[], status=False):
        """
        Enable/Disable option on urbanPiper store.
        Doc: https://api-docs.urbanpiper.com/downstream/api/endpoints/menu/menu-toggle

        NOTE: This endpoint is limited to 100 calls per minute, if you exceed this limit, you may
        receive a 429 Too Many Requests response.
        """
        values = self.env['product.template.attribute.value'].browse(value_ids).exists()
        if not values:
            return {}
        value_lst_str = [f'{value.product_tmpl_id.id}-{value.product_attribute_value_id.id}' for value in values]
        return self.make_request('/hub/api/v1/items/', 'POST', data={
            'location_ref_id': self.store.store_identifier,
            'item_ref_ids': [],
            'option_ref_ids': value_lst_str,
            'action': 'enable' if status else 'disable'
        })

    def post_order_status(self, order_id, new_status, prep_time, code=None):
        """
        Update order status in UrbanPiper.
        Doc: https://api-docs.urbanpiper.com/downstream/api/endpoints/order-management/order-status-update

        NOTE: This endpoint is limited to 100 calls per minute, if you exceed this limit, you may
        receive a 429 Too Many Requests response.
        """
        payload = {
            'new_status': new_status,
            'reason_code': code,
        }
        if new_status == 'Acknowledged':
            payload['extra'] = {
                'prep_time_mins': prep_time,
            }
        return self.make_request(f'/external/api/v1/orders/{order_id}/status/', 'PUT', data=payload)

    def post_order_reference_update(self, order):
        """
        Update order reference in UrbanPiper
        Doc: https://api-docs.urbanpiper.com/downstream/api/endpoints/order-management/order-relay

        NOTE: This endpoint is limited to 150 calls per minute, if you exceed this limit, you may
        receive a 429 Too Many Requests response.
        """
        return self.make_request(f'/external/api/v1/orders/{order.delivery_identifier}/', 'PUT', data={
            'reference_id': order.pos_reference
        })

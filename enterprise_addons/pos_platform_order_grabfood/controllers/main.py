# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
import pprint

from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError
from odoo.addons.pos_platform_order_grabfood.controllers import auth

_logger = logging.getLogger(__name__)


class GrabFoodController(http.Controller):
    _menu_webhook_url = '/grabfood/merchant/menu'
    _order_webhook_url = '/grabfood/orders'
    _order_state_webhook_url = '/grabfood/order/state'
    _menu_sync_webhook_url = '/grabfood'

    @auth.require_oauth
    @http.route(_menu_webhook_url, auth='public', type='http', readonly=True)
    def get_menu_webhook(self, **data):
        """
        Endpoint to handle GrabFood's webhook for food menu updates.
        This endpoint is called by GrabFood when the merchant's menu is updated.
        """
        store_sudo = request.env['platform.order.entity'].sudo()._find_store_from_data('grabfood', data)
        response_json = {
            **store_sudo._prepare_grabfood_menu_data(),
            'merchantID': store_sudo.external_id,
            'partnerMerchantID': data.get('partnerMerchantID'),
        }
        return request.make_json_response(response_json)

    @auth.require_oauth
    @http.route(_menu_sync_webhook_url, auth='public', type='http', methods=['POST'], csrf=False)
    def push_menu_sync_status(self):
        data = request.get_json_data()
        try:
            store_sudo = request.env['platform.order.entity'].sudo()._find_store_from_data('grabfood', data)
            store_sudo._grabfood_handle_menu_sync_notification(data)
        except ValidationError:
            return http.Response("Invalid data", status=400)

        return 'OK'

    @auth.require_oauth
    @http.route(_order_webhook_url, auth='public', type='http', methods=['POST'], csrf=False)
    def submit_orders_webhook(self):
        data = request.get_json_data()
        try:
            store_sudo = request.env['platform.order.entity'].sudo()._find_store_from_data('grabfood', data)
            if data.get('featureFlags', {}).get('isMexEditOrder'):
                store_sudo._grabfood_handle_edit_order_notification(data)
            else:
                store_sudo._create_order_from_data(data)

        except ValidationError:
            return http.Response("Invalid data", status=400)

        return 'OK'

    @auth.require_oauth
    @http.route(_order_state_webhook_url, auth='public', type='http', methods=['PUT'], csrf=False)
    def push_order_state_webhook(self):
        """
        Endpoint to handle GrabFood's webhook for order state updates.
        This endpoint is called by GrabFood when the order state changes.
        """
        data = request.get_json_data()
        try:
            order_sudo = request.env['pos.order'].sudo()._find_order_from_data('grabfood', data, raise_if_not_found=False)
            if order_sudo:
                order_sudo._update_order_status_from_data(data)

            # Reject the order directly if not found
            else:
                _logger.warning("GrabFood: Order not found for data:\n%s", pprint.pformat(data))

        except ValidationError:
            return http.Response("Invalid data", status=400)

        return request.make_json_response({'success': True}, status=200)

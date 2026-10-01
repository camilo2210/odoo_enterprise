# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from requests.exceptions import RequestException

from odoo import _, api, models
from odoo.exceptions import UserError

from odoo.addons.pos_platform_order_gofood.utils import const
from odoo.addons.pos_platform_order_gofood.utils.gofood_request import GoFoodClient

_logger = logging.getLogger(__name__)

PROVIDER_CODE = 'gofood'


class PosOrder(models.Model):
    _inherit = 'pos.order'

    # region NOTIFICATION HANDLING
    # override
    @api.model
    def _find_order_from_data(self, provider_code, notification_data, raise_if_not_found=True):
        if provider_code != PROVIDER_CODE:
            return super()._find_order_from_data(provider_code, notification_data, raise_if_not_found)

        order_id = notification_data['body']['order']['order_number']
        order = self.search([
            ('platform_order_ref', '=', order_id),
            ('platform_order_provider_code', '=', PROVIDER_CODE),
        ], limit=1)
        if not order and raise_if_not_found:
            raise UserError(_("GoFood: No order found matching order ID %s.", order_id))

        return order

    # override
    def _update_order_status_from_data(self, notification_data):
        self.ensure_one()
        if self.platform_order_provider_code != PROVIDER_CODE:
            return super()._update_order_status_from_data(notification_data)

        next_status = const.ORDER_STATUS_MAPPING.get(notification_data['body']['order']['status'])
        if not next_status:
            _logger.warning("GoFood: Unknown status %s", notification_data['body']['order']['status'])
            return None

        if next_status == self.platform_order_status:
            return None

        match next_status:
            case 'driver_allocated':
                self._set_driver_allocated({
                    'platform_order_rider_name': notification_data['body']['driver']['name'],
                })
            case 'driver_arrived':
                self._set_driver_arrived()
            case 'collected':
                self._set_collected()
            case 'delivered':
                self._set_delivered()
            case 'cancelled' | 'failed':
                cancel_reason = notification_data['body']['order'].get('cancellation_detail', {}).get('reason', '')
                self._set_cancelled(cancel_reason)
        return None
    # endregion

    # region HOOKS
    # override
    def _send_food_ready_request(self):
        self.ensure_one()
        if self.platform_order_provider_code != PROVIDER_CODE:
            return super()._send_food_ready_request()

        try:
            client = GoFoodClient(self.platform_order_store_id)
            client.set_food_ready(self.platform_order_ref)
        except RequestException as error:
            _logger.error("GoFood: Failed to mark food as ready: %s", error)
            raise UserError(_("GoFood: Failed to mark food as ready: %s", str(error))) from error

    # override
    def _send_accept_order_request(self):
        self.ensure_one()
        if self.platform_order_provider_code != PROVIDER_CODE:
            return super()._send_accept_order_request()

        try:
            client = GoFoodClient(self.platform_order_store_id)
            client.accept_order(self.platform_order_ref)
        except RequestException as error:
            _logger.error("GoFood: Failed to accept order: %s", error)
            raise UserError(_("GoFood: Failed to accept order: %s", str(error))) from error

    # override
    def _send_reject_order_request(self, reason):
        self.ensure_one()
        if self.platform_order_provider_code != PROVIDER_CODE:
            return super()._send_reject_order_request(reason)

        if self.platform_order_food_ready:
            raise UserError(_("GoFood: Cannot reject the order as the food is already marked as ready."))

        try:
            client = GoFoodClient(self.platform_order_store_id)
            client.reject_order(self.platform_order_ref, reason, _("Order rejected by merchant"))
        except RequestException as error:
            error_message = str(error)
            if error.response is not None:
                error_message = error.response.json()
            _logger.error("GoFood: Failed to reject order: %s", error_message)
            raise UserError(_("GoFood: Failed to reject order: %s", error_message)) from error
    # endregion

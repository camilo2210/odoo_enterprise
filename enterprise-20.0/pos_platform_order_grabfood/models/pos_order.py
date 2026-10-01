# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
from requests.exceptions import RequestException

from odoo import api, models
from odoo.exceptions import UserError, ValidationError
from odoo.addons.pos_platform_order_grabfood.utils import const
from odoo.addons.pos_platform_order_grabfood.utils.grabfood_request import GrabFoodClient

_logger = logging.getLogger(__name__)

PROVIDER_CODE = 'grabfood'


class PosOrder(models.Model):
    _inherit = 'pos.order'

    # region NOTIFICATION HANDLING
    # override
    @api.model
    def _find_order_from_data(self, provider_code, notification_data, raise_if_not_found=True):
        if provider_code != PROVIDER_CODE:
            return super()._find_order_from_data(provider_code, notification_data, raise_if_not_found)

        order_id = notification_data.get('orderID')
        if not order_id:
            raise ValidationError(self.env._("GrabFood: Received data with missing order ID."))

        order = self.search([
            ('platform_order_ref', '=', order_id),
            ('platform_order_provider_code', '=', PROVIDER_CODE),
        ], limit=1)
        if not order and raise_if_not_found:
            raise ValidationError(self.env._("GrabFood: No order found matching order ID %s.", order_id))

        return order

    # override
    def _update_order_status_from_data(self, notification_data):
        self.ensure_one()
        if self.platform_order_provider_code != PROVIDER_CODE:
            return super()._update_order_status_from_data(notification_data)

        new_status = const.ORDER_STATUS_MAPPING.get(notification_data['state'])
        if not new_status:
            _logger.warning(self.env._("GrabFood: Received unknown order status '%s'. Ignoring.", notification_data['state']))
            return None

        match new_status:
            case 'driver_allocated':
                self._set_driver_allocated()
            case 'driver_arrived':
                self._set_driver_arrived()
            case 'collected':
                self._set_collected()
            case 'delivered':
                self._set_delivered()
            case 'cancelled' | 'failed':
                self._set_cancelled()
        return None
    # endregion

    # region HOOKS
    # override
    def _send_food_ready_request(self):
        self.ensure_one()
        if self.platform_order_provider_code != PROVIDER_CODE:
            return super()._send_food_ready_request()

        try:
            client = GrabFoodClient(self.platform_order_store_id)
            client.set_food_ready(self.platform_order_ref, self.platform_order_type)
        except RequestException as error:
            raise UserError(self.env._("GrabFood: Failed to mark food as ready: %s", str(error)))

    # override
    def _send_accept_order_request(self):
        self.ensure_one()
        if self.platform_order_provider_code != PROVIDER_CODE:
            return super()._send_accept_order_request()

        try:
            client = GrabFoodClient(self.platform_order_store_id)
            client.update_order_state(self.platform_order_ref, "Accepted")
        except RequestException as error:
            raise UserError(self.env._("GrabFood: Failed to accept order: %s", str(error)))

    # override
    def _send_reject_order_request(self, reason):
        self.ensure_one()
        if self.platform_order_provider_code != PROVIDER_CODE:
            return super()._send_reject_order_request(reason)

        try:
            client = GrabFoodClient(self.platform_order_store_id)
            client.cancel_order(self.platform_order_ref, reason_code=int(reason))
        except RequestException as error:
            raise UserError(self.env._("GrabFood: Failed to reject order: %s", str(error)))
    # endregion

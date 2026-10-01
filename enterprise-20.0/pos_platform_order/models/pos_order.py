# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command


class PosOrder(models.Model):
    _inherit = 'pos.order'

    source = fields.Selection(selection_add=[('platform_order', 'Platform Order')], ondelete={'platform_order': 'set default'})

    # -- Provider and Store Information --
    platform_order_store_id = fields.Many2one('platform.order.entity', string='Store', readonly=True, copy=False, index='btree_not_null')
    platform_order_provider_id = fields.Many2one(related='platform_order_store_id.provider_id', store=True, copy=False, index='btree_not_null')
    platform_order_provider_code = fields.Selection(related='platform_order_provider_id.code', string='Provider Code', copy=False)

    # -- Platform Order Data --
    platform_order_ref = fields.Char(string='Online Order Reference', index=True, readonly=True, copy=False, help='Reference of the order in the food ordering platform.')
    platform_order_type = fields.Selection(
        [('delivery', 'Delivery'), ('pickup', 'Pickup'), ('dine_in', 'Dine In')],
        string='Order Type', readonly=True, copy=False)
    platform_order_status = fields.Selection([
        ('new', 'New'),
        ('accepted', 'Accepted'),
        ('driver_allocated', 'Driver Allocated'),
        ('driver_arrived', 'Driver Arrived'),
        ('collected', 'Collected'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('failed', 'Failed')], string='Order Status', readonly=True, copy=False)
    platform_order_pin = fields.Char('Order PIN', readonly=True, copy=False)
    platform_order_food_ready = fields.Boolean('Food Ready', readonly=True, copy=False)
    platform_order_rider_name = fields.Char('Rider Name', readonly=True, copy=False)
    platform_order_cancel_reason = fields.Char('Cancellation Reason', readonly=True, copy=False)
    platform_order_printed = fields.Boolean(string="Platform Order Printed", default=False)

    def _get_payment_method_values(self):
        self.ensure_one()
        return {
            'state': 'paid',
            'amount_paid': self.amount_total,
            'payment_ids': [Command.create({
                'payment_method_id': self.platform_order_store_id.payment_method_id.id,
                'amount': self.amount_total,
            })],
        }

    def _ensure_provider_is_not_disabled(self):
        """Checks if the provider is active before making an API call."""
        self.ensure_one()
        if self.platform_order_provider_id.state == 'disabled':
            raise UserError(_("The provider '%s' is disabled.", self.platform_order_provider_id.name))

    # region JS-CALLABLE METHODS (FOR POS INTERFACE)
    def platform_order_status_update_from_ui(self, status, **kwargs):
        self._ensure_provider_is_not_disabled()
        try:
            return self._order_status_update_handler(status, **kwargs)
        except UserError as e:
            return {'success': False, 'message': str(e)}

    def _order_status_update_handler(self, status, **kwargs):
        match status:
            case 'accept':
                return self._accept_order_handler(**kwargs)
            case 'food_ready':
                return self._food_ready_handler(**kwargs)
            case 'reject':
                return self._reject_order_handler(**kwargs)
            case _:
                raise UserError(self.env._("Unsupported status update action: %s", status))

    def _accept_order_handler(self):
        self._send_accept_order_request()
        self._set_accepted()
        return {'success': True, 'message': self.env._("Order has been accepted successfully.")}

    def _food_ready_handler(self):
        if self.platform_order_food_ready:
            raise UserError(self.env._("Food is already marked as ready for pickup or delivery."))
        self._send_food_ready_request()
        self.platform_order_food_ready = True
        self.message_post(body=self.env._("Food is now marked as ready for pickup or delivery."))
        return {'success': True, 'message': self.env._("Food marked as ready successfully.")}

    def _reject_order_handler(self, reason):
        if self.platform_order_status == 'driver_arrived':
            raise UserError(_("Cannot reject the order as the driver has already arrived."))
        try:
            self._send_reject_order_request(reason)
            self._set_cancelled(reason=reason)
            return {'success': True, 'message': self.env._("Order has been rejected successfully.")}
        except UserError as e:
            self._set_cancelled(reason=self.env._("Rejected by user with error: %s", str(e)))
            raise

    def mark_platform_prep_order_as_printed(self):
        self.ensure_one()
        if self.platform_order_printed:
            raise UserError(self.env._("This delivery order has already been printed automatically."))
        self.platform_order_printed = True
        return True
    # endregion

    # region NOTIFICATION HANDLING
    @api.model
    def _find_order_from_data(self, provider_code, notification_data, raise_if_not_found=True):
        """ Find the corresponding order based on notification data. """
        # This method is a placeholder for provider-specific logic.
        msg = "This method should be implemented in provider-specific subclasses."
        raise NotImplementedError(msg)

    def _update_order_status_from_data(self, notification_data):
        """ Process and apply updates from notification data to the order. """
        # This method is a placeholder for provider-specific logic.
        msg = "This method should be implemented in provider-specific subclasses."
        raise NotImplementedError(msg)
    # endregion

    # region ORDER STATE UPDATES
    def _set_accepted(self):
        self._update_state(('new',), 'accepted')

    def _set_driver_allocated(self, driver_values: dict | None = None):
        self._update_state(('accepted',), 'driver_allocated', extra_values=driver_values)

    def _set_driver_arrived(self):
        self._update_state(('driver_allocated',), 'driver_arrived')

    def _set_collected(self):
        # Collect payment in this stage
        self._update_state(('driver_allocated', 'driver_arrived'), 'collected', extra_values=self._get_payment_method_values())

    def _set_delivered(self):
        extra_values = {} if self.payment_ids else self._get_payment_method_values()
        self._update_state(
            ('accepted', 'driver_allocated', 'driver_arrived', 'collected'),
            'delivered',
            extra_values=extra_values,
        )

    def _set_cancelled(self, reason: str | None = None):
        allowed_states = ('new', 'accepted', 'driver_allocated', 'driver_arrived', 'collected')
        extra_values = {'state': 'cancel'}
        if reason:
            extra_values['platform_order_cancel_reason'] = reason
            self.sudo().message_post(body=self.env._("Order cancelled with reason: %s", reason))
        self._update_state(allowed_states, 'cancelled', extra_values=extra_values)

    def _update_state(self, allowed_states, target_state, extra_values=None):
        values_to_write = dict(extra_values or {})
        orders_to_process = self.filtered(lambda o: o.platform_order_status in allowed_states)

        if len(orders_to_process) != len(self):
            raise UserError(self.env._(
                "Cannot update state for orders that are not in the allowed states: %s.",
                ', '.join(allowed_states),
            ))

        values_to_write['platform_order_status'] = target_state
        orders_to_process.write(values_to_write)
        orders_to_process.sudo().message_post(body=self.env._("Platform status updated to %s.", target_state))
        orders_to_process.config_id.notify_platform_order_synchronisation(orders_to_process)
    # endregion

    # region HOOKS
    def _send_food_ready_request(self):
        """Hook for provider-specific implementation to notify 'food ready'."""
        raise NotImplementedError("Provider '%s' does not implement _send_food_ready_request." % self.platform_order_provider_id.name)

    def _send_accept_order_request(self):
        """Hook for provider-specific implementation to accept an order."""
        raise NotImplementedError("Provider '%s' does not implement _send_accept_order_request." % self.platform_order_provider_id.name)

    def _send_reject_order_request(self, reason):
        """Hook for provider-specific implementation to reject an order."""
        raise NotImplementedError("Provider '%s' does not implement _send_reject_order_request." % self.platform_order_provider_id.name)
    # endregion

    @api.model
    def _load_pos_preparation_data_fields(self):
        res = super()._load_pos_preparation_data_fields()
        return res + ['platform_order_ref']

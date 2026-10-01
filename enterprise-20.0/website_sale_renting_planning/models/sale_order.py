# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _is_cart_ready_for_checkout(self, **kwargs):
        """Override of `website_sale_renting` to block the cart when a planning-backed
        rental service has no free resource for the requested period, so the customer
        cannot reach payment for an unavailable booking."""
        ready = super()._is_cart_ready_for_checkout(**kwargs)
        if not self.is_rental_order:
            return ready
        if any(
            line._is_planning_rental_service()
            and line.product_id.planning_role_id.sync_shift_rental
            and len(line._get_planning_resources_available()) < int(line.product_uom_qty)
            for line in self.order_line
        ):
            self._add_blocking_alert(self.env._(
                "Some of your rental products cannot be rented during the selected period."
                " Please pick a different date or quantity."
            ))
            return False
        return ready

    def _verify_updated_quantity(self, order_line, product_id, new_qty, uom_id, **kwargs):
        new_qty, warning = super()._verify_updated_quantity(
            order_line, product_id, new_qty, uom_id, **kwargs
        )
        product = self.env['product.product'].browse(product_id)
        renting_availabilities = product._renting_product_availabilities(
            kwargs.get('start_date', order_line.start_date),
            kwargs.get('end_date', order_line.return_date)
        )
        max_qty = min(
            (a['quantity_available'] for a in renting_availabilities),
            default=float('inf')
        )
        if new_qty > max_qty:
            warning = self._get_rental_dates_error_base_message()
            return max_qty, warning

        return new_qty, warning

    def _get_rental_dates_error_message(self):
        """Override of `website_sale_renting` to check the product preparation times."""
        if error_msg := super()._get_rental_dates_error_message():
            return error_msg

        for order_line in self.order_line:
            renting_availabilities = order_line.product_id._renting_product_availabilities(
                self.rental_start_date or order_line.start_date,
                self.rental_return_date or order_line.return_date
            )
            max_qty = min(
                (a['quantity_available'] for a in renting_availabilities),
                default=float('inf')  # No renting availabilities means no constraint
            )
            if order_line.product_qty > max_qty:
                return self._get_rental_dates_error_base_message()
        return ""

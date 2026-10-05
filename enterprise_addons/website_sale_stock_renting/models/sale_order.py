# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta

from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _get_cart_qty(self, product_id, exclude_line=None):
        """Override to consider the max quantity of `product_id` simultaneously rented by this
        order during its rental period, instead of blindly summing all its rental lines
        regardless of whether they have already been returned.

        :param int product_id: `product.product` id
        :param exclude_line: an order line to exclude from the computation
        :return: product quantity in the product uom
        :rtype: float
        """
        product = self.env["product.product"].browse(product_id)
        if not product.rent_periodicity:
            return super()._get_cart_qty(product_id, exclude_line=exclude_line)

        common_lines = self._get_common_product_lines(product_id) - (
            exclude_line or self.env["sale.order.line"]
        )
        from_date = self.rental_start_date and (
            self.rental_start_date - timedelta(hours=product.preparation_time)
        )
        to_date = self.rental_return_date
        rented_qties, key_dates = common_lines._get_rented_quantities([from_date, to_date])
        current_cart_qty = max_cart_qty = 0.0
        for i in range(1, len(key_dates)):
            start_dt = key_dates[i - 1]
            if start_dt >= to_date:
                break
            current_cart_qty += rented_qties[start_dt]
            max_cart_qty = max(max_cart_qty, current_cart_qty)
        return max_cart_qty

    def _get_rental_dates_error_message(self):
        """Override of `website_sale_renting` to check the product preparation times."""
        if error_msg := super()._get_rental_dates_error_message():
            return error_msg

        rental_order_lines = self.order_line.filtered("is_rental")
        max_padding_time = max(rental_order_lines.product_id.mapped("preparation_time"), default=0)
        initial_time = self.rental_start_date - timedelta(hours=max_padding_time)

        # 15 minutes of allowed time between adding the product to cart and paying it.
        if initial_time < fields.Datetime.now() - timedelta(minutes=15):
            base_msg = self._get_rental_dates_error_base_message()
            return base_msg + self.env._(
                "\nYour rental product cannot be prepared on time, please rent later."
            )

        return ""

# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta

from odoo import models
from odoo.fields import Domain
from odoo.http import request


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _get_free_qty(self, *, warehouse_id=None, start_date=None, end_date=None, **kwargs):
        """Override of `website_sale_stock` to account for the rental period.

        :param int warehouse_id: ID of the warehouse to check availability in
        :param datetime start_date: The start of the rental period
        :param datetime end_date: The end of the rental period
        :param dict kwargs: Optional data
        :return: available quantity
        :rtype: float
        """
        if start_date and end_date and self.rent_periodicity and self.is_storable:
            start_date -= timedelta(hours=self.preparation_time)
            return min(
                (
                    avail["quantity_available"]
                    for avail in self._get_availabilities(start_date, end_date, warehouse_id)
                ),
                default=0,
            )
        return super()._get_free_qty(
            warehouse_id=warehouse_id, start_date=start_date, end_date=end_date, **kwargs
        )

    def _get_rented_quantities(self, from_date, to_date, domain=None):
        """Get the rented quantities for all the rental sale order line with product self.

        Note: self.ensure_one()

        :param datetime from_date: The first date where a rental sale order line is returned.
        :param datetime to_date: The last date where a rental sale order line reservation begins.
        :param domain: An additional restrictive domain to search sale order line for.
        """
        self.ensure_one()

        return (
            self
            .env["sale.order.line"]
            .search(
                Domain.AND([
                    domain or Domain.TRUE,
                    [
                        ("is_rental", "=", True),
                        ("product_id", "=", self.id),
                        ("state", "in", ["sent", "sale", "done"]),  # FIXME TLE: sent ?
                        ("return_date", ">", from_date),
                        "|",
                        ("reservation_begin", "<", to_date),
                        ("qty_delivered", ">", 0),
                    ],
                ]),
                order="reservation_begin asc",
            )
            ._get_rented_quantities([from_date, to_date])
        )

    def _get_availabilities(self, from_date, to_date, warehouse_id, with_cart=False):
        """Return a list of availabilities for a given period.

        The availabilities are structured in a dictionary of keys :
            - start: The date where the available_quantity becomes valid.
            - end: The date where the available_quantity becomes invalid.
            - available_quantity: The quantity of products available between the two dates.

        Early pickups and returns are taken into account.

        Note: self.ensure_one()

        :param datetime from_date: The date from which the availabilities should be computed
        :param datetime to_date: The date to which the availabilities should be computed
        :param int warehouse_id: The warehouse id
        """
        self.ensure_one()

        # This implementation is not perfect since qty_available is a poor float field which is,
        # in fact, equal to min(qty_available(t)) for t in [from_date, to_date]
        qty_available = self.with_context(
            from_date=from_date, to_date=to_date, warehouse_id=warehouse_id
        ).qty_available
        qty_available += self.with_context(warehouse_id=warehouse_id).qty_in_rent
        wh_domain = [("order_id.warehouse_id", "=", warehouse_id)] if warehouse_id else []
        rented_quantities, key_dates = self._get_rented_quantities(
            from_date, to_date, domain=wh_domain
        )
        cart = (with_cart and request and request.cart) or self.env["sale.order"]
        if cart:
            common_lines = cart._get_common_product_lines(self.id)
            so_rented_qties, so_key_dates = common_lines._get_rented_quantities([
                from_date,
                to_date,
            ])
            key_dates = list(set(so_key_dates + key_dates))
            key_dates.sort()
        current_qty_available = qty_available
        availabilities = []
        for i in range(1, len(key_dates)):
            start_dt = key_dates[i - 1]
            if start_dt > to_date:
                break
            # We consider here the worst case scenario, where qty_available is constant for the
            # whole period
            current_qty_available -= rented_quantities[start_dt]
            if cart:
                current_qty_available -= so_rented_qties[start_dt]
            if start_dt >= from_date:
                availabilities.append({
                    "start": start_dt,
                    "end": key_dates[i],
                    "quantity_available": current_qty_available,
                })

        return availabilities

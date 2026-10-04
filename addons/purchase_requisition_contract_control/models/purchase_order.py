# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import format_date, formatLang

# Purchase order states in which the order is (being) confirmed.
CONFIRMATION_STATES = ('to approve', 'purchase')


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    # ------------------------------------------------------------
    # ONCHANGE METHODS (user feedback)
    # ------------------------------------------------------------

    @api.onchange('requisition_id')
    def _onchange_requisition_id(self):
        """Keep the native agreement defaults, but do not import blanket order lines.

        The native implementation (``purchase_requisition``) copies every agreement
        line into the order. For blanket orders the user only adds the products that
        are actually needed; the agreement price is still applied natively by
        ``purchase.order.line._compute_price_unit_and_date_planned_and_name``.
        Purchase templates keep their native behaviour, as importing their lines is
        their very purpose.
        """
        if self.requisition_id.requisition_type != 'blanket_order':
            return super()._onchange_requisition_id()
        current_lines = self.order_line
        result = super()._onchange_requisition_id()
        # Drop the lines added by the native onchange, keep the ones the user entered.
        self.order_line = current_lines
        return result

    @api.onchange('requisition_id')
    def _onchange_requisition_id_check_expiration(self):
        if self.requisition_id and self._is_requisition_expired():
            return {
                'warning': {
                    'title': self.env._("Expired Agreement"),
                    'message': self._get_requisition_expired_message(),
                },
            }

    @api.onchange('order_line', 'requisition_id')
    def _onchange_order_line_check_requisition_quantities(self):
        if self.state == 'cancel' or self.requisition_id.requisition_type != 'blanket_order':
            return
        excesses = self._get_requisition_quantity_excesses()
        if excesses:
            return {
                'warning': {
                    'title': self.env._("Agreement Quantity Exceeded"),
                    'message': self._get_requisition_quantity_excess_message(excesses),
                },
            }

    # ------------------------------------------------------------
    # CONSTRAINTS (data integrity)
    # ------------------------------------------------------------

    @api.constrains('requisition_id')
    def _check_requisition_on_link(self):
        """An order cannot be created with, or linked to, an expired or exceeded agreement."""
        orders = self.filtered(lambda order: order.requisition_id and order.state != 'cancel')
        orders._check_requisition_not_expired()
        orders._check_requisition_quantities()

    @api.constrains('state')
    def _check_requisition_on_confirmation(self):
        """Re-validate at confirmation, whatever the entry point (button_confirm,
        button_approve, direct write...): the agreement may have expired, or other
        orders may have consumed its quantities since the order was saved."""
        orders = self.filtered(
            lambda order: order.requisition_id and order.state in CONFIRMATION_STATES
        )
        orders._check_requisition_not_expired()
        orders._check_requisition_quantities()

    # ------------------------------------------------------------
    # BUSINESS METHODS
    # ------------------------------------------------------------

    def _is_requisition_expired(self):
        """An agreement is expired once its end date (last valid day) is in the past."""
        self.ensure_one()
        date_end = self.requisition_id.date_end
        return bool(date_end) and date_end < fields.Date.context_today(self)

    def _get_requisition_expired_message(self):
        self.ensure_one()
        return self.env._(
            "The purchase agreement %(agreement)s expired on %(date)s. "
            "A purchase order cannot be created or confirmed under an expired agreement.\n"
            "Select a valid agreement, or extend the end date of this agreement.",
            agreement=self.requisition_id.display_name,
            date=format_date(self.env, self.requisition_id.date_end),
        )

    def _check_requisition_not_expired(self):
        expired_orders = self.filtered(lambda order: order._is_requisition_expired())
        if expired_orders:
            # dict.fromkeys: one message per agreement, order preserved.
            messages = dict.fromkeys(
                order._get_requisition_expired_message() for order in expired_orders
            )
            raise ValidationError("\n\n".join(messages))

    def _check_requisition_quantities(self):
        messages = []
        for order in self:
            if order.state == 'cancel' or order.requisition_id.requisition_type != 'blanket_order':
                continue
            excesses = order._get_requisition_quantity_excesses()
            if excesses:
                messages.append(order._get_requisition_quantity_excess_message(excesses))
        if messages:
            raise ValidationError("\n\n".join(messages))

    def _get_requisition_quantity_excesses(self):
        """Return the blanket order products whose quantity on this order exceeds the
        quantity still available on the agreement.

        All quantities are expressed in the product unit of measure. The available
        quantity is the agreement quantity minus the quantity ordered through other
        confirmed purchase orders of the same agreement, which is the native definition
        of "Ordered" on agreement lines. Products that are not part of the agreement
        are not restricted, as in standard Odoo.

        :return: list of dicts with keys ``product``, ``requested`` and ``available``
        """
        self.ensure_one()
        requisition = self.requisition_id
        if requisition.requisition_type != 'blanket_order':
            return []

        agreement_products = requisition.line_ids.product_id
        requested = defaultdict(float)
        for line in self.order_line:
            if not line.display_type and line.product_id and line.product_id in agreement_products:
                # product_uom_qty: native stored quantity converted to the product UoM.
                requested[line.product_id.id] += line.product_uom_qty
        if not requested:
            return []

        allowed = defaultdict(float)
        for requisition_line in requisition.line_ids:
            product = requisition_line.product_id
            if product.id in requested:
                allowed[product.id] += requisition_line.product_uom_id._compute_quantity(
                    requisition_line.product_qty, product.uom_id, round=False,
                )

        products = self.env['product.product'].browse(list(requested))
        consumed = self._get_requisition_consumed_quantities(products)

        excesses = []
        for product in products:
            available = max(allowed[product.id] - consumed.get(product.id, 0.0), 0.0)
            if product.uom_id.compare(requested[product.id], available) > 0:
                excesses.append({
                    'product': product,
                    'requested': requested[product.id],
                    'available': available,
                })
        return excesses

    def _get_requisition_consumed_quantities(self, products):
        """Quantities (product UoM) of ``products`` ordered through the *other* confirmed
        purchase orders of this order's agreement, computed with a single SQL query.

        The native non-stored ``purchase.requisition.line.qty_ordered`` is not reused on
        purpose: it includes the order being validated, it is not invalidated when a
        confirmed order line quantity changes, and its handling of duplicated agreement
        products depends on the computation batch.

        :return: dict {product_id: quantity}
        """
        self.ensure_one()
        # sudo: integrity must account for every confirmed order of the agreement,
        # regardless of the current user's record rules. Only aggregates are read.
        groups = self.env['purchase.order.line'].sudo()._read_group(
            domain=[
                ('order_id.requisition_id', '=', self.requisition_id.id),
                ('order_id.state', '=', 'purchase'),
                ('order_id', 'not in', self._origin.ids),
                ('product_id', 'in', products.ids),
                ('display_type', '=', False),
            ],
            groupby=['product_id'],
            aggregates=['product_uom_qty:sum'],
        )
        return {product.id: quantity for product, quantity in groups}

    def _get_requisition_quantity_excess_message(self, excesses):
        self.ensure_one()
        details = "\n".join(
            self.env._(
                "- %(product)s: requested %(requested)s %(uom)s, available %(available)s %(uom)s",
                product=excess['product'].display_name,
                requested=formatLang(self.env, excess['requested'], dp='Product Unit'),
                available=formatLang(self.env, excess['available'], dp='Product Unit'),
                uom=excess['product'].uom_id.name,
            )
            for excess in excesses
        )
        return self.env._(
            "The requested quantities exceed the remaining quantities of the purchase "
            "agreement %(agreement)s:\n%(details)s\n"
            "The available quantity already deducts the quantities ordered through other "
            "confirmed purchase orders of this agreement. Reduce the quantities to continue.",
            agreement=self.requisition_id.display_name,
            details=details,
        )

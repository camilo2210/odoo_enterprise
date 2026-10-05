# Part of Odoo. See LICENSE file for full copyright and licensing details.

import ast

from odoo import api, fields, models
from odoo.fields import Domain


class ProductProduct(models.Model):
    _inherit = "product.product"

    qty_in_rent = fields.Float("Quantity currently in rent", compute="_compute_qty_in_rent")

    @api.depends("rent_periodicity")
    @api.depends_context("show_rental_tag")
    def _compute_display_name(self):
        super()._compute_display_name()
        if not self.env.context.get("show_rental_tag"):
            return
        for product in self:
            if product.rent_periodicity:
                product.display_name = product.env._("%s (Rental)", product.display_name)

    def _compute_qty_in_rent(self):
        # Note: we don't use the product `qty_available` field
        # because there are no stock moves for services (which can be rented).
        active_rental_lines = self.env["sale.order.line"]._read_group(
            domain=self._get_qty_in_rent_domain(),
            groupby=["product_id"],
            aggregates=["qty_delivered:sum", "qty_returned:sum"],
        )
        res = {
            product.id: qty_delivered - qty_returned
            for product, qty_delivered, qty_returned in active_rental_lines
        }
        for product in self:
            product.qty_in_rent = res.get(product.id, 0)

    def _get_qty_in_rent_domain(self):
        return [("is_rental", "=", True), ("product_id", "in", self.ids), ("state", "=", "sale")]

    def action_view_rentals(self):
        """Access Schedule view of rental order lines, filtered on the current variants."""
        action = self.env["ir.actions.actions"]._for_xml_id(
            "sale_renting.action_rental_order_schedule"
        )
        domain = Domain(ast.literal_eval(action.get("domain", "True")))
        context: dict = ast.literal_eval(action.get("context", "{}"))

        domain &= Domain("product_id", "in", self.ids)
        if first_product := self[:1]:
            context["default_product_id"] = first_product.id

        action.update(domain=domain, context=context)
        return action

    def _get_number_of_periods(self, start_date, end_date):
        return self.product_tmpl_id._get_number_of_periods(start_date, end_date)

    def _has_multiple_uoms(self):
        # multi-uoms doesn't work with rental (for now)
        if self.rent_periodicity:
            return False
        return super()._has_multiple_uoms()

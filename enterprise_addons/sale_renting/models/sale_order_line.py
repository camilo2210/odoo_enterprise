# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain
from odoo.tools import format_amount
from odoo.tools.sql import SQL


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    product_id = fields.Many2one(group_expand="_read_group_expand_product_id")

    order_is_rental = fields.Boolean(related="order_id.is_rental_order")

    # Stored because a product could have been rentable when added to the SO but then updated
    is_rental = fields.Boolean(compute="_compute_is_rental", precompute=True, store=True)
    is_product_rentable = fields.Boolean(compute="_compute_is_product_rentable")

    qty_returned = fields.Float("Returned", default=0.0, copy=False)
    start_date = fields.Datetime(related="order_id.rental_start_date", readonly=False)
    return_date = fields.Datetime(related="order_id.rental_return_date", readonly=False)
    reservation_begin = fields.Datetime(
        string="Pickup date - padding time",
        compute="_compute_reservation_begin",
        store=True,
        init_storage=lambda _model: None,
    )

    # Technical computed fields for UX purposes (hide/make fields readonly, ...)
    is_late = fields.Boolean(related="order_id.is_late")
    team_id = fields.Many2one(related="order_id.team_id")
    country_id = fields.Many2one(related="order_id.partner_id.country_id")
    rental_status = fields.Selection(
        selection=[("pickup", "Booked"), ("return", "Picked-Up"), ("returned", "Returned")],
        compute="_compute_rental_status",
        search="_search_rental_status",
    )
    rental_color = fields.Integer(compute="_compute_rental_color")

    @api.depends("order_partner_id.name", "order_id.name", "product_id.name")
    @api.depends_context("sale_renting_short_display_name")
    def _compute_display_name(self):
        if not self.env.context.get("sale_renting_short_display_name"):
            return super()._compute_display_name()
        for sol in self:
            descriptions = []
            group_by = self.env.context.get("group_by", [])

            if "partner_id" not in group_by:
                descriptions.append(sol.order_partner_id.display_name)
            if "product_id" not in group_by:
                descriptions.append(sol.product_id.name)
            descriptions.append(sol.order_id.name)

            sol.display_name = ", ".join(descriptions)

    @api.depends("order_is_rental", "product_id")
    def _compute_is_rental(self):
        for line in self:
            line.is_rental = line.order_is_rental and line.is_product_rentable

    @api.depends("product_id")
    def _compute_is_product_rentable(self):
        for line in self:
            line.is_product_rentable = bool(line.product_id.rent_periodicity)

    @api.depends("order_id.rental_start_date")
    def _compute_reservation_begin(self):
        lines = self.filtered("is_rental")
        for line in lines:
            line.reservation_begin = line.order_id.rental_start_date
        (self - lines).reservation_begin = None

    @api.depends("is_rental")
    def _compute_qty_delivered_method(self):
        """Allow modification of delivered qty without depending on stock moves."""
        rental_lines = self.filtered("is_rental")
        super(SaleOrderLine, self - rental_lines)._compute_qty_delivered_method()
        rental_lines.qty_delivered_method = "manual"

    @api.depends("is_rental")
    def _compute_product_updatable(self):
        rental_lines = self.filtered("is_rental")
        super(SaleOrderLine, self - rental_lines)._compute_product_updatable()
        rental_lines.product_updatable = True

    @api.depends("product_uom_qty", "qty_delivered", "qty_returned")
    def _compute_rental_status(self):
        self.rental_status = False
        for sol in self.filtered("order_is_rental"):
            if sol.qty_delivered < sol.product_uom_qty:
                sol.rental_status = "pickup"
            elif sol.qty_returned >= sol.qty_delivered and sol.qty_delivered >= sol.product_uom_qty:
                sol.rental_status = "returned"
            else:
                sol.rental_status = "return"

    @api.depends("order_is_rental", "state", "rental_status", "is_late")
    def _compute_rental_color(self):
        self.rental_color = 0
        for sol in self.filtered("order_is_rental"):
            if sol.state in ("draft", "sent"):
                sol.rental_color = 5  # purple
                continue
            match sol.rental_status:
                case "pickup":
                    sol.rental_color = 3 if sol.is_late else 4  # yellow if late else blue
                case "return":
                    sol.rental_color = 6 if sol.is_late else 2  # red if late else orange
                case "returned":
                    sol.rental_color = 7  # green

    def _search_rental_status(self, operator, values):
        if operator != "in":
            return NotImplemented

        # Uses custom SQL to compare fields between each other.
        return (Domain("order_is_rental", "=", False) if False in values else Domain.FALSE) | (
            Domain([("order_is_rental", "=", True)])
            & Domain.custom(
                to_sql=lambda table: SQL(
                    """
                    CASE
                        WHEN %(qty_delivered)s < %(product_uom_qty)s THEN 'pickup'
                        WHEN (
                            %(qty_returned)s >= %(qty_delivered)s
                            AND %(qty_delivered)s >= %(product_uom_qty)s
                        ) THEN 'returned'
                        ELSE 'return'
                    END IN %(values)s
                    """,
                    product_uom_qty=table.product_uom_qty,
                    qty_delivered=table.qty_delivered,
                    qty_returned=table.qty_returned,
                    values=tuple(values),
                )
            )
        )

    def _read_group_expand_product_id(self, products, domain):  # noqa: ARG002
        if not self.env.context.get("in_rental_schedule"):
            return self.env["product.product"]

        expanded_products = self.env["product.product"].search(
            Domain([
                ("id", "not in", products.ids),
                ("sale_ok", "=", True),
                ("rent_periodicity", "!=", False),
                ("type", "!=", "combo"),
            ]),
            limit=80 - len(products),
        )
        # While `_web_read_group_expand` already includes `products` in the expanded set, it
        # exhibits an unusual behavior of adding the expanded groups first, even though they are
        # empty groups. Performing the union here reverses this behavior.
        return products + expanded_products

    def web_gantt_write(self, vals):
        """Update the sale order line with the provided values and performs necessary validations.

        This method also recalculates rental prices if the duration of the rental changes.

        :param dict vals: Dictionary of values to update on the sale order line.
        :raises UserError: If the order is already picked up and the start date is being updated.
        :raises UserError: If the order is already returned and the end date is being updated.
        :raises UserError: If the write operation fails.
        :return: A dictionary containing notifications and/or actions, if applicable. Format: {
            'notifications': list[{'type': str, 'message': str, 'code': str}],
            'actions': list[dict]  # Action dictionaries
        }
        :rtype: dict
        """
        self.ensure_one()
        result = {"notifications": [], "actions": []}

        if self.order_id.rental_status in ("return", "returned") and "start_date" in vals:
            raise UserError(self.env._("The order is already picked-up."))
        if self.order_id.rental_status == "returned" and "return_date" in vals:
            raise UserError(self.env._("The order is already returned."))

        updating_duration = "start_date" in vals or "return_date" in vals
        old_duration = self.return_date - self.start_date if updating_duration else None

        if not self.write(vals):
            raise UserError(self.env._("An error occurred. Please try again."))

        if updating_duration:
            new_duration = self.return_date - self.start_date
            if old_duration != new_duration:
                self.order_id.order_line.filtered("is_rental")._compute_name()
                self.order_id._recompute_rental_prices()
                result["notifications"].append({
                    "type": "success",
                    "message": self.env._("The rental prices have been updated."),
                    "code": "rental_price_update",
                })

        return result

    def _get_sale_order_line_multiline_description_sale(self):
        """Add Rental information to the SaleOrderLine name."""
        res = super()._get_sale_order_line_multiline_description_sale()
        if self.is_rental:
            self.order_id._ensure_rental_dates()
            duration = self._get_rental_duration_description()
            separator = "\n" if res else ""
            res += f"{separator}{duration}"
            # Invalidate the recordset to ensure that the label field is
            # recomputed with the new description, because if name field is computed twice in a
            # transaction the second computation will not be triggered if the field is already
            # computed once.
            self.invalidate_recordset(["label"])

        return res

    def _get_rental_duration_description(self):
        start_date = self.order_id.rental_start_date
        return_date = self.order_id.rental_return_date
        periods = self.product_template_id._get_number_of_periods(start_date, return_date)
        periodicity = self.product_template_id._get_rent_periodicity_label(periods)
        return f"{periods} {periodicity}"

    def _get_rental_pricing_description(self):
        self.ensure_one()

        order = self.order_id
        duration = self.product_id._get_number_of_periods(
            order.rental_start_date, order.rental_return_date
        )
        price = self.currency_id.round(self._get_displayed_unit_price() / duration)

        return self.env._(
            "%(amount)s / %(duration_unit)s",
            amount=format_amount(self.env, amount=price, currency=self.currency_id),
            duration_unit=self.product_template_id._get_rent_periodicity_label(),
        )

    def _get_pricelist_price(self):
        """Override to compute the price from the pricelist instead of the cached pricelist rule, as
        rental product can depend on multiple rules."""
        if self.is_rental:
            return self.order_id.pricelist_id._get_product_price(
                self.product_id.with_context(**self._get_product_price_context()),
                **self._get_pricelist_kwargs(),
            )
        return super()._get_pricelist_price()

    def _get_pricelist_kwargs(self):
        res = super()._get_pricelist_kwargs()
        if self.is_rental:
            res.update({"start_date": self.start_date, "end_date": self.return_date})
        return res

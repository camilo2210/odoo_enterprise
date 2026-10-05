# Part of Odoo. See LICENSE file for full copyright and licensing details.

from math import ceil

from odoo import Command, api, fields, models
from odoo.fields import Domain
from odoo.tools import float_compare
from odoo.tools.date_utils import to_timezone

RENTAL_STATUS = [
    ("draft", "Quotation"),
    ("sent", "Quotation Sent"),
    ("pickup", "Reserved"),
    ("return", "Pickedup"),
    ("returned", "Returned"),
    ("cancel", "Cancelled"),
]


class SaleOrder(models.Model):
    _inherit = "sale.order"

    _rental_period_coherence = models.Constraint(
        "CHECK(rental_start_date < rental_return_date)",
        "The rental start date must be before the rental return date if any.",
    )

    @api.model
    def default_get(self, fields):
        """Override to map relevant default `sale.order.line` fields to `sale.order` fields.

        Mainly used to create a new rental order from the rental schedule view, as it works on
        `sale.order.line` records.

        :param Sequence[str] fields: Fields without values.
        :return: A dictionary mapping the default field values.
        :rtype: dict[str, Any]
        """
        defaults = super().default_get(fields)
        self = self.browse()  # noqa: PLW0642

        if self.env.context.get("convert_default_order_line_values"):
            missing_fields = set(fields) - defaults.keys()

            SO_TO_SOL_FIELDS_MAPPING = [
                ("partner_id", "order_partner_id"),
                ("rental_start_date", "start_date"),
                ("rental_return_date", "return_date"),
            ]
            for so_fname, sol_fname in SO_TO_SOL_FIELDS_MAPPING:
                if so_fname in missing_fields and (
                    default_value := self.env.context.get(f"default_{sol_fname}")
                ):
                    defaults[so_fname] = default_value

            if "order_line" in missing_fields:
                defaults["order_line"] = [Command.create(self._build_default_order_line_values())]

            # Convert added default values to the right format (see also `BaseModel.default_get`)
            for fname in defaults.keys() & missing_fields:
                field = self._fields[fname]
                value = field.convert_to_cache(defaults[fname], self, validate=False)
                defaults[fname] = field.convert_to_write(value, self)

        return defaults

    def _build_default_order_line_values(self):
        """Generate default values for `sale.order.line` based on context keys prefixed with
        'default_'."""
        # Extract field names from context keys that start with 'default_'
        default_field_names = (
            key.replace("default_", "", 1)  # Remove the 'default_' prefix
            for key in self.env.context
            if key.startswith("default_")
        )
        # Filter field names to include only those that exist in `sale.order.line` fields
        sol_field_names = (
            field_name
            for field_name in default_field_names
            if field_name in self.env["sale.order.line"]._fields
        )

        return {
            "product_uom_qty": 1.0,
            **{
                field_name: self.env.context[f"default_{field_name}"]
                for field_name in sol_field_names
            },
        }

    # === FIELDS ===#

    rental_start_date = fields.Datetime(string="Rental Start Date", tracking=True)
    rental_return_date = fields.Datetime(string="Rental Return Date", tracking=True)
    is_rental_order = fields.Boolean(
        string="Rental Order", compute="_compute_is_rental_order", search="_search_is_rental_order"
    )
    has_rentable_lines = fields.Boolean(compute="_compute_has_rentable_lines")

    duration_days = fields.Integer(
        string="Duration in days",
        compute="_compute_duration",
        help="The duration in days of the rental period.",
    )
    remaining_hours = fields.Integer(
        string="Remaining duration in hours",
        compute="_compute_duration",
        help="The leftover hours of the rental period.",
    )

    rental_status = fields.Selection(
        selection=RENTAL_STATUS,
        string="Rental Status",
        compute="_compute_rental_status",
        store=True,
        init_storage=lambda model: None,
    )
    # rental_status = next action to do basically, but shown string is action done.
    next_action_date = fields.Datetime(
        string="Next Action",
        compute="_compute_rental_status",
        store=True,
        init_storage=lambda model: None,
    )

    has_pickable_lines = fields.Boolean(compute="_compute_has_action_lines")
    has_returnable_lines = fields.Boolean(compute="_compute_has_action_lines")

    is_late = fields.Boolean(
        string="Is overdue",
        help="The products haven't been picked-up or returned in time."
        " This excludes any grace period before late fees apply.",
        compute="_compute_is_late",
        search="_search_is_late",
    )

    # === COMPUTE METHODS === #

    @api.depends("rental_start_date")
    def _compute_delivery_date(self):
        """Override to use the rental start date as the delivery date for rental orders."""
        super()._compute_delivery_date()
        for order in self:
            if order.is_rental_order:
                order.delivery_date = order.rental_start_date

    @api.depends("rental_start_date", "rental_return_date")
    def _compute_is_rental_order(self):
        for order in self:
            order.is_rental_order = order.rental_start_date and order.rental_return_date

    @api.depends("order_line.is_product_rentable")
    def _compute_has_rentable_lines(self):
        for order in self:
            order.has_rentable_lines = any(line.is_product_rentable for line in order.order_line)

    @api.depends("rental_start_date", "rental_return_date")
    def _compute_duration(self):
        self.duration_days = 0
        self.remaining_hours = 0
        for order in self:
            if order.rental_start_date and order.rental_return_date:
                duration = order.rental_return_date - order.rental_start_date
                order.duration_days = duration.days
                order.remaining_hours = ceil(duration.seconds / 3600)

    @api.depends(
        "rental_start_date",
        "rental_return_date",
        "state",
        "order_line.is_rental",
        "order_line.product_uom_qty",
        "order_line.qty_delivered",
        "order_line.qty_returned",
    )
    def _compute_rental_status(self):
        self.next_action_date = False
        for order in self:
            if not order.is_rental_order:
                order.rental_status = False
            elif order.state != "sale":
                order.rental_status = order.state
            # As soon as an item is picked, the order status turns to "Pickedup"
            elif order.has_returnable_lines:
                order.rental_status = "return"
                order.next_action_date = order.rental_return_date
            elif order.has_pickable_lines:
                order.rental_status = "pickup"
                order.next_action_date = order.rental_start_date
            else:
                order.rental_status = "returned"

    @api.depends(
        "is_rental_order",
        "state",
        "order_line.is_rental",
        "order_line.product_uom_qty",
        "order_line.qty_delivered",
        "order_line.qty_returned",
    )
    def _compute_has_action_lines(self):
        self.has_pickable_lines = False
        self.has_returnable_lines = False
        for order in self:
            if order.state == "sale" and order.is_rental_order:
                rental_order_lines = order.order_line.filtered(
                    lambda line: line.is_rental and line.product_type != "combo"
                )
                order.has_pickable_lines = any(
                    sol.qty_delivered < sol.product_uom_qty for sol in rental_order_lines
                )
                order.has_returnable_lines = any(
                    sol.qty_returned < sol.qty_delivered for sol in rental_order_lines
                )

    @api.depends("is_rental_order", "next_action_date", "rental_status")
    def _compute_is_late(self):
        now = fields.Datetime.now()
        for order in self:
            order.is_late = (
                order.is_rental_order
                and order.rental_status in ["pickup", "return"]
                and order.next_action_date
                and order.next_action_date < now
            )

    @api.depends("is_rental_order")
    def _compute_show_ship_button(self):
        rental_orders = self.filtered("is_rental_order")
        rental_orders.show_ship_button = False
        super(SaleOrder, self - rental_orders)._compute_show_ship_button()

    # === SEARCH METHODS === #

    def _search_is_rental_order(self, operator, value):
        if True not in value:
            return NotImplemented

        domain = Domain([("rental_start_date", "!=", False), ("rental_return_date", "!=", False)])
        return ~domain if operator == "not in" else domain

    def _search_is_late(self, operator, value):
        if operator != "in" and True not in value:
            return NotImplemented

        return Domain([
            ("is_rental_order", "=", True),
            ("rental_status", "in", ("pickup", "return")),
            ("next_action_date", "!=", False),
            ("next_action_date", "<", "now"),
        ])

    # === ONCHANGE METHODS ===#

    def onchange(self, values, field_names, fields_spec):
        """Override to forward values from the form to the `_onchange_*` methods.

        When creating a new order, `self._origin` doesn't exist yet. It is therefore impossible to
        know what the original record held until it is saved. This override works around that by
        capturing the temporary record values from the form directly.
        """
        if self._origin:
            return super().onchange(values, field_names, fields_spec)
        return super(
            SaleOrder, self.with_context(origin_is_rental_order=values.get("is_rental_order"))
        ).onchange(values, field_names, fields_spec)

    @api.onchange("rental_start_date", "rental_return_date")
    def _onchange_rental_dates(self):
        if bool(self.rental_start_date) ^ bool(self.rental_return_date):
            # Wait until both dates are set (or both cleared) before proceeding.
            return

        # Recompute the rental descriptions to include the new duration
        rentable_lines = self.order_line.filtered("is_product_rentable")
        self.env.add_to_compute(rentable_lines._fields["name"], rentable_lines)

        if self.is_rental_order:
            self._recompute_rental_prices()

    @api.onchange("has_rentable_lines")
    def _onchange_has_rentable_lines(self):
        if self.has_rentable_lines and not self.is_rental_order:
            self._ensure_rental_dates()
            # Recompute rental prices because they were initially computed before rental dates were
            # set.
            self._recompute_rental_prices()

    # === ACTION METHODS ===#

    def _recompute_rental_prices(self):
        self.with_context(rental_recompute_price=True)._recompute_prices()

    def _get_update_prices_lines(self):
        """Exclude non-rental lines from price recomputation."""
        lines = super()._get_update_prices_lines()
        if not self.env.context.get("rental_recompute_price"):
            return lines
        return lines.filtered("is_rental")

    # PICKUP / RETURN : rental.processing wizard

    def action_open_pickup(self):
        self.ensure_one()
        precision = self.env["decimal.precision"].precision_get("Product Unit")
        lines_to_pickup = self.order_line.filtered(
            lambda r: (
                r.is_rental
                and r.product_type != "combo"
                and float_compare(r.product_uom_qty, r.qty_delivered, precision_digits=precision)
                > 0
            )
        )
        return self._open_rental_wizard("pickup", lines_to_pickup.ids)

    def action_open_return(self):
        self.ensure_one()
        precision = self.env["decimal.precision"].precision_get("Product Unit")
        lines_to_return = self.order_line.filtered(
            lambda r: (
                r.is_rental
                and r.product_type != "combo"
                and float_compare(r.qty_delivered, r.qty_returned, precision_digits=precision) > 0
            )
        )
        return self._open_rental_wizard("return", lines_to_return.ids)

    def _open_rental_wizard(self, status, order_line_ids):
        context = {
            "order_line_ids": order_line_ids,
            "default_status": status,
            "default_order_id": self.id,
        }
        return {
            "name": self.env._("Validate a pickup")
            if status == "pickup"
            else self.env._("Validate a return"),
            "view_mode": "form",
            "res_model": "rental.order.wizard",
            "type": "ir.actions.act_window",
            "target": "new",
            "context": context,
        }

    def _get_portal_return_action(self):
        """Return the action used to display orders when returning from customer portal."""
        if self.is_rental_order:
            return self.env.ref("sale_renting.rental_order_action")
        return super()._get_portal_return_action()

    # === TOOLING ===#

    def _ensure_rental_dates(self):
        self.ensure_one()
        if self.rental_start_date and self.rental_return_date:
            return

        start_date, return_date = self._get_first_rentable_template()._get_default_rental_dates(
            tzinfo=self._get_tzinfo()
        )
        self.update({"rental_start_date": start_date, "rental_return_date": return_date})

    def _get_first_rentable_template(self):
        return next(
            (line.product_template_id for line in self.order_line if line.is_product_rentable),
            self.env["product.template"],
        )

    def _to_order_tz(self, dt):
        """Localize the given datetime in the order timezone.

        This method is useful when comparing or changing the date part, as it may depend on the
        timezone.
        """
        to_order_tz = to_timezone(self._get_tzinfo())
        return to_order_tz(dt)

    def _get_tzinfo(self):
        """Get the order timezone.

        The order timezone depends on the current salesman, (or the website when installed).
        """
        self.ensure_one()
        return self.env.tz

    # === BUSINESS METHODS ===#

    def _get_product_catalog_order_data(self, products, **kwargs):
        """Override to add the rental dates for the price computation."""
        return super()._get_product_catalog_order_data(
            products, start_date=self.rental_start_date, end_date=self.rental_return_date, **kwargs
        )

    def _update_order_line_info(self, product, *args, **kwargs):
        """Override to add the context to mark the line as rental and the rental dates for the
        price computation."""
        if product.rent_periodicity and not self.has_rentable_lines:
            self._ensure_rental_dates()
        return super()._update_order_line_info(
            product,
            *args,
            start_date=self.rental_start_date,
            end_date=self.rental_return_date,
            **kwargs,
        )

    def _get_action_add_from_catalog_extra_context(self):
        """Override to add rental dates in the context for product availabilities."""
        extra_context = super()._get_action_add_from_catalog_extra_context()
        extra_context.update(start_date=self.rental_start_date, end_date=self.rental_return_date)
        return extra_context

    @api.model
    def retrieve_rental_dashboard(self):
        """Retrieve counts for the rental dashboard.

        :return: A dictionary containing counts for each dashboard card.
        :rtype: dict
        """
        base = Domain("is_rental_order", "=", True)
        return {
            "today": self.search_count(
                Domain("next_action_date", ">=", "today")
                & Domain("next_action_date", "<", "today +1d")
            ),
            "pickups": self.search_count(Domain("rental_status", "=", "pickup")),
            "returns": self.search_count(Domain("rental_status", "=", "return")),
            "late": self.search_count(
                Domain("rental_status", "in", ["pickup", "return"])
                & Domain("next_action_date", "<", "+1H")
            ),
            "to_confirm": self.search_count(Domain("rental_status", "in", ["draft", "sent"])),
            "to_invoice": self.search_count(base & Domain("invoice_status", "=", "to invoice")),
        }

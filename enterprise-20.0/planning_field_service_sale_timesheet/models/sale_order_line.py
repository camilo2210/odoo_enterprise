from odoo import api, fields, models
from odoo.tools import float_compare, float_is_zero


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    planning_slot_id = fields.Many2one('planning.slot', 'Intervention')
    delivered_price_subtotal = fields.Monetary(
        compute='_compute_delivered_amount',
        string='Delivered Subtotal',
        export_string_translation=False,
    )
    delivered_price_tax = fields.Float(
        compute='_compute_delivered_amount',
        string='Delivered Total Tax',
        export_string_translation=False,
    )
    delivered_price_total = fields.Monetary(
        compute='_compute_delivered_amount',
        string='Delivered Total',
        export_string_translation=False,
    )

    @api.depends('qty_delivered', 'discount', 'price_unit', 'tax_ids')
    def _compute_delivered_amount(self):
        """
        Compute the amounts of the SO line for delivered quantity.
        """
        for line in self:
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            taxes = line.tax_ids.compute_all(price, line.order_id.currency_id, line.qty_delivered, product=line.product_id, partner=line.order_id.partner_shipping_id)
            line.delivered_price_tax = sum(t.get('amount', 0.0) for t in taxes.get('taxes', []))
            line.delivered_price_total = taxes['total_included']
            line.delivered_price_subtotal = taxes['total_excluded']

    def _compute_invoice_status(self):
        sol_from_intervention_without_amount = self.filtered(
            lambda sol:
                sol.planning_slot_id
                and float_is_zero(sol.price_unit, precision_rounding=sol.currency_id.rounding)
                and sol.invoice_status not in ('invoiced', 'upselling')
        )
        sol_from_intervention_with_anglo = sol_from_intervention_without_amount.filtered(
            lambda sol: sol.company_id.anglo_saxon_accounting
        )
        precision = self.env['decimal.precision'].precision_get('Product Unit')
        sol_from_task_with_anglo_invoiced = sol_from_intervention_with_anglo.filtered(
            lambda sol: float_compare(sol.qty_invoiced, sol.product_uom_qty, precision_digits=precision) >= 0
        )
        sol_from_task_with_anglo_invoiced.invoice_status = 'invoiced'
        (sol_from_intervention_with_anglo - sol_from_task_with_anglo_invoiced).invoice_status = 'to invoice'
        (sol_from_intervention_without_amount - sol_from_intervention_with_anglo).invoice_status = 'no'
        super(SaleOrderLine, self - sol_from_intervention_without_amount)._compute_invoice_status()

    @api.depends('price_unit')
    def _compute_qty_to_invoice(self):
        sol_from_intervention_without_amount = self.filtered(
            lambda sol:
                sol.planning_slot_id
                and float_is_zero(sol.price_unit, precision_rounding=sol.currency_id.rounding)
        )
        sol_from_intervention_with_anglo = sol_from_intervention_without_amount.filtered(
            lambda sol: sol.company_id.anglo_saxon_accounting
        )
        sol_from_task_without_anglo = sol_from_intervention_without_amount - sol_from_intervention_with_anglo
        sol_from_task_without_anglo.qty_to_invoice = 0.0
        super(SaleOrderLine, self - sol_from_task_without_anglo)._compute_qty_to_invoice()

    def _planning_slot_values(self):
        slot_vals = super()._planning_slot_values()
        slot_vals['partner_id'] = self.order_id.partner_shipping_id.id if self.env.user.has_group('account.group_delivery_invoice_address') else self.order_partner_id.id
        return slot_vals

    def _consider_in_catalog(self, *args, **kwargs) -> bool:
        """Override of `sale` to restrict the lines considered in the catalog when it's opened
        through the smart button of a "field service".
        """
        res = super()._consider_in_catalog(*args, **kwargs)

        if intervention_id := self.env.context.get("intervention_id"):
            return res and intervention_id == self.planning_slot_id.id

        return res

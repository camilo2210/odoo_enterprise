from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    lot_ids = fields.Many2many('stock.lot', string='Equipment Maintained',
        domain="[('partner_ids', 'in', order_partner_id)]",
        compute='_compute_lot_ids', store=True, readonly=False,
        copy=False, groups='stock.group_stock_user')

    allow_lot_update = fields.Boolean(compute='_compute_allow_lot_update', export_string_translation=False)

    @api.depends('product_id.type', 'product_id.recurring_invoice')
    def _compute_allow_lot_update(self):
        for line in self:
            is_service = line.product_id.type == 'service'
            is_subscription = line.product_id.recurring_invoice
            line.allow_lot_update = is_service and is_subscription

    @api.depends('product_id.type', 'product_id.recurring_invoice')
    def _compute_lot_ids(self):
        contract_lines = self.filtered('allow_lot_update')
        (self - contract_lines).lot_ids = False
        contracts_per_order = contract_lines.grouped('order_id')

        for order, contract_lines in contracts_per_order.items():
            delivered_lots = order.order_line.move_ids.move_line_ids.filtered(
                lambda ml: ml.state == 'done' and ml.location_dest_id.usage == 'customer'
            ).lot_id
            if not delivered_lots:
                continue
            for line in contract_lines:
                if line.lot_ids:
                    continue
                line.lot_ids = delivered_lots

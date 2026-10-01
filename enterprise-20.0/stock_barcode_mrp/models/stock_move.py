from odoo import api, models
from odoo.tools.float_utils import float_compare


class StockMove(models.Model):
    _inherit = 'stock.move'

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        for move, vals in zip(moves, vals_list):
            if not vals.get('uom_id') and move.bom_line_id:
                move.uom_id = move.bom_line_id.uom_id
        return moves

    def _get_fields_stock_barcode(self):
        return super()._get_fields_stock_barcode() + ['uom_id', 'bom_line_id']

    def split_uncompleted_moves(self):
        production_moves = self.filtered(lambda m: m.picking_type_id.code == 'mrp_operation')
        new_move_line_vals = []
        for move in production_moves:
            rounding = self.env['decimal.precision'].precision_get('Product Unit')
            if (
                float_compare(move.quantity, 0, precision_digits=rounding) > 0
                and float_compare(move.quantity, move.product_uom_qty, precision_digits=rounding) < 0
                and move.picked and move.state != "done"
            ):
                qty_split = move.uom_id._compute_quantity(move.product_uom_qty - move.quantity, move.product_id.uom_id, rounding_method='HALF-UP')
                move_line_vals = move._prepare_move_line_vals(quantity=qty_split)
                move_line_vals['picked'] = False
                new_move_line_vals.append(move_line_vals)
        if new_move_line_vals:
            self.env['stock.move.line'].create(new_move_line_vals)
        return super(StockMove, self - production_moves).split_uncompleted_moves()

    def _should_bypass_set_qty_producing(self):
        if self.env.context.get('barcode_view') or self.env.context.get('barcode_trigger'):
            picking_type = self.raw_material_production_id.picking_type_id
            if picking_type.restrict_scan_product or (
                picking_type.restrict_scan_tracking_number and self.product_id.tracking in ('lot', 'serial')
            ):
                return True
        return super()._should_bypass_set_qty_producing()

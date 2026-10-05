from odoo import api, Command, models


class StockMove(models.Model):
    _inherit = 'stock.move'

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        if not self.env.context.get('skip_intercompany_sync'):
            for move in res:
                if not move.company_id.intercompany_sync_delivery_receipt:
                    continue
                if move.purchase_line_id:
                    corresponding_moves = move.sudo().purchase_line_id.auto_sale_order_line_id.move_ids
                    if corresponding_moves:
                        move.sudo().write({'move_orig_ids': [Command.link(m.id) for m in corresponding_moves]})
                if move.sale_line_id:
                    corresponding_moves = move.sudo().sale_line_id.auto_purchase_order_line_id.move_ids
                    if corresponding_moves:
                        move.sudo().write({'move_dest_ids': [Command.link(m.id) for m in corresponding_moves]})
        return res

    def _prepare_move_line_vals(self, quantity=None, reserved_quant=None):
        vals = super()._prepare_move_line_vals(quantity=quantity, reserved_quant=reserved_quant)
        if self.move_orig_ids and self.move_orig_ids.company_id != self.company_id and reserved_quant:
            vals['lot_name'] = reserved_quant.lot_id.name
        return vals

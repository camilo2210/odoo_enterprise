# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _get_linked_intercompany_pickings(self):
        self.ensure_one()
        dest_moves = self.move_ids.move_dest_ids
        if dest_pickings := dest_moves.sudo().picking_id.filtered(lambda p: p.company_id != self.company_id):
            return dest_pickings
        origin_moves = self.move_ids.move_orig_ids
        if origin_pickings := origin_moves.sudo().picking_id.filtered(lambda p: p.company_id != self.company_id):
            return origin_pickings
        return self.env['stock.picking']

    def action_cancel(self):
        for picking in self:
            linked_pickings = picking._get_linked_intercompany_pickings()
            for linked_picking in linked_pickings:
                values = {
                    'partner_id': linked_picking.user_id.partner_id,
                    'picking': picking,
                }
                linked_picking.message_post_with_source(
                    'sale_purchase_stock_inter_company_rules.cancelled_interco_transfer',
                    render_values=values,
                    partner_ids=linked_picking.user_id.partner_id.ids,
                )

        return super().action_cancel()

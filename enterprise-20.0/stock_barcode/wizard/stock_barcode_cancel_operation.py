# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class Stock_BarcodeCancelOperation(models.TransientModel):
    _name = 'stock_barcode.cancel.operation'
    _description = 'Cancel Operation'

    picking_id = fields.Many2one('stock.picking', 'Transfer', readonly=True)
    picking_name = fields.Char('Transfer Name', readonly=True, related='picking_id.display_name')
    batch_id = fields.Many2one('stock.picking.batch', 'Batch Transfer', readonly=True)
    batch_name = fields.Char('Batch Transfer Name', readonly=True, related='batch_id.name')

    def action_cancel_operation(self):
        record_to_cancel = self.picking_id
        if self.env.user.has_group('stock.group_stock_picking_batch') and self.batch_id:
            record_to_cancel = self.batch_id
        res = record_to_cancel.action_cancel()
        return {'type': 'ir.actions.act_window_close', 'infos': {'cancelled': res}}

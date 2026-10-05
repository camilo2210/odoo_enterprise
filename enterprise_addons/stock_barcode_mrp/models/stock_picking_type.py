from odoo import fields, models
from odoo.fields import Domain


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    count_mo_confirmed = fields.Integer(compute='_compute_count_mo_confirmed')

    def _compute_count_mo_confirmed(self):
        for pick_type in self:
            pick_type.count_mo_confirmed = self.env['mrp.production'].search_count([
                ('state', 'in', ['confirmed', 'progress']),
                ('picking_type_id', 'in', pick_type.ids),
                ('reservation_state', '=', 'assigned'),
            ])

    def _compute_show_barcode_validation(self):
        other_operation_types = self.env['stock.picking.type']
        for picking_type in self:
            if picking_type.code == 'mrp_operation':
                picking_type.show_barcode_validation = not picking_type.restrict_scan_product
            else:
                other_operation_types |= picking_type
        super(StockPickingType, other_operation_types)._compute_show_barcode_validation()

    def _compute_is_barcode_picking_type(self):
        for picking_type in self:
            if picking_type.code == 'mrp_operation':
                picking_type.is_barcode_picking_type = True
            else:
                super(StockPickingType, picking_type)._compute_is_barcode_picking_type()

    def get_action_picking_tree_ready_kanban(self):
        if self.code == 'mrp_operation':
            res = self._get_action('stock_barcode_mrp.mrp_action_kanban')
            res['domain'] = Domain.AND([
                res['domain'],
                [('picking_type_id.active', '=', True)],
            ])
            return res
        return super().get_action_picking_tree_ready_kanban()

    def _get_barcode_config(self):
        config = super()._get_barcode_config()
        return config

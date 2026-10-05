# -*- coding: utf-8 -*-

from odoo import api, fields, models


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    pick_type_create_components_lots = fields.Boolean(related='picking_type_id.use_create_components_lots')

    @api.depends('move_id', 'production_id')
    def _compute_parent_location_id(self):
        lines_not_in_production = self.env['stock.move.line']
        for line in self:
            # if component
            if line.production_id:
                if self.env.context.get('newByProduct', False):
                    # For byproducts
                    line.parent_location_id = line.production_id.production_location_id
                    line.parent_location_dest_id = line.production_id.location_src_id
                else:
                    line.parent_location_id = line.production_id.location_src_id
                    line.parent_location_dest_id = line.production_id.production_location_id
            # if final product
            elif line.move_id.production_id:
                line.parent_location_id = line.move_id.production_id.production_location_id
                line.parent_location_dest_id = line.move_id.production_id.location_dest_id
            else:
                lines_not_in_production |= line
        super(StockMoveLine, lines_not_in_production)._compute_parent_location_id()

    @api.model_create_multi
    def create(self, vals_list):
        move_line_ids = super().create(vals_list)
        for ml in move_line_ids:
            if not ml.move_id and ml.production_id:
                # Try to find a move this move line belongs to
                if self.env.context.get('newByProduct'):
                    mrp_o2m_field = 'move_byproduct_ids'
                else:
                    mrp_o2m_field = 'move_raw_ids'
                candidate_moves = ml.production_id[mrp_o2m_field]
                move = candidate_moves.filtered(lambda m: m.product_id == ml.product_id)
                if not move:
                    # To avoid setting production_id when creating stock move we clear it from the context
                    move = self.env['stock.move'].with_context(default_production_id=None).create(ml._prepare_stock_move_vals())
                ml.move_id = move[0].id
        return move_line_ids

    def _compute_qty_done(self):
        # Show quantity only when qty_producing > 0 or when explicitly picked but not for
        # uncompletd splitted move_lines (i.e. line is not picked but move is picked)
        raw_lines = self.filtered(lambda l: l.production_id and not l.move_id.production_id)
        for line in raw_lines:
            if line.picked or (line.production_id.qty_producing and not line.move_id.picked):
                line.qty_done = line.quantity
            else:
                line.qty_done = 0
        super(StockMoveLine, self - raw_lines)._compute_qty_done()

    def _inverse_qty_done(self):
        # Only mark lines as picked when they are directky edited from the form not just
        # by having qty_done
        raw_lines = self.filtered(lambda l: l.production_id and not l.move_id.production_id)
        for line in raw_lines.with_context({'preserve_state': True}):
            qty_done = line.qty_done
            line.quantity = qty_done
            if qty_done and self.env.context.get('mark_picked'):
                line.picked = True
        super(StockMoveLine, self - raw_lines)._inverse_qty_done()

    def _prepare_stock_move_vals(self):
        move_vals = super()._prepare_stock_move_vals()
        if not self.production_id:
            return move_vals
        move_vals.update({
            'location_id': self.location_id.id,
            'location_dest_id': self.location_dest_id.id,
            'state': 'assigned',
            'picking_type_id': self.production_id.picking_type_id.id,
            'company_id': self.production_id.company_id.id
        })
        if self.env.context.get('newByProduct'):
            move_vals['production_id'] = self.production_id.id
        else:
            move_vals['raw_material_production_id'] = self.production_id.id
        return move_vals

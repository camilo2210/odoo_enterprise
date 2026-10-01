# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    fsm_lot_id = fields.Many2one('stock.lot', domain="[('product_id', '=', product_id)]")

    def _prepare_procurement_values(self):
        values = super()._prepare_procurement_values()
        triggered_from_fsm_product_view = self.env.context.get('field_service_stock_set_quantity')
        triggered_from_fsm_stock_tracking_wizard = self.env.context.get('field_service_stock_tracking') and self.fsm_lot_id
        if self.planning_slot_id and (triggered_from_fsm_product_view or triggered_from_fsm_stock_tracking_wizard):
            values['warehouse_id'] = self.env.user._get_default_warehouse_id()
        return values

    def _action_launch_stock_rule(self, **kwargs):
        result = super()._action_launch_stock_rule(**kwargs)
        ml_to_create = []
        for sol_to_treat in self:
            if not (sol_to_treat.planning_slot_id and sol_to_treat.product_id.type == 'consu'):
                continue
            for move in sol_to_treat.move_ids:
                if move.state in ('done', 'cancel'):
                    continue
                if move.product_uom_qty:
                    if not move.move_line_ids:
                        ml_vals = move._prepare_move_line_vals(quantity=0)
                        ml_vals['quantity'] = move.product_uom_qty
                        ml_vals['lot_id'] = sol_to_treat.fsm_lot_id.id
                        ml_to_create.append(ml_vals)
                    else:
                        qty_done_in_move_lines = sum(ml.quantity for ml in move.move_line_ids)
                        qty_done_diff = move.product_uom_qty - qty_done_in_move_lines
                        if qty_done_diff == 0:
                            continue
                        if qty_done_diff > 0:  # qty was added to the sale_line
                            move_line = move.move_line_ids[-1]
                            if not move_line.lot_id:
                                move_line.lot_id = sol_to_treat.fsm_lot_id
                            if move_line.lot_id == sol_to_treat.fsm_lot_id:
                                move_line.quantity += qty_done_diff
                        else:  # qty was removed from the sale_line
                            for move_line in move.move_line_ids:
                                if not move_line.lot_id:
                                    move_line.lot_id = sol_to_treat.fsm_lot_id
                                if move_line.quantity > 0 and move_line.lot_id == sol_to_treat.fsm_lot_id:
                                    new_line_qty = max(0, move_line.quantity + qty_done_diff)
                                    qty_done_diff += move_line.quantity - new_line_qty
                                    move_line.quantity = new_line_qty
                                    if not move_line.lot_id:
                                        move_line.lot_id = sol_to_treat.fsm_lot_id
                                    if qty_done_diff == 0:
                                        break
                else:
                    move.move_line_ids.unlink()
        if ml_to_create:
            self.env['stock.move.line'].create(ml_to_create)
        return result

    def _get_product_catalog_lines_data(self, parent_record, **kwargs) -> dict:
        res = super()._get_product_catalog_lines_data(parent_record, **kwargs)

        # TODO once the props is made optional, should only be sent if intervention_id in context
        res['minimumQuantityOnProduct'] = res['quantity'] - self.product_id.quantity_decreasable_sum

        if (
            self.env.context.get('intervention_id', False)
            and len(self) != 1
            and self.order_id
            and self.product_id.tracking
        ):
            # Here we remove the readonly fixed by sale on product present on many sale order lines.
            res['readOnly'] = self.order_id._is_readonly()

        return res

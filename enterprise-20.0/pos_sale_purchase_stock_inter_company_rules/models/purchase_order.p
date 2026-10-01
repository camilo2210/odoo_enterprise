from odoo import Command, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def _set_pcavs_from_order(self, so_lines_vals):
        super()._set_pcavs_from_order(so_lines_vals)
        po_lines = self.order_line
        if not po_lines:
            return
        linked_move = self.env['stock.move'].browse(po_lines[0].move_ids._rollup_move_dests())
        if (pos_order := linked_move.reference_ids.pos_order_ids):
            seen_pos_lines_ids = set()
            for sol in so_lines_vals:
                pos_line = pos_order.lines.filtered(
                    lambda line: line.id not in seen_pos_lines_ids
                    and line.product_id.id == sol[2]["product_id"]
                    and line.custom_attribute_value_ids
                )[:1]
                sol[2]["product_custom_attribute_value_ids"] = [
                    Command.create({
                        "custom_product_template_attribute_value_id": pcav.custom_product_template_attribute_value_id.id,
                        "custom_value": pcav.custom_value,
                    })
                    for pcav in pos_line.custom_attribute_value_ids
                ]
                seen_pos_lines_ids.add(pos_line.id)

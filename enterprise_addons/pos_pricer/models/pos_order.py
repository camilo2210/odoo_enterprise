from odoo import models


class PosOrder(models.Model):
    _inherit = "pos.order"

    def _process_saved_order(self, draft):
        order = super()._process_saved_order(draft=draft)

        products = self.lines.filtered(
            lambda l: (
                l.product_id.type == "consu" and not l.product_id.uom_id.is_zero(l.qty)
            )
        ).product_id
        products.sudo().write({"needs_pricer_update": True})
        return order

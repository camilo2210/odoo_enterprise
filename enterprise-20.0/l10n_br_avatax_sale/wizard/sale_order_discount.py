from odoo import models, Command


class SaleOrderDiscount(models.TransientModel):
    _inherit = "sale.order.discount"

    def _create_discount_lines(self):
        # Clean up taxes to avoid previous calculations to affect when setting a global discount
        if self.sale_order_id.l10n_br_is_avatax:
            self.sale_order_id.order_line.write({
                'extra_tax_data': {},
                'tax_ids': [Command.clear()],
            })
        return super()._create_discount_lines()

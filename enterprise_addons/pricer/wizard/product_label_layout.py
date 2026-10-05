from odoo import fields, models


class ProductLabelLayout(models.TransientModel):
    _inherit = "product.label.layout"

    print_format = fields.Selection(
        selection_add=[
            ("pricer_tags", "Pricer Tags"),
        ],
        ondelete={"pricer_tags": "set default"},
    )

    pricer_tags_pricelist_id = fields.Many2one(
        "product.pricelist",
        domain=[
            "|",
            "|",
            ("item_ids.compute_price", "=", "fixed"),
            ("item_ids.is_plain_discount", "=", True),
            ("item_ids.base", "in", ["list_price", "standard_price"]),
        ],
    )

    def process(self):
        if self.print_format != "pricer_tags":
            return super().process()

        for product in self.product_ids:
            product.pricer_tags_pricelist_id = self.pricer_tags_pricelist_id

        pricer_stores = self.product_ids.mapped("pricer_store_id")
        notification = pricer_stores.action_button_update_pricer_tags()
        notification["params"]["next"] = {"type": "ir.actions.act_window_close"}
        return notification

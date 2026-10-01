from odoo import models


class PricerProductSupplierInfo(models.Model):
    _inherit = "product.supplierinfo"

    def write(self, vals):
        res = super().write(vals)

        # If we change the supplier product reference, update Pricer tags
        if "product_code" in vals:
            self.mapped("product_id").filtered_domain(
                [
                    ("pricer_tag_ids", "!=", False),
                    ("pricer_store_id", "!=", False),
                ]
            ).sudo().write({"needs_pricer_update": True})

        return res

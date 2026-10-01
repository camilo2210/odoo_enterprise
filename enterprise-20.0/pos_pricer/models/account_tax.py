from odoo import models


class AccountTax(models.Model):
    _inherit = "account.tax"

    def write(self, vals):
        res = super().write(vals)

        # If we change the taxes name, update Pricer tags with the new name
        if "name" in vals:
            self.env["product.product"].sudo().search(
                [
                    ("taxes_id", "in", self.ids),
                    ("pricer_tag_ids", "!=", False),
                    ("pricer_store_id", "!=", False),
                ]
            ).write({"needs_pricer_update": True})
        return res

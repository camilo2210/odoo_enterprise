# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _planning_slot_values(self):
        slot_vals = super()._planning_slot_values()
        slot_vals['worksheet_template_id'] = self.product_id.worksheet_template_id.id
        return slot_vals

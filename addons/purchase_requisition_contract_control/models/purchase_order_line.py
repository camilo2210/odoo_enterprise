# -*- coding: utf-8 -*-
from odoo import api, models


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    @api.constrains('product_id', 'product_qty', 'product_uom_id')
    def _check_requisition_quantities(self):
        """Enforce the blanket order remaining quantities whenever a line changes, including
        lines created or written directly (import, RPC, procurement) without touching the order."""
        self.order_id._check_requisition_quantities()

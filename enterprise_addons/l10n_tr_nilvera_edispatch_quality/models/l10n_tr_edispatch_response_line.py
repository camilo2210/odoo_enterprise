from odoo import api, fields, models


class L10n_TrEdispatchResponseLine(models.Model):
    _name = 'l10n_tr.edispatch.response.line'
    _inherit = ['l10n_tr.edispatch.count.mixin']
    _description = "Türkiye e-Dispatch Response Line"
    _check_company_auto = True

    check_id = fields.Many2one(
        comodel_name='quality.check',
        string="Quality Check",
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(related='check_id.company_id', store=True, index=True)
    move_id = fields.Many2one(
        comodel_name='stock.move',
        string="Stock Move",
        check_company=True,
        required=True,
        ondelete='cascade',
        index=True,
    )
    product_id = fields.Many2one(related='move_id.product_id')
    product_uom_qty = fields.Float(compute='_compute_product_uom_qty', store=True)
    uom_id = fields.Many2one(related='move_id.uom_id')

    @api.depends('move_id.product_uom_qty')
    def _compute_product_uom_qty(self):
        for line in self:
            # An answered count keeps the demand it was answered against, whatever the order says later.
            if line.check_id.quality_state == 'none':
                line.product_uom_qty = line.move_id.product_uom_qty

    def _l10n_tr_get_quantity_payload(self, quantity):
        self.ensure_one()
        return {'UnitCode': self.uom_id._get_unece_code(), 'Value': quantity}

    def _l10n_tr_get_unit_price(self):
        """Return the price the goods were bought at, or None when the receipt answers no purchase."""
        self.ensure_one()
        if 'purchase_line_id' not in self.move_id._fields or not self.move_id.purchase_line_id:
            return None
        return self.move_id.purchase_line_id.price_unit

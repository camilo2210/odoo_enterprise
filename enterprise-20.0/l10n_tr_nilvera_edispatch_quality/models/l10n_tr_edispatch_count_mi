from odoo import api, fields, models
from odoo.exceptions import ValidationError


class L10n_TrEdispatchCountMixin(models.AbstractModel):
    _name = 'l10n_tr.edispatch.count.mixin'
    _description = "Türkiye e-Dispatch Counted Quantities"

    product_id = fields.Many2one(comodel_name='product.product', string="Product")
    product_uom_qty = fields.Float(string="Demand", digits='Product Unit')
    uom_id = fields.Many2one(comodel_name='uom.uom', string="Unit of Measure")
    received_qty = fields.Float(string="Received", digits='Product Unit')
    rejected_qty = fields.Float(string="Rejected Amount", digits='Product Unit')
    accepted_qty = fields.Float(
        string="Accepted Amount",
        digits='Product Unit',
        compute='_compute_accepted_qty',
    )
    missing_qty = fields.Float(
        string="Missing Amount",
        digits='Product Unit',
        compute='_compute_missing_excess_qty',
        store=True,
        readonly=False,
    )
    excess_qty = fields.Float(
        string="Excess Amount",
        digits='Product Unit',
        compute='_compute_missing_excess_qty',
        store=True,
        readonly=False,
    )
    rejection_reason = fields.Text(string="Rejection Reason")

    @api.depends('received_qty', 'rejected_qty', 'excess_qty')
    def _compute_accepted_qty(self):
        for line in self:
            line.accepted_qty = line.received_qty - line.rejected_qty - line.excess_qty

    @api.depends('received_qty', 'product_uom_qty')
    def _compute_missing_excess_qty(self):
        for line in self:
            line.missing_qty = max(0, line.product_uom_qty - line.received_qty)
            line.excess_qty = max(0, line.received_qty - line.product_uom_qty)

    @api.constrains('received_qty', 'rejected_qty', 'excess_qty')
    def _check_rejected_qty(self):
        for line in self:
            if line.uom_id.compare(line.rejected_qty + line.excess_qty, line.received_qty) > 0:
                raise ValidationError(self.env._(
                    "%(product)s cannot have more rejected and excess goods than what was received.",
                    product=line.product_id.display_name,
                ))

    @api.constrains('rejected_qty', 'rejection_reason')
    def _check_rejection_reason(self):
        for line in self:
            if not line.uom_id.is_zero(line.rejected_qty) and not line.rejection_reason:
                raise ValidationError(self.env._("A rejection reason is required for %(product)s.", product=line.product_id.display_name))

    def _l10n_tr_get_counted_values(self):
        """Return the counted quantities, to carry them between a count and the answer it feeds."""
        self.ensure_one()
        return {
            'received_qty': self.received_qty,
            'rejected_qty': self.rejected_qty,
            'missing_qty': self.missing_qty,
            'excess_qty': self.excess_qty,
            'rejection_reason': self.rejection_reason,
        }

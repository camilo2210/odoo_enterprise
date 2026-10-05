from odoo import fields, models


class L10n_TrEdispatchCountLine(models.TransientModel):
    _name = 'l10n_tr.edispatch.count.line'
    _inherit = ['l10n_tr.edispatch.count.mixin']
    _description = "Türkiye e-Dispatch Count to Answer With"

    wizard_id = fields.Many2one(
        comodel_name='quality.check.wizard',
        string="Quality Check Wizard",
        required=True,
        ondelete='cascade',
    )
    response_line_id = fields.Many2one(
        comodel_name='l10n_tr.edispatch.response.line',
        string="Response Line",
        required=True,
        ondelete='cascade',
    )
    product_id = fields.Many2one(related='response_line_id.product_id')
    product_uom_qty = fields.Float(related='response_line_id.product_uom_qty')
    uom_id = fields.Many2one(related='response_line_id.uom_id')

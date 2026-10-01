# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models, api


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    resource_ids = fields.Many2many('resource.resource', string="Resources", help="The planning resources linked to this payment method. If there are several, the user will be able to choose on the POS which one to use when validating an order with this payment method.")
    type = fields.Selection(
        selection_add=[('resource', 'Resource')],
        ondelete={"resource": "cascade"},
    )

    @api.model
    def _load_pos_data_fields(self, config):
        res = super()._load_pos_data_fields(config)
        res += ['resource_ids']
        return res

    def write(self, vals):
        if vals.get('type') == 'resource':
            vals['receivable_account_id'] = False
            vals['outstanding_account_id'] = False
            vals['journal_id'] = False
            vals['payment_provider'] = False
            vals['qr_code_method'] = False
            vals['payment_method_type'] = 'none'
        return super().write(vals)

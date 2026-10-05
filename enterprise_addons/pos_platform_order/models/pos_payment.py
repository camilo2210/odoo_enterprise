# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, models


class PosPayment(models.Model):
    _inherit = 'pos.payment'

    @api.constrains('payment_method_id')
    def _check_payment_method_id(self):
        platform_order_payments = self.filtered(lambda p: p.pos_order_id.platform_order_store_id)
        super(PosPayment, self - platform_order_payments)._check_payment_method_id()

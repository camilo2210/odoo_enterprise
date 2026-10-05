# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class PosPayment(models.Model):
    _inherit = 'pos.payment'

    @api.constrains('payment_method_id')
    def _check_payment_method_id(self):
        """
        A delivery payment method is only applicable to delivery orders, not to regular orders. So Bypass those payment method.
        """
        bypass_check_payments = self.filtered('payment_method_id.delivery_provider_id')
        super(PosPayment, self - bypass_check_payments)._check_payment_method_id()

from odoo import api, models


class AccountPaymentMethod(models.Model):
    _inherit = 'account.payment.method'

    @api.model
    def _get_mandate_type_per_code(self):
        """ Map a payment method code to the ``mandate_type`` it collects with.
        Example: {'sdd': 'sepa', 'cpa005': 'cpa005_pad', 'payment_method_code': 'mandate_type_key'}.
        """
        return {}

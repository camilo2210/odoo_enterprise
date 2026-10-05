# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class AccountPaymentMethod(models.Model):
    _inherit = 'account.payment.method'

    @api.model
    def _get_payment_method_information(self):
        res = super()._get_payment_method_information()
        res['sdd'] = {'mode': 'multi', 'type': ('bank',)}
        return res

    @api.model
    def _get_sdd_payment_method_code(self):
        res = super()._get_sdd_payment_method_code()
        res.append('sdd')
        return res

    @api.model
    def _get_mandate_type_per_code(self):
        res = super()._get_mandate_type_per_code()
        res['sdd'] = 'sepa'
        return res

    def _get_sdd_alerts(self, currency):
        self.ensure_one()
        if self.code in ('sdd', 'sepa_direct_debit') and currency.name != 'EUR':
            return {
                'sepa_wrong_currency': {
                    'message': self.env._("SEPA Scheme operates in Euro."),
                    'level': 'warning',
                },
            }
        return {}

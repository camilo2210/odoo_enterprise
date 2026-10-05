from odoo import api, models


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    @api.depends('payment_method_code', 'currency_id')
    def _compute_actionable_errors(self):
        super()._compute_actionable_errors()
        for wizard in self.filtered(lambda w: w.payment_method_code in ('sdd', 'sepa_direct_debit')):
            wizard.actionable_errors = {
                **(wizard.actionable_errors or {}),
                **wizard.payment_method_line_id.payment_method_id._get_sdd_alerts(wizard.currency_id),
            }

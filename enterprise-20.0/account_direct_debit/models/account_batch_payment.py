from odoo import models


class AccountBatchPayment(models.Model):
    _inherit = 'account.batch.payment'

    def check_payments_for_errors(self):
        rslt = []
        # Also closes the mandates that have expired since their payment was posted
        if invalid_payments := self.payment_ids._filter_needs_mandate_but_invalid():
            rslt.append({
                'title': self.env._("Some payments are missing a Direct Debit Mandate, or are linked to an invalid one."),
                'records': invalid_payments,
            })
        return rslt + super().check_payments_for_errors()

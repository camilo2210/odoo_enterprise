from odoo import models
from odoo.exceptions import UserError


class AccountOnlineAccount(models.Model):
    _inherit = 'account.online.account'

    def _check_payment_limit_exceeded(self, payments):
        """ Pre-check of the batch payment properties before starting the payment process with Odoofin.
        Other errors might still arise during that process and will be forwarded to the user.
        """
        institution_data = self.account_online_link_id._get_institution_data()
        payment_amount_limit = institution_data['payment_institution']['institution_payment_max_amount_limit']
        payment_instructions_limit = institution_data['payment_institution']['institution_payment_instructions_limit']

        if batch := payments.batch_payment_id:
            if payment_amount_limit and abs(batch.amount) > payment_amount_limit:
                raise UserError(self.env._(
                    "The maximum amount for payments with your bank is %(amount)s.\n"
                    "If you want to send your payment(s) through Odoo, please split your batch or create separate smaller payments.",
                    amount=self.currency_id.format(payment_amount_limit),
                ))
        else:
            if payment_amount_limit and abs(sum(payment.amount for payment in payments)) > payment_amount_limit:
                raise UserError(self.env._(
                    "The maximum amount for payments with your bank is %(amount)s.\n"
                    "If you want to send your payment(s) through Odoo, please split your batch or create separate smaller payments.",
                    amount=self.currency_id.format(payment_amount_limit),
                ))

        if payment_instructions_limit and len(payments) > payment_instructions_limit:
            raise UserError(self.env._(
                "Your bank allows a maximum of %(limit)s payments per batch.\n"
                "If you want to send your payments through Odoo, please split your batch.",
                limit=payment_instructions_limit,
            ))

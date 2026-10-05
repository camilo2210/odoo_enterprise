# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    l10n_tr_currency_rate_type = fields.Selection(
        selection=[("sell", "Selling"), ("buy", "Buying")],
        compute="_compute_l10n_tr_currency_rate_type",
        store=True,
        readonly=False,
        precompute=True,
        required=True,
        help="Whether the buying or selling exchange rate is used to convert this payment's currency.",
    )
    l10n_tr_payment_currency_rate = fields.Float(
        compute="_compute_l10n_tr_payment_currency_rate",
        digits=0,
        readonly=True,
        help="Currency rate from company currency to payment currency.",
    )

    @api.depends("payment_type")
    def _compute_l10n_tr_currency_rate_type(self):
        for payment in self:
            payment.l10n_tr_currency_rate_type = "buy" if payment.payment_type == "outbound" else "sell"

    @api.depends("currency_id", "company_id", "date", "l10n_tr_currency_rate_type")
    def _compute_l10n_tr_payment_currency_rate(self):
        for payment in self:
            if payment.currency_id and payment.currency_id != payment.company_currency_id:
                if payment.l10n_tr_currency_rate_type == "buy":
                    payment.l10n_tr_payment_currency_rate = self.env["res.currency"]._l10n_tr_get_buy_conversion_rate(
                        payment.company_currency_id, payment.currency_id, payment.company_id, payment.date
                    )
                else:
                    payment.l10n_tr_payment_currency_rate = self.env["res.currency"]._get_conversion_rate(
                        payment.company_currency_id, payment.currency_id, payment.company_id, payment.date
                    )
            else:
                payment.l10n_tr_payment_currency_rate = 1

    def l10n_tr_action_toggle_currency_rate_type(self):
        self.ensure_one()
        if self.state != "draft":
            return
        self.l10n_tr_currency_rate_type = "buy" if self.l10n_tr_currency_rate_type == "sell" else "sell"

    def _get_trigger_fields_to_synchronize(self):
        # EXTENDS account
        return super()._get_trigger_fields_to_synchronize() + ("l10n_tr_currency_rate_type",)

    def _prepare_move_lines_per_type(self, write_off_line_vals=None, force_balance=None):
        # EXTENDS account
        return super(AccountPayment, self.with_context(l10n_tr_currency_rate_type=self.l10n_tr_currency_rate_type))._prepare_move_lines_per_type(
            write_off_line_vals, force_balance
        )

    @api.depends("l10n_tr_currency_rate_type")
    def _compute_amount_company_currency_signed(self):
        # EXTENDS account
        for payment in self:
            super(AccountPayment, payment.with_context(l10n_tr_currency_rate_type=payment.l10n_tr_currency_rate_type))._compute_amount_company_currency_signed()

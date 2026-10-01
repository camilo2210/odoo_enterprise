# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    l10n_tr_currency_rate_type = fields.Selection(
        selection=[("sell", "Selling"), ("buy", "Buying")],
        compute="_compute_l10n_tr_currency_rate_type",
        store=True,
        readonly=False,
        help="Whether the buying or selling exchange rate is used to convert this payment's currency.",
    )

    @api.depends("payment_type")
    def _compute_l10n_tr_currency_rate_type(self):
        for wizard in self:
            wizard.l10n_tr_currency_rate_type = "buy" if wizard.payment_type == "outbound" else "sell"

    def l10n_tr_action_toggle_currency_rate_type(self):
        # An action must be returned, otherwise the JS defaults to closing the wizard dialog.
        self.ensure_one()
        self.l10n_tr_currency_rate_type = "buy" if self.l10n_tr_currency_rate_type == "sell" else "sell"
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    @api.depends("l10n_tr_currency_rate_type")
    def _compute_exchange_rate(self):
        # EXTENDS account
        for wizard in self:
            super(AccountPaymentRegister, wizard.with_context(l10n_tr_currency_rate_type=wizard.l10n_tr_currency_rate_type))._compute_exchange_rate()

    def _create_payment_vals_from_wizard(self, batch_result):
        # EXTENDS account
        payment_vals = super(AccountPaymentRegister, self.with_context(l10n_tr_currency_rate_type=self.l10n_tr_currency_rate_type))._create_payment_vals_from_wizard(
            batch_result
        )
        payment_vals["l10n_tr_currency_rate_type"] = self.l10n_tr_currency_rate_type
        return payment_vals

    def _create_payment_vals_from_batch(self, batch_result):
        # EXTENDS account
        batch_values = self._get_wizard_values_from_batch(batch_result)
        rate_type = "buy" if batch_values["payment_type"] == "outbound" else "sell"
        payment_vals = super(AccountPaymentRegister, self.with_context(l10n_tr_currency_rate_type=rate_type))._create_payment_vals_from_batch(
            batch_result
        )
        payment_vals["l10n_tr_currency_rate_type"] = rate_type
        return payment_vals

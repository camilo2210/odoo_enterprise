# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, timedelta

from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_tr_currency_rate_type = fields.Selection(
        selection=[("sell", "Selling"), ("buy", "Buying")],
        compute="_compute_l10n_tr_currency_rate_type",
        store=True,
        readonly=False,
        precompute=True,
        required=True,
        help="Whether the buying or selling exchange rate is used to convert this document's currency.",
    )

    @api.depends("move_type", "partner_id")
    def _compute_l10n_tr_currency_rate_type(self):
        for move in self:
            if move.is_purchase_document(include_receipts=True):
                move.l10n_tr_currency_rate_type = move.partner_id.l10n_tr_bill_currency_rate_type or "buy"
            else:
                move.l10n_tr_currency_rate_type = move.partner_id.l10n_tr_invoice_currency_rate_type or "sell"

    @api.depends("l10n_tr_currency_rate_type")
    def _compute_expected_currency_rate(self):
        # EXTENDS account
        super()._compute_expected_currency_rate()

    def _get_expected_currency_rate_at(self, date):
        # EXTENDS account
        self.ensure_one()
        if self.l10n_tr_currency_rate_type == "buy":
            return self.env["res.currency"]._l10n_tr_get_buy_conversion_rate(
                from_currency=self.company_currency_id, to_currency=self.currency_id, company=self.company_id, date=date
            )
        return super()._get_expected_currency_rate_at(date)

    def get_currency_rate(self, company_id, to_currency_id, requested_date):
        # EXTENDS account
        if len(self) == 1 and self.l10n_tr_currency_rate_type == "buy":
            company = self.env["res.company"].browse(company_id)
            to_currency = self.env["res.currency"].browse(to_currency_id)
            next_day = (date.fromisoformat(requested_date) + timedelta(days=1)).isoformat()
            return self.env["res.currency"]._l10n_tr_get_buy_conversion_rate(
                from_currency=company.currency_id, to_currency=to_currency, company=company, date=next_day
            )
        return super().get_currency_rate(company_id, to_currency_id, requested_date)

    def l10n_tr_action_toggle_currency_rate_type(self):
        self.ensure_one()
        if self.state != "draft":
            return
        self.l10n_tr_currency_rate_type = "buy" if self.l10n_tr_currency_rate_type == "sell" else "sell"

    def _post(self, soft=True):
        # EXTENDS account
        posted = super()._post(soft=soft)
        for move in posted:
            partner = move.commercial_partner_id
            if not partner or not move.company_id._l10n_tr_uses_buy_rate():
                continue
            if move.is_purchase_document(include_receipts=True):
                if not partner.l10n_tr_bill_currency_rate_type:
                    partner.l10n_tr_bill_currency_rate_type = move.l10n_tr_currency_rate_type
            elif move.is_sale_document(include_receipts=True):
                if not partner.l10n_tr_invoice_currency_rate_type:
                    partner.l10n_tr_invoice_currency_rate_type = move.l10n_tr_currency_rate_type
        return posted

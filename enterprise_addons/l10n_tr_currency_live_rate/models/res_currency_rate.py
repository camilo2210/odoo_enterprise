# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import UserError


class ResCurrencyRate(models.Model):
    _inherit = "res.currency.rate"

    l10n_tr_buy_rate = fields.Float(
        digits=0,
        aggregator="avg",
        help="The buying rate of the currency to the currency of rate 1",
        string="Technical Buy Rate",
    )
    l10n_tr_company_buy_rate = fields.Float(
        digits=0,
        compute="_compute_l10n_tr_company_buy_rate",
        inverse="_inverse_l10n_tr_company_buy_rate",
        aggregator="avg",
        help="The currency of rate 1 to the buying rate of the currency.",
    )
    l10n_tr_inverse_company_buy_rate = fields.Float(
        digits=0,
        compute="_compute_l10n_tr_inverse_company_buy_rate",
        inverse="_inverse_l10n_tr_inverse_company_buy_rate",
        aggregator="avg",
        help="The buying rate of the currency to the currency of rate 1 ",
    )

    _l10n_tr_buy_rate_check = models.Constraint(
        "CHECK (l10n_tr_buy_rate>0)",
        "The buying rate must be strictly positive.",
    )

    def _l10n_tr_get_latest_buy_rate(self):
        if not self.name:
            raise UserError(self.env._("The name for the current rate is empty.\nPlease set it."))
        return self.currency_id.rate_ids.sudo().filtered(lambda x: (
            x.l10n_tr_buy_rate
            and (x.company_id in (self.company_id or self.env.company.root_id) or not x.company_id)
            and x.name < (self.name or fields.Date.context_today(self))
        )).sorted("name")[-1:]

    def _l10n_tr_get_last_buy_rates_for_companies(self, companies):
        return {
            company: company.sudo().currency_id.rate_ids.filtered(lambda x: (
                x.l10n_tr_buy_rate
                and (x.company_id == company or not x.company_id)
            )).sorted("name")[-1:].l10n_tr_buy_rate or 1
            for company in companies
        }

    @api.depends("l10n_tr_buy_rate", "name", "currency_id", "company_id", "currency_id.rate_ids.l10n_tr_buy_rate")
    @api.depends_context("company")
    def _compute_l10n_tr_company_buy_rate(self):
        last_rate = self._l10n_tr_get_last_buy_rates_for_companies(self.company_id | self.env.company.root_id)
        for currency_rate in self:
            company = currency_rate.company_id or self.env.company.root_id
            currency_rate.l10n_tr_company_buy_rate = (currency_rate.l10n_tr_buy_rate or currency_rate._l10n_tr_get_latest_buy_rate().l10n_tr_buy_rate or 1.0) / last_rate[company]

    @api.onchange("l10n_tr_company_buy_rate")
    def _inverse_l10n_tr_company_buy_rate(self):
        last_rate = self._l10n_tr_get_last_buy_rates_for_companies(self.company_id | self.env.company.root_id)
        for currency_rate in self:
            company = currency_rate.company_id or self.env.company.root_id
            currency_rate.l10n_tr_buy_rate = currency_rate.l10n_tr_company_buy_rate * last_rate[company]

    @api.depends("l10n_tr_company_buy_rate")
    def _compute_l10n_tr_inverse_company_buy_rate(self):
        for currency_rate in self:
            if not currency_rate.l10n_tr_company_buy_rate:
                currency_rate.l10n_tr_company_buy_rate = 1.0  # noqa: OLS03019
            currency_rate.l10n_tr_inverse_company_buy_rate = 1.0 / currency_rate.l10n_tr_company_buy_rate

    @api.onchange("l10n_tr_inverse_company_buy_rate")
    def _inverse_l10n_tr_inverse_company_buy_rate(self):
        for currency_rate in self:
            if not currency_rate.l10n_tr_inverse_company_buy_rate:
                currency_rate.l10n_tr_inverse_company_buy_rate = 1.0
            currency_rate.l10n_tr_company_buy_rate = 1.0 / currency_rate.l10n_tr_inverse_company_buy_rate

    def _sanitize_vals(self, vals):
        # EXTENDS base
        vals = super()._sanitize_vals(vals)
        if "l10n_tr_inverse_company_buy_rate" in vals and ("l10n_tr_company_buy_rate" in vals or "l10n_tr_buy_rate" in vals):
            del vals["l10n_tr_inverse_company_buy_rate"]
        if "l10n_tr_company_buy_rate" in vals and "l10n_tr_buy_rate" in vals:
            del vals["l10n_tr_company_buy_rate"]
        return vals

    def write(self, vals):
        # EXTENDS base
        self.env["res.currency"].invalidate_model(["l10n_tr_inverse_buy_rate"])
        result = super().write(vals)
        if "rate" in vals and "l10n_tr_buy_rate" not in vals:
            self.filtered(lambda rate: not (rate.company_id or self.env.company)._l10n_tr_uses_buy_rate()).l10n_tr_buy_rate = vals["rate"]
        return result

    @api.model_create_multi
    def create(self, vals_list):
        # EXTENDS base
        for vals in vals_list:
            if not vals.get("l10n_tr_buy_rate") and vals.get("rate"):
                vals["l10n_tr_buy_rate"] = vals["rate"]
        self.env["res.currency"].invalidate_model(["l10n_tr_inverse_buy_rate"])
        return super().create(vals_list)

    @api.model
    def _get_view_cache_key(self, view_id=None, view_type="form", **options):
        # EXTENDS base
        key = super()._get_view_cache_key(view_id, view_type, **options)
        company = self.env["res.company"].browse(self.env.context.get("company_id")) or self.env.company
        return key + (
            company.currency_id.name,
            company._l10n_tr_uses_buy_rate(),
            self.env.context.get("active_id"),
        )

    @api.model
    def _get_view(self, view_id=None, view_type="form", **options):
        # EXTENDS base
        arch, view = super()._get_view(view_id, view_type, **options)
        company = self.env["res.company"].browse(self.env.context.get("company_id")) or self.env.company
        if view_type == "list" and company._l10n_tr_uses_buy_rate():
            names = {
                "company_currency_name": company.currency_id.name,
                "rate_currency_name": self.env["res.currency"].browse(self.env.context.get("active_id")).name or "Unit",
            }
            for name, label in [
                ["company_rate", self.env._("Selling %(rate_currency_name)s per %(company_currency_name)s", **names)],
                ["inverse_company_rate", self.env._("Selling %(company_currency_name)s per %(rate_currency_name)s", **names)],
                ["l10n_tr_company_buy_rate", self.env._("Buying %(rate_currency_name)s per %(company_currency_name)s", **names)],
                ["l10n_tr_inverse_company_buy_rate", self.env._("Buying %(company_currency_name)s per %(rate_currency_name)s", **names)],
            ]:
                if (node := arch.find(f"./field[@name='{name}']")) is not None:
                    node.set("string", label)
        return arch, view

# Part of Odoo. See LICENSE file for full copyright and licensing details.

from lxml.builder import E

from odoo import api, fields, models
from odoo.tools import SQL


class ResCurrency(models.Model):
    _inherit = "res.currency"

    l10n_tr_buy_rate = fields.Float(compute="_compute_l10n_tr_current_buy_rate", digits=0, help="The buying rate of the currency to the currency of rate 1.")
    l10n_tr_inverse_buy_rate = fields.Float(compute="_compute_l10n_tr_current_buy_rate", digits=0, readonly=True, help="The currency of rate 1 to the buying rate of the currency.")
    l10n_tr_show_buy_rate = fields.Boolean(compute="_compute_l10n_tr_show_buy_rate")

    @api.depends_context("company", "company_id")
    def _compute_l10n_tr_show_buy_rate(self):
        company = self.env["res.company"].browse(self.env.context.get("company_id")) or self.env.company
        self.l10n_tr_show_buy_rate = company._l10n_tr_uses_buy_rate()

    def _l10n_tr_get_buy_rates(self, company, date):
        # Mirrors core's res.currency._get_rates, keyed off l10n_tr_buy_rate instead of rate. Caching deliberately omitted.
        if not self.ids:
            return {}
        company = company.root_id
        Currency = self.env["res.currency"].sudo()
        Rate = self.env["res.currency.rate"].sudo()

        currency_query = Currency._search([("id", "in", self.ids)], active_test=False)
        currency_id_field = currency_query.table.id

        rate_query = Rate._search(
            [("name", "<", date), ("company_id", "in", (False, company.root_id.id))],
            order="company_id.id, name DESC", limit=1,
        )
        rate_table = rate_query.table
        rate_query.add_where(SQL("%s = %s", rate_table.currency_id, currency_id_field))
        rate_query = rate_query.subselect(rate_table.l10n_tr_buy_rate)
        currency_query.add_join("LEFT JOIN LATERAL", "before_rate", rate_query, SQL("TRUE"))

        rate_query_fallback = Rate._search(
            [("company_id", "in", (False, company.root_id.id))],
            order="company_id.id, name ASC", limit=1,
        )
        rate_table_fallback = rate_query_fallback.table
        rate_query_fallback.add_where(SQL("%s = %s", rate_table_fallback.currency_id, currency_id_field))
        rate_query_fallback = rate_query_fallback.subselect(rate_table_fallback.l10n_tr_buy_rate)
        currency_query.add_join("LEFT JOIN LATERAL", "after_rate", rate_query_fallback, SQL("TRUE"))

        return dict(self.env.execute_query(currency_query.select(
            SQL.identifier("res_currency", "id"),
            SQL('COALESCE("before_rate"."l10n_tr_buy_rate", "after_rate"."l10n_tr_buy_rate", 1.0) AS "l10n_tr_buy_rate"'),
        )))

    @api.depends("rate_ids.l10n_tr_buy_rate")
    @api.depends_context("to_currency", "date", "company", "company_id")
    def _compute_l10n_tr_current_buy_rate(self):
        date = self.env.context.get("date") or fields.Date.context_today(self)
        company = self.env["res.company"].browse(self.env.context.get("company_id")) or self.env.company
        to_currency = self.browse(self.env.context.get("to_currency")) or company.currency_id
        currency_rates = (self + to_currency)._l10n_tr_get_buy_rates(self.env.company, date)
        for currency in self:
            currency.l10n_tr_buy_rate = (currency_rates.get(currency.id) or 1.0) / currency_rates.get(to_currency.id)
            currency.l10n_tr_inverse_buy_rate = 1 / currency.l10n_tr_buy_rate

    def _l10n_tr_get_buy_conversion_rate(self, from_currency, to_currency, company=None, date=None):
        if from_currency == to_currency:
            return 1
        company = (company or self.env.company).root_id
        if company in self.env["res.company"].browse(self.env.user._get_company_ids()).root_id:
            from_currency = from_currency.sudo()
        date = date or fields.Date.context_today(self)
        return from_currency.with_company(company).with_context(to_currency=to_currency.id, date=str(date)).l10n_tr_inverse_buy_rate

    @api.model
    def _get_conversion_rate(self, from_currency, to_currency, company=None, date=None):
        # EXTENDS base
        if self.env.context.get("l10n_tr_currency_rate_type") == "buy":
            return self._l10n_tr_get_buy_conversion_rate(from_currency, to_currency, company, date)
        return super()._get_conversion_rate(from_currency, to_currency, company, date)

    @api.model
    def _get_view_cache_key(self, view_id=None, view_type="form", **options):
        # EXTENDS base: the labels below depend on the company currency and on whether it uses buying rates.
        key = super()._get_view_cache_key(view_id, view_type, **options)
        company = self.env["res.company"].browse(self.env.context.get("company_id")) or self.env.company
        return key + (company.currency_id.name, company._l10n_tr_uses_buy_rate())

    @api.model
    def _get_view(self, view_id=None, view_type="form", **options):
        # EXTENDS base
        arch, view = super()._get_view(view_id, view_type, **options)
        company = self.env["res.company"].browse(self.env.context.get("company_id")) or self.env.company
        if view_type in {"list", "form"} and company._l10n_tr_uses_buy_rate():
            currency_name = company.currency_id.name
            fields_maps = [
                [["company_rate", "rate"], self.env._("Selling Unit per %s", currency_name)],
                [["inverse_company_rate", "inverse_rate"], self.env._("Selling %s per Unit", currency_name)],
                [["l10n_tr_company_buy_rate"], self.env._("Buying Unit per %s", currency_name)],
                [["l10n_tr_inverse_company_buy_rate"], self.env._("Buying %s per Unit", currency_name)],
            ]
            for fnames, label in fields_maps:
                xpath_expression = "//list//field[" + " or ".join(f"@name='{f}'" for f in fnames) + "][1]"
                node = arch.xpath(xpath_expression)
                if node:
                    node[0].set("string", label)
            if view_type == "list":
                # column_invisible can't be keyed on the company on a root list, so the buying
                # columns are injected here instead, for buy/sell companies only.
                for sell_fname, buy_fname, label in [
                    ("rate", "l10n_tr_buy_rate", self.env._("Buying Unit per %s", currency_name)),
                    ("inverse_rate", "l10n_tr_inverse_buy_rate", self.env._("Buying %s per Unit", currency_name)),
                ]:
                    if (node := arch.find(f"./field[@name='{sell_fname}']")) is not None:
                        node.addnext(E.field(**{**node.attrib, "name": buy_fname, "string": label}))
        return arch, view

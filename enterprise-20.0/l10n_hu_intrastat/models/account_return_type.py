from dateutil.relativedelta import relativedelta
from itertools import zip_longest

from odoo import api, fields, models


class AccountReturnType(models.Model):
    _inherit = 'account.return.type'

    @api.model
    def _generate_all_returns(self, country_code, main_company, tax_unit=None, return_types=None):
        intrastat_return_type = self.env.ref('l10n_hu_intrastat.hu_intrastat_goods_return_type', raise_if_not_found=False)
        expression_purchase = self.env.ref('l10n_hu.tax_report_alap_viss_tag', raise_if_not_found=False)
        expression_sale = self.env.ref('l10n_hu.tax_report_alap_fiz_eu_tag', raise_if_not_found=False)

        if country_code != 'HU' or not intrastat_return_type or not expression_purchase or not expression_sale:
            return super()._generate_all_returns(country_code, main_company, tax_unit=tax_unit, return_types=return_types)

        if self.env.ref('l10n_hu.a60g_rec_balance', raise_if_not_found=False):
            # This mean a60 report is installed & COA is up to date, the old expressions are split, and we need to get them all
            a60_labels = {'a60g', 'a60b', 'a60k', 'a60r', 'a60c', 'a60v'}
            expression_purchase = expression_purchase._expand_aggregations().filtered(lambda exp: exp.label in a60_labels)
            expression_sale = expression_sale._expand_aggregations().filtered(lambda exp: exp.label in a60_labels)

        expressions = expression_purchase + expression_sale
        today = fields.Date.context_today(self)
        date_from = fields.Date.start_of(today - relativedelta(years=1), 'month')
        date_to = fields.Date.end_of(today - relativedelta(months=1), 'month')

        options = {
            'date': {
                'date_from': fields.Date.to_string(date_from),
                'date_to': fields.Date.to_string(date_to),
                'filter': 'custom',
                'mode': 'range',
            },
            'selected_variant_id': intrastat_return_type.report_id.id,
            'sections_source_id': intrastat_return_type.report_id.id,
            'tax_unit': tax_unit and tax_unit.id or 'company_only',
        }
        company_ids = self.env['account.return'].sudo()._get_company_ids(main_company, tax_unit, intrastat_return_type.report_id)
        options = intrastat_return_type.report_id.sudo().with_context(allowed_company_ids=company_ids.ids).get_options(previous_options=options)

        if not (tax_return_type := self.env.ref('l10n_hu_reports.hu_tax_return_type', raise_if_not_found=False)):
            return super()._generate_all_returns(country_code, main_company, tax_unit=tax_unit, return_types=return_types)
        expression_totals_per_col_group = tax_return_type.sudo().report_id._compute_expression_totals_for_each_column_group(
            expressions,
            options,
            warnings={}
        )

        expression_totals = next(iter(expression_totals_per_col_group.values()))
        balance_purchase = 0
        balance_sale = 0

        for exp_sale, exp_purchases in zip_longest(expression_sale, expression_purchase, fillvalue={}):
            balance_purchase += expression_totals.get(exp_purchases, {}).get('value', 0)
            balance_sale += expression_totals.get(exp_sale, {}).get('value', 0)

        # An intrastat return must be generated if the threshold exceeds 150 Millions in sale or 270 Millions in purchase in the 12 months period
        if main_company.currency_id.compare_amounts(balance_purchase, 270000000) >= 0 or main_company.currency_id.compare_amounts(balance_sale, 150000000) >= 0:
            months_offset = intrastat_return_type._get_periodicity_months_delay(main_company)
            intrastat_return_type._try_create_return_for_period(today - relativedelta(months=months_offset), main_company, tax_unit)

        return super()._generate_all_returns(country_code, main_company, tax_unit=tax_unit, return_types=return_types)

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class AccountReturnType(models.Model):
    _inherit = 'account.return.type'

    @api.model
    def _generate_all_returns(self, country_code, main_company, tax_unit=None, return_types=None):
        if country_code != 'SE':
            return super()._generate_all_returns(country_code, main_company, tax_unit=tax_unit, return_types=return_types)

        intrastat_return_type = self.env.ref('l10n_se_intrastat.se_intrastat_goods_return_type')
        expressions = (
            self.env.ref('l10n_se.tax_report_line_35_tag')
            | self.env.ref('l10n_se.tax_report_line_36_tag')
        )

        today = fields.Date.context_today(self)
        instrastat_date_from = fields.Date.start_of(today - relativedelta(years=1), 'year')
        instrastat_date_to = fields.Date.end_of(today, 'year')

        options = {
            'date': {
                'date_from': fields.Date.to_string(instrastat_date_from),
                'date_to': fields.Date.to_string(instrastat_date_to),
            },
            'selected_variant_id': intrastat_return_type.report_id.id,
            'sections_source_id': intrastat_return_type.report_id.id,
            'tax_unit': 'company_only' if not tax_unit else tax_unit.id,
        }
        company_ids = self.env['account.return'].sudo()._get_company_ids(main_company, tax_unit, intrastat_return_type.report_id)
        options = intrastat_return_type.report_id.sudo().with_context(allowed_company_ids=company_ids.ids).get_options(previous_options=options)

        balance = 0
        expression_totals_per_col_group = self.env.ref('l10n_se_reports.se_tax_return_type').sudo().report_id._compute_expression_totals_for_each_column_group(
            expressions,
            options,
            warnings={}
        )
        expression_totals = next(iter(expression_totals_per_col_group.values()))
        for expression in expressions:
            balance += expression_totals.get(expression, {}).get('value') or 0

        sek_currency = self.env['res.currency'].search([('name', '=', 'SEK')], limit=1)

        if sek_currency and main_company.currency_id:
            # Convert the balance from company currency to SEK
            balance_in_sek = main_company.currency_id._convert(
                balance,
                sek_currency,
                main_company,
                today
            )

            # An intrastat return must be generated if the threshold exceeds 1 700 000 kr in the current and last year
            if sek_currency.compare_amounts(balance_in_sek, 1_700_000) >= 0:
                months_offset = intrastat_return_type._get_periodicity_months_delay(main_company)
                intrastat_return_type._try_create_return_for_period(today - relativedelta(months=months_offset), main_company, tax_unit)

        return super()._generate_all_returns(country_code, main_company, tax_unit=tax_unit, return_types=return_types)

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models


class AccountReturnType(models.Model):
    _inherit = 'account.return.type'

    @api.model
    def _generate_all_returns(self, country_code, main_company, tax_unit=None, return_types=None):
        rslt = super()._generate_all_returns(country_code, main_company, tax_unit=tax_unit, return_types=return_types)

        if country_code == 'IE':
            intrastat_return_type = self.env.ref('l10n_ie_intrastat.ie_intrastat_goods_return_type')
            company_ids = self.env['account.return'].sudo()._get_company_ids(main_company, tax_unit, intrastat_return_type.report_id)
            report = self.env.ref('account_intrastat.intrastat_report').with_context(allowed_company_ids=company_ids.ids)
            report_handler = self.env[report.custom_handler_model_name]
            offset = intrastat_return_type._get_periodicity_months_delay(main_company)
            date_in_previous_period = fields.Date.context_today(self) - relativedelta(months=offset)
            date_from, date_to = intrastat_return_type._get_period_boundaries(main_company, date_in_previous_period)
            options = {
                'date': {
                    'date_from': fields.Date.to_string(date_from),
                    'date_to': fields.Date.to_string(date_to),
                },
                'selected_variant_id': intrastat_return_type.report_id.id,
                'sections_source_id': intrastat_return_type.report_id.id,
                'tax_unit': 'company_only' if not tax_unit else tax_unit.id,
                'intrastat_type': [
                    {'name': _('Arrival'), 'selected': True, 'id': 'arrival'},
                    {'name': _('Dispatch'), 'selected': False, 'id': 'dispatch'},
                ],
            }

            expressions = report.line_ids.expression_ids
            formulas_dict = expressions.grouped('formula')

            # Does arrival entries (imports) exceed the threshold of 750,000€?
            arrival_options = report.get_options(previous_options=options)
            amount = report_handler._report_engine_intrastat(arrival_options, expressions[0].date_scope, formulas_dict, None)[expressions]['value']
            if amount >= 750_000:
                intrastat_return_type._try_create_return_for_period(date_from, main_company, tax_unit)
                return rslt

            # Does dispatched entries (exports) exceed the threshold of 750,000€?
            options['intrastat_type'][0]['selected'] = False
            options['intrastat_type'][1]['selected'] = True
            dispatch_options = report.get_options(previous_options=options)
            amount = report_handler._report_engine_intrastat(dispatch_options, expressions[0].date_scope, formulas_dict, None)[expressions]['value']
            if amount >= 750_000:
                intrastat_return_type._try_create_return_for_period(date_from, main_company, tax_unit)

        return rslt

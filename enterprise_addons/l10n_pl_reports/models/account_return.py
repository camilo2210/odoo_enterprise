from itertools import chain
from dateutil.relativedelta import relativedelta
from odoo import fields, models


class AccountReturnType(models.Model):
    _inherit = 'account.return.type'

    def _generate_all_returns(self, country_code, main_company, tax_unit=None, return_types=None):
        rslt = super()._generate_all_returns(country_code, main_company, tax_unit=tax_unit, return_types=return_types)

        if country_code == 'PL' and (ec_sales_return_type := self.env.ref('l10n_pl_reports.pl_ec_sales_list_return_type', raise_if_not_found=False)):

            months_offset = ec_sales_return_type._get_periodicity_months_delay(main_company)
            previous_period_start, previous_period_end = ec_sales_return_type._get_period_boundaries(main_company, fields.Date.context_today(self) - relativedelta(months=months_offset))
            company_ids = self.env['account.return'].sudo()._get_company_ids(main_company, tax_unit, ec_sales_return_type.report_id)
            ec_sales_list_tags_info = self.env['l10n_pl_reports.ec.sales.report.handler']._get_ec_sales_tax_tags()
            ec_sales_list_tag_ids = list(chain(*ec_sales_list_tags_info.values()))

            need_ec_sales_list = bool(self.env['account.move.line'].search_count([
                ('tax_tag_ids', 'in', ec_sales_list_tag_ids),
                *self.env['account.move.line']._check_company_domain(company_ids.ids),
                ('date', '>=', previous_period_start),
                ('date', '<=', previous_period_end),
            ], limit=1))

            if need_ec_sales_list:
                ec_sales_return_type._try_create_return_for_period(previous_period_start, main_company, tax_unit)

        return rslt


class AccountReturn(models.Model):
    _inherit = 'account.return'

    def _evaluate_deadline(self, company, return_type, return_type_external_id, date_from, date_to):
        months_per_period = return_type._get_periodicity_months_delay(company)
        if return_type_external_id == 'l10n_pl_reports.pl_tax_return_type':
            return date_to + relativedelta(days=16)
        if return_type_external_id == 'l10n_pl_reports.pl_ec_sales_list_return_type' and months_per_period in (1, 3):
            return date_to + relativedelta(days=25)

        return super()._evaluate_deadline(company, return_type, return_type_external_id, date_from, date_to)

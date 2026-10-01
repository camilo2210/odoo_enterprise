from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class AccountReturn(models.Model):
    _inherit = 'account.return'

    @api.model
    def _evaluate_deadline(self, company, return_type, return_type_external_id, date_from, date_to):
        # Extends account_reports
        if return_type_external_id == 'l10n_mt_reports.mt_tax_return_type' and not return_type.with_company(company).deadline_days_delay:
            return date_to + relativedelta(days=15) + relativedelta(months=1)

        return super()._evaluate_deadline(company, return_type, return_type_external_id, date_from, date_to)

    def _prepare_submission(self):
        # Extends account_reports
        if self.type_external_id == 'l10n_mt_reports.mt_ec_sales_list_return_type':
            return self.env['l10n_mt_reports.ec.sales.list.submission.wizard']._open_submission_wizard(self)
        if self.type_external_id == 'l10n_mt_reports.mt_tax_return_type':
            return self.env['l10n_mt_reports.tax.return.submission.wizard']._open_submission_wizard(self)
        return super()._prepare_submission()


class AccountReturnType(models.Model):
    _inherit = 'account.return.type'

    @api.model
    def _generate_all_returns(self, country_code, main_company, tax_unit=None, return_types=None):
        # Extends account_reports
        rslt = super()._generate_all_returns(country_code, main_company, tax_unit=tax_unit, return_types=return_types)

        if country_code == 'MT':
            ec_sales_return_type = self.env.ref('l10n_mt_reports.mt_ec_sales_list_return_type')
            months_offset = ec_sales_return_type._get_periodicity_months_delay(main_company)
            previous_period_start, previous_period_end = ec_sales_return_type._get_period_boundaries(main_company, fields.Date.context_today(self) - relativedelta(months=months_offset))
            company_ids = self.env['account.return'].sudo()._get_company_ids(main_company, tax_unit, ec_sales_return_type.report_id)

            ec_sales_list_tag_ids = [
                *self.env.ref('l10n_mt.tax_report_line_I_3_tag_column1')._get_matching_tags().ids,
                *self.env.ref('l10n_mt.tax_report_line_I_4_tag_column1')._get_matching_tags().ids,
            ]

            need_ec_sales_list = self.env['account.move.line'].search_count([
                ('tax_tag_ids', 'in', ec_sales_list_tag_ids),
                ('company_id', 'in', company_ids.ids),
                ('date', '>=', previous_period_start),
                ('date', '<=', previous_period_end),
            ], limit=1)

            if need_ec_sales_list:
                ec_sales_return_type._try_create_return_for_period(previous_period_start, main_company, tax_unit)

        return rslt

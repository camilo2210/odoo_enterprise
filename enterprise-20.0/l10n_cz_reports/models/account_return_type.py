from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class AccountReturnType(models.Model):
    _inherit = 'account.return.type'

    @api.model
    def _generate_all_returns(self, country_code, main_company, tax_unit=None, return_types=None):
        rslt = super()._generate_all_returns(country_code, main_company, tax_unit=tax_unit, return_types=return_types)

        if country_code != 'CZ':
            return rslt

        vies_summary_return_type = self.env.ref('l10n_cz_reports.cz_vies_summary_return_type')
        months_offset = vies_summary_return_type._get_periodicity_months_delay(main_company)
        previous_period_start, previous_period_end = vies_summary_return_type._get_period_boundaries(main_company, fields.Date.context_today(self) - relativedelta(months=months_offset))
        company_ids = self.env['account.return'].sudo()._get_company_ids(main_company, tax_unit, vies_summary_return_type.report_id)

        tag_ids = [
            *self.env.ref('l10n_cz.l10n_cz_vat_declaration_line_22').expression_ids._get_matching_tags().ids,
            *self.env.ref('l10n_cz.l10n_cz_vat_declaration_line_23').expression_ids._get_matching_tags().ids,
            *self.env.ref('l10n_cz.l10n_cz_vat_declaration_line_27').expression_ids._get_matching_tags().ids,
        ]
        need_vies_summary_return = self.env['account.move.line'].search_count([
            ('tax_tag_ids', 'in', tag_ids),
            ('company_id', 'in', company_ids.ids),
            ('date', '>=', previous_period_start),
            ('date', '<=', previous_period_end),
        ], limit=1)

        if need_vies_summary_return:
            vies_summary_return_type._try_create_return_for_period(previous_period_start, main_company, tax_unit=tax_unit)

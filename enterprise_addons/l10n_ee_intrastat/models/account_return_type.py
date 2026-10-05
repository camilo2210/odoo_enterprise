from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class AccountReturnType(models.Model):
    _inherit = 'account.return.type'

    @api.model
    def _generate_all_returns(self, country_code, main_company, tax_unit=None, return_types=None):

        if country_code == 'EE':
            intrastat_return_type = self.env.ref("l10n_ee_intrastat.ee_intrastat_goods_return_type")
            today = fields.Date.context_today(self)

            intrastat_date_from = fields.Date.start_of(today - relativedelta(years=1), 'year')
            intrastat_date_to = fields.Date.end_of(today, 'year')

            companies = self.env['account.return'].sudo()._get_company_ids(main_company, tax_unit, intrastat_return_type.report_id)
            allowed_countries_ids = self.env['res.country.group'].search([('code', '=', 'EU')]).country_ids.ids

            invoices = self.env['account.move'].search([
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
                ('invoice_date', '>=', intrastat_date_from),
                ('invoice_date', '<=', intrastat_date_to),
                ('company_id', 'in', companies.ids),
                ('partner_id.country_code', '!=', 'EE'),
                ('partner_id.country_id', 'in', allowed_countries_ids),
            ])

            total_amount = sum(invoices.mapped('amount_total'))

            if main_company.currency_id.compare_amounts(total_amount, 350000) >= 0:
                months_offset = intrastat_return_type._get_periodicity_months_delay(main_company)
                intrastat_return_type._try_create_return_for_period(today - relativedelta(months=months_offset), main_company, tax_unit)

        return super()._generate_all_returns(country_code, main_company, tax_unit=tax_unit, return_types=return_types)

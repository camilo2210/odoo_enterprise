from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class AccountReturnType(models.Model):
    _inherit = 'account.return.type'

    @api.model
    def _generate_all_returns(self, country_code, main_company, tax_unit=None, return_types=None):
        # EXTENDS account_reports
        if country_code == 'HU':
            a60_return_type = self.env.ref('l10n_hu_reports_a60.hu_a60_return_type')
            months_offset = a60_return_type._get_periodicity_months_delay(main_company)
            previous_period_start, _previous_period_end = a60_return_type._get_period_boundaries(main_company, fields.Date.context_today(self) - relativedelta(months=months_offset))
            a60_return_type._try_create_return_for_period(previous_period_start, main_company, tax_unit)

        super()._generate_all_returns(country_code, main_company, tax_unit=tax_unit, return_types=return_types)

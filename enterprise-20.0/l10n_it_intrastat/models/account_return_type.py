from dateutil.relativedelta import relativedelta

from odoo import fields, models


class AccountReturnType(models.Model):
    _inherit = 'account.return.type'

    def _generate_all_returns(self, country_code, main_company, tax_unit=None, return_types=None):

        if country_code == 'IT' and (it_intrastat_return_type := self.env.ref('l10n_it_intrastat.it_intrastat_goods_return_type', raise_if_not_found=False)):
            months_offset = it_intrastat_return_type._get_periodicity_months_delay(main_company)
            it_intrastat_return_type._try_create_return_for_period(
                fields.Date.context_today(self) - relativedelta(months=months_offset),
                main_company,
                tax_unit,
            )

        return super()._generate_all_returns(country_code, main_company, tax_unit=tax_unit, return_types=return_types)

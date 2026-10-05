# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    def _pre_reload_data(self, company, template_data, data, force_create=True, force_update=False):
        accounts_data = data.get('account.account', {})
        pending_categories = {
            xmlid: values['fiscal_category_id']
            for xmlid, values in accounts_data.items()
            if values.get('fiscal_category_id')
        }
        pending_rates = {
            xmlid: list(values['rate_ids'])
            for xmlid, values in accounts_data.items()
            if values.get('rate_ids')
        }

        super()._pre_reload_data(company, template_data, data, force_create, force_update)

        accounts_data = data.setdefault('account.account', {})

        for xmlid, fiscal_category_id in pending_categories.items():
            account = self.ref(xmlid, raise_if_not_found=False)
            if account and not account.fiscal_category_id:
                accounts_data.setdefault(xmlid, {})['fiscal_category_id'] = fiscal_category_id

        for xmlid, rate_commands in pending_rates.items():
            account = self.ref(xmlid, raise_if_not_found=False)
            if not account:
                continue
            existing_dates = set(account.rate_ids.mapped('date_from'))
            new_rate_commands = [
                command for command in rate_commands
                if (date_from := fields.Date.to_date(command[2].get('date_from')))
                and date_from not in existing_dates
            ]
            if new_rate_commands:
                accounts_data.setdefault(xmlid, {})['rate_ids'] = new_rate_commands
            elif xmlid in accounts_data:
                accounts_data[xmlid].pop('rate_ids', None)

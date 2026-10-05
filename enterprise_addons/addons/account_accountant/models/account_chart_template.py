# -*- coding: utf-8 -*-
from odoo.addons.account.models.chart_template import template
from odoo import models, modules


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template(model='res.company')
    def _get_account_accountant_res_company(self, template_code):
        # Default values when not defined in the CoA base module
        # Should be loaded with _load_pre_defined_data in the post init hook.
        company = self.env.company
        account_data = self._get_account_account(template_code)
        return {
            company.id: {
                'deferred_expense_journal_id': company.deferred_expense_journal_id.id or 'general',
                'deferred_revenue_journal_id': company.deferred_revenue_journal_id.id or 'general',
                'deferred_expense_account_id': company.deferred_expense_account_id.id or next((xid for xid, d in account_data.items() if d['account_type'] == 'asset_current'), None),
                'deferred_revenue_account_id': company.deferred_revenue_account_id.id or next((xid for xid, d in account_data.items() if d['account_type'] == 'liability_current'), None)
            }
        }

    def _post_load_data(self, template_code, company, template_data):
        super()._post_load_data(template_code, company, template_data)

        sepa_countries = self.env.ref('base.sepa_zone').country_ids
        if company.country_id in sepa_countries:
            sepa_module = self.env['ir.module.module'].sudo().search([('name', '=', 'account_iso20022')], limit=1)
            if sepa_module and sepa_module.state != 'installed':
                if self.env.registry.ready and not modules.module.current_test and not self.env.context.get('install_demo'):
                    sepa_module.button_immediate_install()
                else:
                    sepa_module.button_install()

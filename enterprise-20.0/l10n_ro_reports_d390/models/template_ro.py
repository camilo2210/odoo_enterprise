from odoo import models

from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('ro', 'account.tax')
    def _get_ro_sales_report_account_tax(self):
        ro_sales_report_tax = self._parse_csv('ro', 'account.tax', module='l10n_ro_reports_d390')
        existing_taxes = self.env['account.tax'].search([('company_id', 'child_of', self.env.company.root_id.id)])
        # Filter out taxes that already exist
        existing_tax_names = set(existing_taxes.mapped('name'))
        taxes_to_create = {name: tax for name, tax in ro_sales_report_tax.items() if tax['name'] not in existing_tax_names}
        self._deref_account_tags('ro', ro_sales_report_tax)
        return taxes_to_create

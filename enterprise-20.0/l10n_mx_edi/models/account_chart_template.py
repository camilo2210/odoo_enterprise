# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models
from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('mx', 'account.tax.group')
    def _get_mx_edi_account_tax_group(self):
        return self._parse_csv('mx', 'account.tax.group', module='l10n_mx_edi')

    @template('mx', 'account.tax')
    def _get_mx_edi_account_tax(self):
        return self._parse_csv('mx', 'account.tax', module='l10n_mx_edi')

    @template(template='mx', model='res.company')
    def _get_mx_res_company_account(self):
        return {
            self.env.company.id: {
                'l10n_mx_edi_factoring_account_id': 'cuenta203_09',
            }
        }

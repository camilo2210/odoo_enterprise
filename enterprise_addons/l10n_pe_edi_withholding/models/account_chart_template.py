# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models

from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('pe', 'account.tax')
    def _get_pe_withholding_account_tax(self):
        return self._parse_csv('pe', 'account.tax', module='l10n_pe_edi_withholding')

    @template('pe', 'ir.sequence')
    def _get_pe_withholding_ir_sequence(self):
        return {
            'l10n_pe_edi_withholding_sunat_sequence': {
                'name': "SUNAT Retention Sequence",
                'padding': 8,
                'prefix': 'RRR1-',
                'number_next': 1,
            },
        }

    @template('pe', 'res.company')
    def _get_pe_withholding_res_company(self):
        return {
            self.env.company.id: {
                'withholding_tax_base_account_id': 'chart40114',
            },
        }

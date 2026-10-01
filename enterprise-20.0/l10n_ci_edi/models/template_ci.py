from odoo import models
from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('ci', 'account.tax')
    def _get_ci_edi_account_tax(self):
        return self._parse_csv('ci', 'account.tax', module='l10n_ci_edi')

    @template('ci_syscebnl', 'account.tax')
    def _get_ci_syscebnl_edi_account_tax(self):
        return self._parse_csv('ci_syscebnl', 'account.tax', module='l10n_ci_edi')

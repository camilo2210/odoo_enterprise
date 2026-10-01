# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models
from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('co', 'account.account')
    def _get_co_accounts(self):
        return self._parse_csv('co', 'account.account', module='l10n_co_reports')

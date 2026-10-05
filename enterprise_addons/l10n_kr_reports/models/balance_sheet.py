# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class L10nKrBalanceSheetReportHandler(models.AbstractModel):
    _name = 'l10n_kr.balance.sheet.report.handler'
    _inherit = 'account.balance.sheet.report.handler'
    _description = "Korean Balance Sheet Custom Handler"

    def _custom_options_initializer(self, report, options, previous_options=None):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        options['ignore_totals_below_sections'] = True

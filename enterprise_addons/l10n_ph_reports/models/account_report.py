# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class AccountReport(models.Model):
    _inherit = 'account.report'

    def _get_reports_to_print(self, options):
        # For BIR 2306/2307, print only the selected section, not both certificates together
        if self in [self.env.ref('l10n_ph_reports.2307_report'), self.env.ref('l10n_ph_reports.2306_report')]:
            return self.env['account.report'].browse(options['selected_section_id'])
        return super()._get_reports_to_print(options)

    def _get_specific_paperformat_args(self, options):
        if self in [self.env.ref('l10n_ph_reports.2307_report'), self.env.ref('l10n_ph_reports.2306_report')]:
            return {
                'data-report-margin-top': 3,
                'data-report-header-spacing': 5,
                'data-report-margin-bottom': 1,
            }
        return super()._get_specific_paperformat_args(options)

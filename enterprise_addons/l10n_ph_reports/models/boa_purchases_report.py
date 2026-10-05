# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class L10nPhBoaPurchasesReportHandler(models.AbstractModel):
    _name = "l10n_ph.boa.purchases.report.handler"
    _inherit = "l10n_ph.boa.move.report.handler"
    _description = "Book of Accounts - Purchases Custom Handler"

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        options["journal_type"] = "purchase"

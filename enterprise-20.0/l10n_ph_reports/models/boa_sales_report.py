# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class L10nPhBoaSalesReportHandler(models.AbstractModel):
    _name = "l10n_ph.boa.sales.report.handler"
    _inherit = "l10n_ph.boa.move.report.handler"
    _description = "Book of Accounts - Sales Custom Handler"

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        options["journal_type"] = "sale"

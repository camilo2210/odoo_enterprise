from odoo import models


class AccountReturn(models.Model):
    _inherit = 'account.return'

    def _prepare_submission(self):
        # OVERRIDE
        if self.type_external_id == 'l10n_ma_reports.ma_tax_return_type':
            return self.env['l10n_ma_reports.vat.listing.submission.wizard']._open_submission_wizard(self)

        return super()._prepare_submission()

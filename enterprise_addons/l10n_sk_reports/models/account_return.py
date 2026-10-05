from odoo import models


class AccountReturn(models.Model):
    _inherit = 'account.return'

    def _prepare_submission(self):
        # Extends account_reports
        if self.type_external_id == 'l10n_sk_reports.sk_tax_return_type':
            return self.env['l10n_sk_reports.vat.return.submission.wizard']._open_submission_wizard(self)
        if self.type_external_id == 'l10n_sk_reports.sk_vat_control_statement_return_type':
            return self.env['l10n_sk_reports.vat.control.statement.wizard']._open_submission_wizard(self)
        if self.type_external_id == 'l10n_sk_reports.sk_vies_summary_return_type':
            return self.env['l10n_sk_reports.vies.summary.submission.wizard']._open_submission_wizard(self)

        return super()._prepare_submission()

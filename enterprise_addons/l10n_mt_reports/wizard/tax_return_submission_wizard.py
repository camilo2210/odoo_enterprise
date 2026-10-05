from odoo import models


class L10n_Mt_ReportsEcSalesListSubmissionWizard(models.TransientModel):
    _name = 'l10n_mt_reports.tax.return.submission.wizard'
    _inherit = 'account.return.submission.wizard'
    _description = 'Tax Return Submission Wizard'

    def action_proceed_with_submission(self):
        # Extends account_reports
        self.return_id._mark_completed()
        return super().action_proceed_with_submission()

from odoo import models


class L10n_Rs_ReportsTaxReturnSubmissionWizard(models.TransientModel):
    _name = 'l10n_rs_reports.tax.return.submission.wizard'
    _inherit = 'account.return.submission.wizard'
    _description = "rs Tax Return Submission Wizard"

    def action_proceed_with_submission(self):
        # Extends account_reports
        self.return_id.is_completed = True
        super().action_proceed_with_submission()

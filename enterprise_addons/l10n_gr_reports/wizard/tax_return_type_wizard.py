from odoo import models


class L10n_Gr_ReportsTaxReturnSubmissionWizard(models.TransientModel):
    _name = 'l10n_gr_reports.tax.return.submission.wizard'
    _inherit = 'account.return.submission.wizard'
    _description = 'GR Tax Return Submission Wizard'

    def action_proceed_with_submission(self):
        # Extends account_reports
        self.return_id.is_completed = True
        return super().action_proceed_with_submission()

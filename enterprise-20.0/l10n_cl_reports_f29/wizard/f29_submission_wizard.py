from odoo import models, api, _


class F29SubmissionWizard(models.TransientModel):
    _name = 'l10n_cl_reports_f29.return.submission.wizard'
    _inherit = 'account.return.submission.wizard'
    _description = 'F29 Submission Wizard'

    @api.model
    def _open_submission_wizard(self, account_return, instructions=None):
        # EXTEND account_reports
        record_action = super()._open_submission_wizard(account_return, instructions)
        record_action['name'] = _("Submit F29 Return")
        return record_action

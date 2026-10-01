import json

from odoo import models


class L10nFIReportsTaxReportSubmissionWizard(models.TransientModel):
    _name = 'l10n_fi_reports.tax.report.submission.wizard'
    _inherit = 'account.return.submission.wizard'
    _description = "Tax Report Submission Wizard"

    def action_export_tax_report(self):
        options = self.return_id._get_closing_report_options()
        return {
            'type': 'ir_actions_account_report_download',
            'data': {
                'model': self.env.context.get('model'),
                'options': json.dumps(options),
                'file_generator': 'l10n_fi_export_tax_report',
                'no_closing_after_download': True,
            },
        }

    def action_proceed_with_submission(self):
        # EXTENDS account_reports
        self.return_id._mark_completed()
        super().action_proceed_with_submission()

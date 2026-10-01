import json

from odoo import models


class L10n_Sk_VatReturnSubmissionWizard(models.TransientModel):
    _name = 'l10n_sk_reports.vat.return.submission.wizard'
    _inherit = 'account.return.submission.wizard'
    _description = 'Slovak VAT Return Submission Wizard'

    def action_proceed_with_submission(self):
        # EXTENDS account_reports
        self.return_id.is_completed = True
        super().action_proceed_with_submission()

    def print_xml(self):
        options = self.return_id._get_closing_report_options()
        return {
            'type': 'ir_actions_account_report_download',
            'data': {
                'model': self.env.context.get('model'),
                'options': json.dumps(options),
                'file_generator': 'export_to_xml',
                'no_closing_after_download': True,
            },
        }

import json
from odoo import models


class L10n_cz_TaxReturnSubmissionWizard(models.TransientModel):
    _name = 'l10n_cz_reports.tax.return.submission.wizard'
    _description = 'Tax Return Submission Wizard'
    _inherit = 'account.return.submission.wizard'

    def action_proceed_with_submission(self):
        # Extends
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
            }
        }

import json
from odoo import models


class L10n_cz_VatControlStatementWizard(models.TransientModel):
    _name = 'l10n_cz_reports.vat.control.statement.wizard'
    _description = 'VAT Control Statement Wizard'
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
                'file_generator': 'l10n_cz_export_vat_control_report_to_xml',
                'no_closing_after_download': True,
            }
        }

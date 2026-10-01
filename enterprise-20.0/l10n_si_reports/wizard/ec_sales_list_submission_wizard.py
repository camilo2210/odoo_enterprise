import json

from odoo import models


class L10n_Si_ReportsEcSalesListSubmissionWizard(models.TransientModel):
    _name = 'l10n_si_reports.ec.sales.list.submission.wizard'
    _inherit = 'account.return.submission.wizard'
    _description = "EC Sales List Submission Wizard"

    def print_rpo_return(self):
        options = self.return_id._get_closing_report_options() or {}
        return {
            'type': 'ir_actions_account_report_download',
            'data': {
                'model': self.env.context.get('model'),
                'options': json.dumps(options),
                'file_generator': 'l10n_si_export_ec_sales_list_report_to_xml',
                'no_closing_after_download': True,
            },
        }

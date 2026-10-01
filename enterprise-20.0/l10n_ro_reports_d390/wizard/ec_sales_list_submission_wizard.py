import json

from odoo import models


class L10n_ro_ReportsEcSalesListSubmissionWizard(models.TransientModel):
    _name = 'l10n_ro_reports_d390.ec.sales.list.submission.wizard'
    _inherit = 'account.return.submission.wizard'
    _description = "Romanian EC Sales List Submission Wizard"

    def action_proceed_with_submission(self):
        self.return_id.is_completed = True
        super().action_proceed_with_submission()

    def print_xml(self):
        self.ensure_one()

        report_gen_options = self.return_id._get_closing_report_options()
        report_gen_options['return_id'] = self.return_id.id
        return {
            'type': 'ir_actions_account_report_download',
            'data': {
                'model': self.env.context.get('model'),
                'options': json.dumps(report_gen_options),
                'file_generator': 'export_to_xml_sales_report',
            },
        }

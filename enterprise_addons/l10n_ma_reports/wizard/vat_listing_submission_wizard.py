import json

from odoo import fields, models


class L10n_Ma_ReportsVatListingSubmissionWizard(models.TransientModel):
    _name = 'l10n_ma_reports.vat.listing.submission.wizard'
    _inherit = 'account.return.submission.wizard'
    _description = "Moroccan Vat Listing Submission Wizard"

    # Technical field holding XML generation errors meant for the actionable_errors widget.
    xml_generation_errors = fields.Json(compute='_compute_xml_generation_errors')
    has_critical_errors = fields.Boolean(compute='_compute_has_critical_errors')

    def _compute_xml_generation_errors(self):
        handler = self.env['l10n_ma.tax.report.handler']
        for wizard in self:
            options = wizard.return_id._get_closing_report_options()
            values = handler._l10n_ma_prepare_vat_report_values(options)
            wizard.xml_generation_errors = values.get('errors', {})

    def _compute_has_critical_errors(self):
        for wizard in self:
            wizard.has_critical_errors = any(
                err.get('level') == 'danger'
                for err in (wizard.xml_generation_errors or {}).values()
            )

    def action_proceed_with_submission(self):
        self.return_id.is_completed = True
        if not self.has_critical_errors:
            options = self.return_id._get_closing_report_options()
            options['skip_error_check'] = True
            self.return_id._add_attachment(self.env['l10n_ma.tax.report.handler'].l10n_ma_reports_export_vat_to_xml(options))
        super().action_proceed_with_submission()

    def print_xml(self):
        options = self.return_id._get_closing_report_options()
        options['skip_error_check'] = True
        return {
            'type': 'ir_actions_account_report_download',
            'data': {
                'model': self.env.context.get('model'),
                'options': json.dumps(options),
                'file_generator': 'l10n_ma_reports_export_vat_to_xml',
                'no_closing_after_download': True,
            }
        }

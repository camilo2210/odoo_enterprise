from odoo import fields, models
from odoo.addons.l10n_co_reports.models.l10n_co_exogenous_category import EXOGENOUS_REPORT_TYPES


class L10n_Co_ReportsExogenous_ReportWizard(models.TransientModel):
    _name = 'l10n_co_reports.exogenous_report.wizard'
    _description = 'Colombian Exogenous Report Wizard'

    exogenous_wizard_report_type = fields.Selection(
        string="Report",
        required=True,
        selection=EXOGENOUS_REPORT_TYPES,
    )

    def generate_csv(self):
        options = self.env.context.get('options')
        options['exogenous_report_type'] = self.exogenous_wizard_report_type
        report = self.env['account.report'].browse(options['report_id'])
        return report.export_file(options, 'l10n_co_reports_exogenous_report_csv_file_generator')

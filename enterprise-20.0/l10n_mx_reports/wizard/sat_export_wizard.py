from odoo import models, fields


class SATExportWizard(models.TransientModel):
    _name = 'l10n_mx_reports.sat.export.wizard'
    _description = "SAT Export Wizard"

    submit_type = fields.Selection(string="Submit Type", selection=[('N', 'Normal'), ('C', 'Supplementary')], default='N')

    def download_sat_action(self):
        options = self.env.context.get('l10n_mx_reports_report_options', {})
        report_id = self.env["account.report"].browse(options["report_id"])
        return report_id.export_file({**options, 'l10n_mx_reports_sat_wizard_id': self.id, 'submit_type': self.submit_type}, 'action_l10n_mx_generate_sat_xml')

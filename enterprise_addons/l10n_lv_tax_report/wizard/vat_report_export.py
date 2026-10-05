import json

from odoo import models, fields


class AccountFinancialReportXMLReportExport(models.TransientModel):
    _name = "l10n_lv_tax_report.periodic.vat.xml.export"
    _description = "Latvian Periodic VAT Report Export Wizard"

    clarification = fields.Boolean(
        help="Enable this option in case the report has already been submitted previously. The new export is going to be an update.",
    )

    def _l10n_lv_tax_report_vat_export_generate_options(self):
        return {'clarification': self.clarification}

    def print_xml(self):
        options = {
            **self.env.context.get('l10n_lv_tax_report_generation_options'),
            **self._l10n_lv_tax_report_vat_export_generate_options(),
        }
        return {
            'type': 'ir_actions_account_report_download',
            'data': {
                'model': self.env.context.get('model'),
                'options': json.dumps(options),
                'file_generator': 'export_tax_report_to_xml',
            }
        }

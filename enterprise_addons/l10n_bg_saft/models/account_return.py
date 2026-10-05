import re
from odoo import models
from odoo.addons.account_reports.models.account_report import AccountReportFileDownloadException
from odoo.tools import BinaryBytes


class AccountReturn(models.Model):
    _inherit = 'account.return'

    def _attach_purchase_and_sale_txt_reports(self, options):
        tax_report = self.env.ref('l10n_bg.l10n_bg_tax_report')
        tax_report_handler = self.env[tax_report.custom_handler_model_name]
        tax_report_options = tax_report.get_options(previous_options=options)

        POKUPKI_txt_file = tax_report_handler.export_purchase_report_to_txt(tax_report_options)
        PRODAGBI_txt_file = tax_report_handler.export_sale_report_to_txt(tax_report_options)
        self._add_attachment(POKUPKI_txt_file)
        self._add_attachment(PRODAGBI_txt_file)

    def add_attachments_and_validate(self, content, file_name, options):
        # Allow the l10n_bg_saft_file_attachment_error_wizard to continue the validation process
        self._add_attachment({
            'file_content': content,
            'file_name': file_name,
        })
        self._attach_purchase_and_sale_txt_reports(options)
        return super().action_validate()

    def action_validate(self):
        # Extends account_reports

        self.ensure_one()

        if self.type_external_id != 'l10n_bg_reports.bg_tax_return_type':
            return super().action_validate()

        options = {**self._get_closing_report_options(), 'export_mode': 'file'}
        report = self.env.ref('account_reports.general_ledger_report')
        customer_handler = self.env[report.custom_handler_model_name]

        try:
            saft_attachment = customer_handler.l10n_bg_export_saft_to_xml(
                report.get_options(previous_options=options),
            )
            self._add_attachment(saft_attachment)
            self._attach_purchase_and_sale_txt_reports(options)
            return super().action_validate()

        except AccountReportFileDownloadException as e:
            if e.content:
                e.content['file_content'] = e.content['file_content'].decode()
            return self.open_l10n_bg_saft_file_attachment_error_wizard(
                e.errors,
                e.content,
                options,
            )

    def open_l10n_bg_saft_file_attachment_error_wizard(self, errors, content, options):
        self.ensure_one()

        model = 'l10n_bg_saft.file.attachment.error.wizard'
        vals = {'actionable_errors': errors}

        if content:
            vals['file_name'] = content['file_name']
            vals['file_content'] = BinaryBytes(re.sub(r'\n\s*\n', '\n', content['file_content']).encode())
            vals['account_return_id'] = self.id
            vals['options'] = options

        return {
            'name': 'Bulgarian SAF-T file errors',
            'type': 'ir.actions.act_window',
            'res_model': model,
            'res_id': self.env[model].create(vals).id,
            'target': 'new',
            'views': [(False, 'form')],
        }

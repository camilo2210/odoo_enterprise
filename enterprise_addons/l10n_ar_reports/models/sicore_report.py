# Part of Odoo. See LICENSE file for full copyright and licensing details.
import re

from odoo import fields, models, _
from odoo.exceptions import UserError, RedirectWarning


class L10n_ArSicoreReportHandler(models.AbstractModel):
    _name = 'l10n_ar.sicore.report.handler'
    _inherit = ['account.tax.report.handler']
    _description = 'Argentinian SICORE Report Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)

        # Add export button
        txt_export_button = {
            'name': _('Sicore Profits Withholdings TXT'),
            'sequence': 30,
            'action': 'export_file',
            'action_param': 'sicore_book_export_files_to_txt',
            'file_export_type': 'TXT',
        }

        options['buttons'].append(txt_export_button)

    def sicore_book_export_files_to_txt(self, options):
        """ Export method that lets us export the SICORE book to a txt file.
        It contains the file that we upload to SICORE application. """
        return {
            'file_name': _('SICORE_profits_withholdings.txt'),
            'file_content': self._sicore_book_get_txt_files(options),
            'file_type': 'txt',
        }

    def _sicore_book_get_txt_files(self, options):
        """Returns SICORE txt content"""
        move_lines = self._sicore_book_get_txt_lines(options)
        return ''.join(self._get_sicore_txt_content(move_lines)).encode('ISO-8859-1', 'ignore')

    def _sicore_book_get_txt_lines(self, options):
        """Returns account move lines to be printed"""
        state = options.get('all_entries') and 'all' or 'posted'
        if state != 'posted':
            raise UserError(_('Can only generate TXT files using posted entries.'
                              ' Please remove Include unposted entries filter and try again'))
        report = self.env['account.report'].browse(options['report_id'])
        move_line_ids = []
        for line_data in report._get_lines(options):
            model, record_id = report._get_model_info_from_id(line_data.id)
            if model == 'account.move.line':
                move_line_ids.append(record_id)
        return self.env['account.move.line'].browse(move_line_ids)

    def _get_sicore_txt_content(self, move_lines):
        """ Returns the lines to be printed in the txt file. """
        lines = []
        for line in move_lines.filtered('balance').sorted(key=lambda r: (r.date, r.id)):
            content = ''

            partner = line.partner_id
            partner_doc_number = partner.l10n_ar_afip_id_value
            partner_afip_code = partner.l10n_ar_afip_code
            if not partner_doc_number or not partner_afip_code:
                raise RedirectWarning(
                    _(
                        '%(partner_name)s must have an Identification Number set.',
                        partner_name=partner.display_name
                    ),
                    partner.get_record_default_action(),
                    _('Go to the partner'),
                )

            payment = line.payment_id
            move = line.move_id

            # Codigo del Comprobante (document code)         [ 2]
            content += "06"  # Only outbound payments

            # Fecha Emision Comprobante (move line date)     [10] (dd/mm/yyyy)
            content += fields.Date.from_string(line.date).strftime("%d/%m/%Y")

            # Numero Comprobante (document number)           [16]
            content += f"{re.sub(r'[^0-9]', '', move.l10n_latam_document_number or ''):0>16}"

            # Importe Comprobante (document amount)          [16]
            content += f"{-payment.amount_company_currency_signed:016.2f}"

            # Codigo de Impuesto (tax code)                  [ 4]
            content += "0217"

            # Codigo de Regimen (regime code)                [ 3]
            regimen = line.tax_line_id.l10n_ar_code
            content += f"{''.join(filter(str.isdigit, str(regimen))):0>3}" if regimen else "000"

            # Codigo de Operacion (operation code)           [ 1]
            content += "1"

            # Base de Calculo (base amount)                  [14]
            content += f"{-line.tax_base_amount:014.2f}"

            # Fecha Emision Retencion (move line date)       [10] (dd/mm/yyyy)
            issue_date = fields.Date.from_string(payment.date).strftime("%d/%m/%Y")
            content += issue_date

            # Codigo de Condicion (condition code)           [ 2]
            content += "01"

            # Retención Pract. a Suj. ..                     [ 1]
            content += "0"

            # Importe de Retencion (withholding amount)      [14]
            content += f"{-line.balance:014.2f}"

            # Porcentaje de Exclusion (exclusion percentage) [ 6]
            content += "000.00"

            # Fecha Emision Boletin                          [10] (dd/mm/yyyy)
            content += issue_date

            # Tipo Documento Retenido (document type code)   [ 2]
            content += f"{int(partner_afip_code):02d}"

            # Numero Documento Retenido (vat)                [20]
            content += partner_doc_number.ljust(20)

            # Numero Certificado Original                    [14]
            content += f"{0:014d}"

            content += "\r\n"

            lines.append(content)

        return lines

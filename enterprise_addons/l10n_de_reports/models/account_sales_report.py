# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import math
import tempfile
import zipfile

from odoo import _, api, models
from odoo.tools.float_utils import float_round


class L10n_DeEcSalesReportHandler(models.AbstractModel):
    _name = 'l10n_de.ec.sales.report.handler'
    _inherit = ['account.ec.sales.with.tags.report.handler']
    _description = 'German EC Sales Report Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        de_tax_tags = self._get_ec_sales_tax_tags()
        options['sales_report_operation_types'] = {
            'goods': {
                'tax_tag_ids': de_tax_tags['goods'],
                'name': self.env._('Goods'),
                'shortcut': 'L',
            },
            'services': {
                'tax_tag_ids': de_tax_tags['services'],
                'name': self.env._('Services'),
                'shortcut': 'S',
            },
            'triangular': {
                'tax_tag_ids': de_tax_tags['triangular'],
                'name': self.env._('Triangular'),
                'shortcut': 'D',
            },
        }
        super()._custom_options_initializer(report, options, previous_options)

        options.setdefault('buttons', []).append({
            'name': _('CSV'),
            'sequence': 30,
            'action': 'export_file',
            'action_param': 'print_de_csvs_zip',
            'file_export_type': _('ZIP')
        })

    @api.model
    def get_csvs(self, report, options):
        lines = [
            tuple(column.no_format for column in line.columns)
            for line in report._get_lines(options)
            if isinstance((markup := report._get_markup(line.id)), dict)
            and markup.get('groupby', '') == 'partner_id_and_sale_type'
        ]

        line_chunks = []
        chunks = [lines[i * 1000:(i + 1) * 1000] for i in range(math.ceil(len(lines) / 1000))]
        for chunk in chunks:
            # version strings and headers
            content = '#v3.0\n#ve3.2.1\n'
            content += 'Umsatzsteuer-Identifikationsnummer (USt-IdNr.),Betrag (Euro),Art der Leistung\n'
            for vat_country_code, vat_number, service_type, amount, *vals in chunk:
                full_vat_number = f'{vat_country_code}{vat_number}' if vat_country_code and vat_number else ''
                content += f'{full_vat_number},{int(float_round(amount, 0))},{service_type}\n'
            line_chunks.append(content)
        return line_chunks

    def print_de_csvs_zip(self, options):
        report = self.env['account.report'].browse(options['report_id'])
        csvs = self.get_csvs(report, options)
        with tempfile.NamedTemporaryFile() as buf:
            with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED, allowZip64=False) as zip_buffer:
                for i, csv in enumerate(csvs):
                    zip_buffer.writestr('EC_Sales_list%s.csv' % (len(csvs) > 1 and ("_" + str(i+1)) or ""), csv)
            buf.seek(0)
            res = buf.read()
        return {
            'file_name': report.get_default_report_filename(options, 'ZIP'),
            'file_content': res,
            'file_type': 'zip'
        }

    def _get_ec_sales_tax_tags(self):
        return {
            'goods': tuple(self.env.ref('l10n_de.tax_report_de_tag_41_tag')._get_matching_tags().ids),
            'triangular': tuple(self.env.ref('l10n_de.tax_report_de_tag_42_tag')._get_matching_tags().ids),
            'services': tuple(self.env.ref('l10n_de.tax_report_de_tag_21_tag')._get_matching_tags().ids),
        }

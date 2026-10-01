# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import csv
import io
from odoo import _, api, fields, models
from odoo.tools import date_utils


class L10n_SeEcSalesReportHandler(models.AbstractModel):
    _name = 'l10n_se.ec.sales.report.handler'
    _inherit = ['account.ec.sales.with.tags.report.handler']
    _description = 'Swedish EC Sales Report Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        se_tax_tags = self._get_ec_sales_tax_tags()
        options.update({
            'sales_report_operation_types': {
                'goods': {
                    'tax_tag_ids': se_tax_tags['goods'],
                },
                'services': {
                    'tax_tag_ids': se_tax_tags['services'],
                },
                'triangular': {
                    'tax_tag_ids': se_tax_tags['triangular'],
                },
            },
        })
        super()._custom_options_initializer(report, options, previous_options)

        # Buttons
        options.setdefault('buttons', []).append({
            'name': _('KVR'),
            'sequence': 60,
            'action': 'export_file',
            'action_param': 'export_sales_report_to_kvr',
            'file_export_type': _('KVR'),
            'active': report.country_id.code in ('SE', None),
        })

    def _get_ec_sales_tax_tags(self):
        # Overrides account_reports
        goods_expression = self.env.ref('l10n_se.tax_report_line_35_tag')
        services_expression = self.env.ref('l10n_se.tax_report_line_39_tag')
        triangular_expression = self.env.ref('l10n_se.tax_report_line_38_tag')

        return {
            'goods': goods_expression._get_matching_tags().ids,
            'services': services_expression._get_matching_tags().ids,
            'triangular': triangular_expression._get_matching_tags().ids,
        }

    def _format_vat_number(self, full_vat_number):
        # Override super function to not trim country code from vat number
        return full_vat_number

    @api.model
    def _get_se_period(self, options):
        """
        Ensures that the period is in the correct format for the exporting format.
        """
        date_to = fields.Date.from_string(options['date'].get('date_to'))
        if options['date']['period_type'] == 'month':
            return date_to.strftime('%y%m')
        elif options['date']['period_type'] == 'quarter':
            return '%s-%s' % (date_to.strftime('%y'), date_utils.get_quarter_number(date_to))
        else:
            return '%s-to-%s' % (options['date']['date_from'], options['date']['date_to'])

    def export_sales_report_to_kvr(self, options):
        """
        Collect the data for the KVR report.
        """
        options['get_file_data'] = True
        lines = [
            ['SKV574008'],
            [
                self.env.company.vat,
                self._get_se_period(options),
                self.env.user.name,
                self.env.user.phone or '',
                self.env.user.email or '',
                ''
            ],
        ]
        report = self.env['account.report'].browse(options['report_id'])

        for data_line in report._get_lines(options):
            if report._get_model_info_from_id(data_line.id)[0] != 'res.partner':
                continue

            columns = []
            for column in data_line.columns:
                if isinstance(column.no_format, str):
                    columns.append(column.no_format or '')
                elif isinstance(column.no_format, (int, float)):
                    value = round(column.no_format or 0)
                    columns.append(value if value else '')
                else:
                    columns.append('')
            lines.append(columns)
        with io.StringIO() as buf:
            writer = csv.writer(buf, delimiter=';')
            writer.writerows(lines)
            content = buf.getvalue().encode()
        return {
            'file_name': report.get_default_report_filename(options, 'KVR'),
            'file_content': content,
            'file_type': 'csv',  # KVR is just csv with extra steps
        }

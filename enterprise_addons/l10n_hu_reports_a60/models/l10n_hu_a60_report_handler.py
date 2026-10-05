import re
from itertools import batched
from lxml import etree

from odoo import models
from odoo.tools.xml_utils import cleanup_xml_node

TAB_LETTER = {
    '0': 'A',
    '1': 'B',
    '2': 'C',
    '3': 'D',
    '4': 'E',
}

COLUMN_LETTER_MAP = {
    '1': {
        'country_code': 'A',
        'vat_number': 'B',
        'balance': 'C',
        'sale_type_shortcut': 'D',
        'operation_code': 'E',
    },
    '2': {
        'country_code': 'A',
        'vat_number': 'B',
        'balance': 'C',
        'sale_type_shortcut': 'D',
        'operation_code': 'E',
    },
    '3': {
        'country_code': 'A',
        'vat_number': 'B',
        'balance': 'C',
        'operation_code': 'D',
    },
    '4': {
        'country_code': 'A',
        'vat_number': 'B',
        'balance': 'C',
        'operation_code': 'D',
    },
}


class L10nHua60ReportHandler(models.AbstractModel):
    _name = 'l10n_hu_reports_a60.a60.report.handler'
    _inherit = ['account.ec.sales.with.tags.report.handler']
    _description = 'a60 Report Handler'

    def _get_ec_sales_tax_tags(self):
        # OVERRIDES account_reports
        return {
            'goods': [],
            'services': [],
            'triangular_a60b': [],
            'triangular_a60k': [],
            'triangular_a60r': [],
            'triangular_a60c': [],
            'triangular_a60v': [],
        }

    def _custom_options_initializer(self, report, options, previous_options):
        # EXTENDS account_reports
        hu_tax_tags_ids = self._get_ec_sales_tax_tags()
        options.update({
            'sales_report_operation_types': {
                'goods': {
                    'tax_tag_ids': hu_tax_tags_ids['goods'],
                    'name': self.env._('Goods'),
                    'shortcut': '',
                },
                'services': {
                    'tax_tag_ids': hu_tax_tags_ids['services'],
                    'name': self.env._('Services'),
                    'shortcut': '',
                },
                'triangular_a60b': {
                    'tax_tag_ids': hu_tax_tags_ids['triangular_a60b'],
                    'name': self.env._('A60B'),
                    'shortcut': 'B',
                },
                'triangular_a60k': {
                    'tax_tag_ids': hu_tax_tags_ids['triangular_a60k'],
                    'name': self.env._('A60K'),
                    'shortcut': 'K',
                },
                'triangular_a60r': {
                    'tax_tag_ids': hu_tax_tags_ids['triangular_a60r'],
                    'name': self.env._('A60R'),
                    'shortcut': 'R',
                },
                'triangular_a60c': {
                    'tax_tag_ids': hu_tax_tags_ids['triangular_a60c'],
                    'name': self.env._('A60C'),
                    'shortcut': 'C',
                },
                'triangular_a60v': {
                    'tax_tag_ids': hu_tax_tags_ids['triangular_a60v'],
                    'name': self.env._('A60V'),
                    'shortcut': 'V',
                },
            },
        })

        super()._custom_options_initializer(report, options, previous_options)

    def export_to_xml(self, options):
        def generate_eazon_node(value, tab, page, line_number, block, column=''):
            tab_letter = TAB_LETTER[tab]
            code = f'0{tab_letter}{page:04d}{block}{line_number}{column}A'
            nodes_values.append({'code': code, 'value': value})

        report = self.env['account.report'].browse(options['report_id'])
        account_return = self.env['account.return'].browse(self.env.context.get('active_id')).exists()
        assert account_return, "You must specify an account return."

        print_options = report.get_options(previous_options={**options, 'export_mode': 'print'})
        print_options_date = print_options['date']
        reports_to_print = self.env['account.report'].browse([section['id'] for section in print_options['sections']])
        report_lines = {}
        for section_report in reports_to_print:
            report_options = section_report.get_options(previous_options={**print_options, 'selected_section_id': section_report.id, 'export_mode': 'print'})
            section_report_lines = section_report._get_lines(report_options)
            lines = []
            for index, line in enumerate(section_report_lines[1:], start=1):
                columns_value = {column['expression_label']: column['no_format'] for column in line.columns}
                columns_value.update({
                    'index': index,
                    'operation_code': 'U' if columns_value['balance'] > 0 else 'T',
                    'balance': int(columns_value['balance']),
                })
                lines.append(columns_value)
            report_lines[section_report] = lines

        escaped_vat_number = re.sub(r'[a-zA-Z]', '', self.env.company.vat)
        date_from = re.sub(r'[^0-9]', '', print_options_date['date_from'])
        date_to = re.sub(r'[^0-9]', '', print_options_date['date_to'])
        nodes_values = []

        # Depending on the VAT format, we need either 10 digits number or 8 digits
        if len(escaped_vat_number) == 10:
            generate_eazon_node(escaped_vat_number, '0', 1, '001', 'C')
        else:
            generate_eazon_node(escaped_vat_number.split('-')[0], '0', 1, '003', 'C')

        # Fill in with the info from the validation wizard
        generate_eazon_node(account_return.l10n_hu_reports_a60_last_name, '0', 1, '006', 'C')
        generate_eazon_node(account_return.l10n_hu_reports_a60_first_name, '0', 1, '007', 'C')
        generate_eazon_node(self.env.company.name, '0', 1, '008', 'C')
        generate_eazon_node(account_return.l10n_hu_reports_a60_contact_person, '0', 1, '009', 'C')
        generate_eazon_node(account_return.l10n_hu_reports_a60_phone_number, '0', 1, '010', 'C')

        generate_eazon_node(date_from, '0', 1, '001', 'D')
        generate_eazon_node(date_to, '0', 1, '002', 'D')
        for report, lines in report_lines.items():
            tab = re.search(r'page([1-4])', report.custom_handler_model_name).group(1)
            for batch_index, batch_line in enumerate(batched(lines, 24), start=1):
                batch_total = 0
                generate_eazon_node(batch_index, tab, batch_index, '001', 'B')
                for line_index, line in enumerate(batch_line, start=1):
                    batch_total += line['balance']
                    for key, column in COLUMN_LETTER_MAP[tab].items():
                        if line.get(key):
                            generate_eazon_node(line[key], tab, batch_index, f'{line_index:04d}', 'C', column)

                generate_eazon_node(batch_total, tab, batch_index, '0025', 'C', 'C')

        xml_file = self.env['ir.qweb']._render('l10n_hu_reports_a60.l10n_hu_a60_export_file', {
            'company': self.env.company,
            'escaped_vat_number': escaped_vat_number,
            'date_from': re.sub(r'[^0-9]', '', print_options_date['date_from']),
            'date_to': re.sub(r'[^0-9]', '', print_options_date['date_to']),
            'nodes_values': nodes_values,
        })
        xml_file = cleanup_xml_node(xml_file)

        return {
            'file_name': report.get_default_report_filename(options, 'xml'),
            'file_content': etree.tostring(xml_file, encoding='utf-8', pretty_print=True, xml_declaration=True),
            'file_type': 'xml',
        }


class L10nHua60ReportHandlerPage1(models.AbstractModel):
    _name = 'l10n_hu_reports_a60.a60.page1.report.handler'
    _inherit = 'l10n_hu_reports_a60.a60.report.handler'
    _description = 'a60 page 1 Report Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        # EXTENDS account_reports
        super()._custom_options_initializer(report, options, previous_options)
        options.setdefault('forced_domain', []).extend([
            ('move_id.move_type', 'in', ('out_invoice', 'out_refund')),
            '|',
            ('product_id.type', '=', 'consu'),
            ('product_id', '=', False),
        ])

    def _get_ec_sales_tax_tags(self):
        # OVERRIDES account_reports
        tax_tags = super()._get_ec_sales_tax_tags()
        tax_tags.update({
            'goods': self.env.ref('l10n_hu.a60s_goods_balance')._get_matching_tags().ids,
            'triangular_a60b': self.env.ref('l10n_hu.a60b_balance')._get_matching_tags().ids,
            'triangular_a60k': self.env.ref('l10n_hu.a60k_balance')._get_matching_tags().ids,
            'triangular_a60r': self.env.ref('l10n_hu.a60r_balance')._get_matching_tags().ids,
            'triangular_a60c': self.env.ref('l10n_hu.a60c_balance')._get_matching_tags().ids,
            'triangular_a60v': self.env.ref('l10n_hu.a60v_balance')._get_matching_tags().ids,
        })
        return tax_tags


class L10nHua60ReportHandlerPage2(models.AbstractModel):
    _name = 'l10n_hu_reports_a60.a60.page2.report.handler'
    _inherit = 'l10n_hu_reports_a60.a60.report.handler'
    _description = 'a60 page 2 Report Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        # EXTENDS account_reports
        super()._custom_options_initializer(report, options, previous_options)
        options.setdefault('forced_domain', []).extend([
            ('move_id.move_type', 'in', ('in_invoice', 'in_refund')),
            '|',
            ('product_id.type', '=', 'consu'),
            ('product_id', '=', False),
        ])

    def _get_ec_sales_tax_tags(self):
        # OVERRIDES account_reports
        tax_tags = super()._get_ec_sales_tax_tags()
        tax_tags.update({
            'goods': self.env.ref('l10n_hu.a60p_goods_balance')._get_matching_tags().ids,
            'triangular_a60b': self.env.ref('l10n_hu.a60b_rec_balance')._get_matching_tags().ids,
            'triangular_a60k': self.env.ref('l10n_hu.a60k_rec_balance')._get_matching_tags().ids,
            'triangular_a60r': self.env.ref('l10n_hu.a60r_rec_balance')._get_matching_tags().ids,
            'triangular_a60c': self.env.ref('l10n_hu.a60c_rec_balance')._get_matching_tags().ids,
            'triangular_a60v': self.env.ref('l10n_hu.a60v_rec_balance')._get_matching_tags().ids,
        })
        return tax_tags

    def _custom_line_postprocessor(self, report, options, lines):
        # OVERRIDE account_reports
        for line in lines:
            for column in line.columns:
                if column.expression_label == 'balance':
                    column.no_format = -column.no_format
        return lines


class L10nHua60ReportHandlerPage3(models.AbstractModel):
    _name = 'l10n_hu_reports_a60.a60.page3.report.handler'
    _inherit = 'l10n_hu_reports_a60.a60.report.handler'
    _description = 'a60 page 3 Report Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        # EXTENDS account_reports
        super()._custom_options_initializer(report, options, previous_options)
        options.setdefault('forced_domain', []).extend([
            ('move_id.move_type', 'in', ('out_invoice', 'out_refund')),
            '|',
            ('product_id.type', '=', 'service'),
            ('product_id', '=', False),
        ])

    def _get_ec_sales_tax_tags(self):
        # OVERRIDES account_reports
        tax_tags = super()._get_ec_sales_tax_tags()
        tax_tags.update({
            'services': self.env.ref('l10n_hu.a60s_services_balance')._get_matching_tags().ids,
        })
        return tax_tags


class L10nHua60ReportHandlerPage4(models.AbstractModel):
    _name = 'l10n_hu_reports_a60.a60.page4.report.handler'
    _inherit = 'l10n_hu_reports_a60.a60.report.handler'
    _description = 'a60 page 4 Report Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        # EXTENDS account_reports
        super()._custom_options_initializer(report, options, previous_options)
        options.setdefault('forced_domain', []).extend([
            ('move_id.move_type', 'in', ('in_invoice', 'in_refund')),
            '|',
            ('product_id.type', '=', 'service'),
            ('product_id', '=', False),
        ])

    def _get_ec_sales_tax_tags(self):
        # OVERRIDES account_reports
        tax_tags = super()._get_ec_sales_tax_tags()
        tax_tags.update({
            'services': self.env.ref('l10n_hu.a60p_services_balance')._get_matching_tags().ids,
        })
        return tax_tags

    def _custom_line_postprocessor(self, report, options, lines):
        # OVERRIDE account_reports
        for line in lines:
            for column in line.columns:
                if column.expression_label == 'balance':
                    column.no_format = -column.no_format
        return lines

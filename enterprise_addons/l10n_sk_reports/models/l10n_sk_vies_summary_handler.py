from lxml import etree
from stdnum.sk import vat as sk_vat

from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools import date_utils, float_round
from odoo.tools.xml_utils import cleanup_xml_node

# Number of records per page in the XML export, required by the XSD schema.
RECORDS_PER_PAGE = 12


class SlovakVIESSummaryReportCustomHandler(models.AbstractModel):
    """
        Generate the VIES Summary Statement (Súhrnný výkaz DPH) for Slovakia.
        Reference: https://www.financnasprava.sk/sk/podnikatelia/dane/dan-z-pridanej-hodnoty/suhrnny-vykaz-dph
    """
    _name = 'l10n_sk.vies.summary.report.handler'
    _inherit = 'account.ec.sales.with.tags.report.handler'
    _description = 'Slovak Report Custom Handler (VIES Summary)'

    def _custom_options_initializer(self, report, options, previous_options=None):
        sk_tax_tags = self._get_ec_sales_tax_tags()
        options['sales_report_operation_types'] = {
            'goods': {
                'tax_tag_ids': sk_tax_tags['goods'],
                'name': self.env._('Goods'),
                'shortcut': '0',
            },
            'services': {
                'tax_tag_ids': sk_tax_tags['services'],
                'name': self.env._('Services'),
                'shortcut': '1',
            },
            'triangular': {
                'tax_tag_ids': sk_tax_tags['triangular'],
                'name': self.env._('Triangular'),
                'shortcut': '2',
            },
        }
        super()._custom_options_initializer(report, options, previous_options=previous_options)

        options.setdefault('buttons', []).append({
            'name': self.env._('XML'),
            'sequence': 30,
            'action': 'export_file',
            'action_param': 'export_to_xml',
            'file_export_type': self.env._('XML'),
        })

    def _get_ec_sales_tax_tags(self):
        # Overrides account_reports
        return {
            'goods': tuple(self.env.ref('l10n_sk.sk_vat_exempt_14_goods_base')._get_matching_tags().ids),
            'services': tuple(self.env.ref('l10n_sk.sk_vat_exempt_14_services_base')._get_matching_tags().ids),
            'triangular': tuple(self.env.ref('l10n_sk.sk_vat_exempt_14_triangular_base')._get_matching_tags().ids),
        }

    ####################################################
    # XML EXPORT
    ####################################################

    def export_to_xml(self, options):
        report = self.env['account.report'].browse(options['report_id'])
        sender_company = report._get_sender_company_for_export(options)

        if not sender_company.vat:
            raise UserError(self.env._("Please set the company VAT number before exporting."))

        report_options = {**options, 'export_mode': 'file'}
        report_lines = report._get_lines({**report_options})

        lines = []
        for report_line in report_lines:
            markup = report._get_markup(report_line.id)
            if not isinstance(markup, dict) or markup.get('groupby') != 'partner_id_and_sale_type':
                continue

            column_values = {
                col.expression_label: col.no_format
                for col in report_line.columns
            }

            shortcut = column_values.get('sale_type_shortcut') or ''
            lines.append({
                'country_code': column_values.get('country_code') or '',
                'vat_number': column_values.get('vat_number') or '',
                'total_value': int(float_round(column_values.get('balance') or 0, precision_digits=0)),
                # goods transaction code '0' must be exported as empty, as required by the XSD
                'transaction_code': '' if shortcut == '0' else shortcut,
            })

        # Build paginated body data (12 records per page, as required by the XSD)
        pages = []
        for i in range(0, max(len(lines), 1), RECORDS_PER_PAGE):
            page_lines = lines[i:i + RECORDS_PER_PAGE]
            # Pad to exactly 12 records
            page_lines += [{}] * (RECORDS_PER_PAGE - len(page_lines))
            pages.append(page_lines)

        total_value = sum(line.get('total_value', 0) for line in lines)

        data = {
            'header': self._get_header_values(sender_company, options, total_value),
            'pages': pages,
        }

        xml_content = self.env['ir.qweb']._render('l10n_sk_reports.vies_summary_export_template', values=data)
        tree = etree.fromstring(xml_content)
        cleanup_xml_node(tree, remove_blank_nodes=False)
        formatted_xml = etree.tostring(tree, pretty_print=True, xml_declaration=True, encoding='UTF-8')

        return {
            'file_name': report.get_default_report_filename(options, 'xml'),
            'file_content': formatted_xml,
            'file_type': 'xml',
        }

    def _get_header_values(self, company, options, total_value):
        """ Build header values for the XML export, following the XSD structure. """
        partner = company.partner_id
        date_from = fields.Date.to_date(options['date']['date_from'])
        date_to = fields.Date.to_date(options['date']['date_to'])
        today = fields.Date.context_today(self)

        # Split company name into up to 4 lines as required by the XSD
        name_lines = [line for line in company.name.splitlines() if line.strip()][:4]
        name_lines += [''] * (4 - len(name_lines))

        period_values = self._compute_tax_period(date_from, date_to)
        return {
            'kod_statu': 'SK',
            'dic': sk_vat.compact(company.vat or ''),  # Extract numeric part of VAT (remove country prefix)
            'danovy_urad': '',
            'riadny': '1',
            'opravny': '0',
            'dodatocny': '0',
            **period_values,
            'obchodne_meno': name_lines,
            'ulica': partner.street or '',
            'cislo': partner.street2 or '',
            'psc': partner.zip or '',
            'obec': partner.city or '',
            'tel': partner.phone or '',
            'email': partner.email or '',
            'celkova_hodnota': str(total_value) if total_value else '',
            'konatel': '',
            'konatel_tel': '',
            'konatel_email': '',
            'datum_den': str(today.day),
            'datum_mesiac': str(today.month),
            'datum_rok': str(today.year),
        }

    def _compute_tax_period(self, date_from, date_to):
        """ Compute the period (month or quarter) for the VIES statement. """
        mesiac = ''
        stvrtrok = ''
        quarter_start, quarter_end = date_utils.get_quarter(date_from)

        if date_from.year == date_to.year and date_from.month == date_to.month:
            mesiac = str(date_to.month)
        elif date_from == quarter_start and date_to == quarter_end:
            stvrtrok = str(date_utils.get_quarter_number(date_to))

        return {
            'mesiac': mesiac,
            'stvrtrok': stvrtrok,
            'rok': str(date_to.year),
        }

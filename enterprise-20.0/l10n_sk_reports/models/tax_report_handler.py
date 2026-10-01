from datetime import date

from lxml import etree
from stdnum.sk import vat as sk_vat

from odoo import fields, models
from odoo.tools import date_utils, float_round
from odoo.tools.business_data import street_split


class SlovakTaxReportCustomHandler(models.AbstractModel):
    """
        Generate the VAT report for the Slovakia.
        Generated using as a reference the documentation at
        https://www.financnasprava.sk/sk/podnikatelia/dane/dan-z-pridanej-hodnoty/danove-priznanie
    """
    _name = 'l10n_sk.tax.report.handler'
    _inherit = 'account.tax.report.handler'
    _description = 'Slovak Tax Report Custom Handler'

    _BODY_FIELD_MAP = [
        ('r01', 'sk_01', 'base'), ('r01a', 'sk_01a', 'base'),
        ('r02', 'sk_01', 'vat'), ('r02a', 'sk_01a', 'vat'),
        ('r03', 'sk_03', 'base'), ('r04', 'sk_03', 'vat'),
        ('r05', 'sk_05', 'base'), ('r05a', 'sk_05a', 'base'),
        ('r06', 'sk_05', 'vat'), ('r06a', 'sk_05a', 'vat'),
        ('r07', 'sk_07', 'base'), ('r08', 'sk_07', 'vat'),
        ('r09', 'sk_09', 'base'), ('r09a', 'sk_09a', 'base'), ('r09b', 'sk_09b', 'base'),
        ('r10', 'sk_09', 'vat'), ('r10a', 'sk_09a', 'vat'), ('r10b', 'sk_09b', 'vat'),
        ('r11', 'sk_11', 'base'), ('r11a', 'sk_11a', 'base'), ('r11b', 'sk_11b', 'base'),
        ('r11c', 'sk_11c', 'base'), ('r11d', 'sk_11d', 'base'), ('r11e', 'sk_11e', 'base'),
        ('r12', 'sk_11', 'vat'), ('r12a', 'sk_11a', 'vat'), ('r12b', 'sk_11b', 'vat'),
        ('r12c', 'sk_11c', 'vat'), ('r12d', 'sk_11d', 'vat'), ('r12e', 'sk_11e', 'vat'),
        ('r13', 'sk_13', 'base'), ('r14', 'sk_14', 'base'), ('r15', 'sk_15', 'base'),
        ('r16', 'sk_16', 'vat'), ('r17', 'sk_17', 'vat'),
        ('r18', 'sk_18_total', 'vat'), ('r18a', 'sk_18a_total', 'vat'), ('r19', 'sk_19_total', 'vat'),
        ('r20', 'sk_20', 'vat'), ('r20a', 'sk_20a', 'vat'), ('r21', 'sk_21', 'vat'),
        ('r22', 'sk_22', 'vat'), ('r22a', 'sk_22a', 'vat'), ('r23', 'sk_23', 'vat'),
        ('r23a', 'sk_23a', 'vat'), ('r23b', 'sk_23b', 'vat'), ('r23c', 'sk_23c', 'vat'),
        ('r24', 'sk_24', 'base'), ('r25', 'sk_24', 'vat'),
        ('r26', 'sk_26', 'base'), ('r27', 'sk_26', 'vat'),
        ('r28', 'sk_28', 'vat'), ('r29', 'sk_29', 'vat'),
        ('r30', 'sk_30', 'vat'), ('r31', 'sk_31', 'vat'),
        ('r32', 'sk_32', 'vat'),
        ('r33', 'sk_33', 'vat'), ('r34', 'sk_34', 'vat'), ('r35', 'sk_35', 'vat'),
        ('r36', 'sk_36', 'vat'), ('r37', 'sk_37', 'vat'),
    ]

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)

        options.setdefault('buttons', []).append({
            'name': self.env._('XML'),
            'sequence': 30,
            'action': 'export_file',
            'action_param': 'export_to_xml',
            'file_export_type': self.env._('XML'),
        })

    def export_to_xml(self, options):
        report = self.env['account.report'].browse(options['report_id'])
        sender_company = report._get_sender_company_for_export(options)

        data = {
            'xml_values': self._l10n_sk_get_xml_values(report, options, sender_company),
        }

        xml_content = self.env['ir.qweb']._render('l10n_sk_reports.sk_vat_report_template', values=data)
        tree = etree.fromstring(xml_content)
        formatted_xml = etree.tostring(tree, pretty_print=True, xml_declaration=True, encoding='UTF-8')

        return {
            'file_name': report.get_default_report_filename(options, 'xml'),
            'file_content': formatted_xml,
            'file_type': 'xml',
        }

    def _l10n_sk_get_report_line_values(self, report, options):
        report_options = report.get_options(previous_options={**options, 'export_mode': 'file'})
        values = {}
        for line in report._get_lines(report_options):
            code = line.code
            if not code or not code.startswith('sk_'):
                continue

            expression_values = {
                column.expression_label: column.no_format
                for column in line.columns
            }
            values[code] = {
                'base': float_round(expression_values.get('base') or 0, precision_digits=2),
                'vat': float_round(expression_values.get('vat') or 0, precision_digits=2),
            }

        return values

    def _l10n_sk_compute_tax_period(self, date_from, date_to):
        month_value = ''
        quarter_value = ''
        quarter_start, quarter_end = date_utils.get_quarter(date_from)

        if date_from.year == date_to.year and date_from.month == date_to.month:
            month_value = str(date_to.month)
        elif date_from == quarter_start and date_to == quarter_end:
            quarter_value = str(date_utils.get_quarter_number(date_to))

        return {
            'mesiac': month_value,
            'stvrtrok': quarter_value,
            'rok': str(date_to.year),
        }

    def _l10n_sk_get_body_values(self, report_values):
        def _format_decimal(value):
            rounded = float_round(value or 0, precision_digits=2)
            return f"{rounded:.2f}"

        values = {
            xml_field: _format_decimal(report_values.get(report_code, {}).get(label, 0))
            for xml_field, report_code, label in self._BODY_FIELD_MAP
        }
        values['splneniePodmienok'] = '0'
        return values

    def _l10n_sk_get_header_values(self, company):
        partner = company.partner_id
        split_address = street_split(partner.street or '')

        company_name_lines = [line for line in (company.name or '').split('\n') if line][:4] or ['']
        partner_phone = partner.phone or company.phone or ''
        partner_email = partner.email or company.email or ''

        return {
            'kodStatu': 'SK',
            'cislo': company.partner_id._get_additional_identifier('SK_EN') or '',
            'dic': sk_vat.compact(company.vat or ''),
            'danovyUrad': '',
            'nevzniklaPov': '0',
            'rdp': '1',
            'odp': '0',
            'ddp': '0',
            'datumZisteniaDdp': '',
            'platitel': '1',
            'registrovana': '0',
            'inaPovinna': '0',
            'zdanitelna': '1',
            'zastupca': '0',
            'zastupca69aa': '0',
            'meno_riadky': company_name_lines,
            'ulica': split_address['street_name'] or '',
            'cislo_adresy': split_address['street_number'] or '',
            'psc': partner.zip or '',
            'obec': partner.city or '',
            'telefon': partner_phone,
            'email': partner_email,
            'menoPriezvisko': partner.name or '',
            'telefon_oos': partner_phone,
            'email_oos': partner_email,
            'datumVyhlasenia': date.today().strftime('%d.%m.%Y'),
        }

    def _l10n_sk_get_xml_values(self, report, options, company):
        date_from = fields.Date.to_date(options['date']['date_from'])
        date_to = fields.Date.to_date(options['date']['date_to'])
        report_values = self._l10n_sk_get_report_line_values(report, options)
        xml_values = self._l10n_sk_get_body_values(report_values)
        xml_values.update(self._l10n_sk_get_header_values(company))
        xml_values.update(self._l10n_sk_compute_tax_period(date_from, date_to))
        return xml_values

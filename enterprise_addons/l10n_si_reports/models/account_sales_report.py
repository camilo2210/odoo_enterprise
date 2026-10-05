from lxml import etree

from odoo import models
from odoo.tools import float_round
from odoo.tools.business_data import split_vat


class SlovenianECSalesReportCustomHandler(models.AbstractModel):
    _name = 'l10n_si.ec.sales.report.handler'
    _inherit = ['account.ec.sales.with.tags.report.handler']
    _description = 'Slovenian Sales Report Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options=None):
        si_tax_tags = self._get_ec_sales_tax_tags()
        options['sales_report_operation_types'] = {
            'goods': {
                'tax_tag_ids': si_tax_tags['goods'],
            },
            'services': {
                'tax_tag_ids': si_tax_tags['services'],
            },
            'triangular': {
                'tax_tag_ids': si_tax_tags['triangular'],
            },
            'goods_42_63': {
                'tax_tag_ids': si_tax_tags['goods_42_63'],
            },
            'goods_stocks': {
                'tax_tag_ids': si_tax_tags['goods_stocks'],
            },
        }
        super()._custom_options_initializer(report, options, previous_options)

    def _get_ec_sales_tax_tags(self):
        # Overrides account_reports
        tag_mapping = {
            'goods': self.env.ref('l10n_si.tax_report_ir_10a_tag'),
            'services': self.env.ref('l10n_si.tax_report_ir_10d_tag'),
            'triangular': self.env.ref('l10n_si.tax_report_ir_11_tag'),
            'goods_42_63': self.env.ref('l10n_si.tax_report_ir_10b_tag'),
            'goods_stocks': self.env.ref('l10n_si.tax_report_32_tag'),
        }

        return {
            key: ref._get_matching_tags().ids
            for key, ref in tag_mapping.items()
        }

    # ====================
    # EC Sales List Report
    # ====================
    def l10n_si_export_ec_sales_list_report_to_xml(self, options):
        # Method is public in order to be called from the Return Submission Wizard
        file_name = self._l10n_si_get_file_name(options['date']['date_to'])
        xml_content = self._l10n_si_ec_sales_list_generate_xml(options)
        return {
            'file_name': file_name,
            'file_content': xml_content,
            'file_type': 'xml',
        }

    def _l10n_si_get_file_name(self, report_date):
        # Format: {tax number without prefix}_YYYY-MM_VIES-KP.xml
        return f"{split_vat(self.env.company.vat, default_country_code='SI')[1]}_{report_date[:7]}_VIES_KP.xml"

    def _l10n_si_ec_sales_list_generate_xml(self, options):
        NSMAP = {
            'r': 'http://edavki.durs.si/Documents/Schemas/VIES_KP_5.xsd',
            'edp': 'http://edavki.durs.si/Documents/Schemas/EDP-Common-1.xsd',
            'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
        }

        def qname(prefix, tag):
            return etree.QName(NSMAP[prefix], tag)

        company = self.env.company

        # Root element
        envelope = etree.Element(qname('r', 'Envelope'), nsmap=NSMAP)

        # Header
        header = etree.SubElement(envelope, qname('edp', 'Header'))
        taxpayer = etree.SubElement(header, qname('edp', 'taxpayer'))

        etree.SubElement(taxpayer, qname('edp', 'taxNumber')).text = split_vat(company.vat, default_country_code='SI')[1]
        etree.SubElement(taxpayer, qname('edp', 'name')).text = company.name

        # Signature field
        etree.SubElement(envelope, qname('edp', 'Signatures'))

        # Structure
        body = etree.SubElement(envelope, qname('r', 'body'))
        etree.SubElement(body, qname('edp', 'bodyContent'))
        vies_kp = etree.SubElement(body, qname('r', 'VIES_KP'))

        # General
        general = etree.SubElement(vies_kp, "General")

        year, month, _day = options['date']['date_to'].split('-')
        etree.SubElement(general, "H1_Year").text = str(year)
        etree.SubElement(general, "H1_Month").text = str(int(month))

        ec_sales_report = self.env['account.report'].browse(options['report_id'])
        expressions = ec_sales_report.line_ids[0].expression_ids
        formulas_dict = expressions.grouped('formula')
        engine_total_results = self._report_engine_ec_sales_report(
            options,
            'strict_range',
            formulas_dict,
            None,
            warnings={},
        )[expressions]
        engine_partners_results = self._report_engine_ec_sales_report(
            options,
            'strict_range',
            formulas_dict,
            'partner_id',
            warnings={},
        )[expressions]

        totals_xml_mapping = {
            'goods': 'A13_CurrentTotal',
            'goods_42_63': 'A14_Current4263Total',
            'triangular': 'A15_CurrentThreePartyTotal',
            'services': 'A16_CurrentServiceTotal',
        }
        partners_xml_mapping = {
            'goods': 'A3_T',
            'goods_42_63': 'A4_C4263',
            'triangular': 'A5_T3',
            'services': 'A6_S',
        }

        for ec_sales_key, xml_key in totals_xml_mapping.items():
            #  Round up the total value to the nearest whole euro
            # (Mandatory requirement for the EC Sales List report as per FURS (Slovenian Tax Administration))
            rounded_value = int(float_round(engine_total_results[ec_sales_key], precision_digits=0, rounding_method='HALF-UP'))
            if rounded_value:
                etree.SubElement(general, xml_key).text = str(rounded_value)

        # A_Current block (transaction details per partner)
        A_Current = etree.SubElement(vies_kp, "A_Current")

        for partner_id, partner_values in engine_partners_results:
            partner_node = etree.SubElement(A_Current, "A")
            etree.SubElement(partner_node, 'A1_C').text = partner_values['country_code']
            etree.SubElement(partner_node, 'A2_N').text = partner_values['vat_number']

            for ec_sales_key, xml_key in partners_xml_mapping.items():
                #  Round up the total value to the nearest whole euro
                rounded_value = int(float_round(partner_values[ec_sales_key], precision_digits=0, rounding_method='HALF-UP'))
                if rounded_value:
                    etree.SubElement(partner_node, xml_key).text = str(rounded_value)

        report_xml_bytes = etree.tostring(envelope, pretty_print=True, encoding="UTF-8", xml_declaration=True)

        return report_xml_bytes

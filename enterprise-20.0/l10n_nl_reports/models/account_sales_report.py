# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re
from lxml import etree

from odoo import fields, models, _
from odoo.exceptions import RedirectWarning
from odoo.tools import cleanup_xml_node
from odoo.tools.business_data import split_vat


class L10n_Nl_ReportsEcSalesReportHandler(models.AbstractModel):
    _name = 'l10n_nl_reports.ec.sales.report.handler'
    _inherit = ['account.ec.sales.with.tags.report.handler']
    _description = 'Dutch EC Sales Report Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        nl_tax_tags = self._get_ec_sales_tax_tags()
        options.update({
            'sales_report_operation_types': {
                'goods': {
                    'tax_tag_ids': nl_tax_tags['goods'],
                },
                'services': {
                    'tax_tag_ids': nl_tax_tags['services'],
                },
                'triangular': {
                    'tax_tag_ids': nl_tax_tags['triangular'],
                },
            },
        })
        super()._custom_options_initializer(report, options, previous_options)
        options['buttons'].append({'name': "XBRL", 'sequence': 40, 'action': 'open_xbrl_wizard', 'file_export_type': _('XBRL')})
        options.get('sales_report_taxes', {}).update(self._get_ec_sales_tax_tags())

    def _get_ec_sales_tax_tags(self):
        # Overrides account_reports
        goods_expression = self.env.ref('l10n_nl.tax_report_rub_3bg_tag')
        services_expression = self.env.ref('l10n_nl.tax_report_rub_3bs_tag')
        triangular_expression = self.env.ref('l10n_nl.tax_report_rub_3bt_tag')
        return {
            'goods': goods_expression._get_matching_tags().ids,
            'services': services_expression._get_matching_tags().ids,
            'triangular': triangular_expression._get_matching_tags().ids,
        }

    def open_xbrl_wizard(self, options):
        res = self.env['l10n_nl_reports.tax.report.handler'].open_xbrl_wizard(options)
        res.update({
            'name': _('EC Sales (ICP) SBR'),
            'res_model': 'l10n_nl_reports.sbr.icp.wizard',
        })
        return res

    def export_icp_report_to_xbrl(self, options):
        # This will generate the XBRL file (similar style to XML).
        report = self.env['account.report'].browse(options['report_id'])
        lines = report._get_lines(options)
        data = self._generate_codes_values(report, lines, options)

        date_to = fields.Date.to_date(options['date']['date_to'])
        template_xmlid = 'l10n_nl_reports.icp_report_sbr'
        if date_to.year == 2024:
            # We still need to support the NT18 taxonomy for 2024 until that declaration period is over.
            template_xmlid = 'l10n_nl_reports.icp_report_sbr_nt18'
        elif date_to.year == 2025:
            # We still need to support the NT19 taxonomy for 2025 until that declaration period is over.
            template_xmlid = 'l10n_nl_reports.icp_report_sbr_nt19'

        report_template = self.env.ref(template_xmlid, raise_if_not_found=False)
        if not report_template:
            raise RedirectWarning(
                message=_(
                    "We couldn't find the correct export template for the year %(year)s. Please upgrade your module 'Netherlands - Accounting Reports' and try again.",
                    year=date_to.year,
                ),
                action=self.env.ref('base.open_module_tree').id,
                button_text=_("Go to Apps"),
                additional_context={
                    'search_default_name': 'l10n_nl_reports',
                    'search_default_extra': True,
                },
            )

        xbrl = self.env['ir.qweb']._render(report_template.id, data)
        xbrl_element = etree.fromstring(xbrl)
        xbrl_file = etree.tostring(cleanup_xml_node(xbrl_element, remove_blank_nodes=False), xml_declaration=True, encoding='utf-8')
        return {
            'file_name': report.get_default_report_filename(options, 'xbrl'),
            'file_content': xbrl_file,
            'file_type': 'xml',
        }

    def _generate_codes_values(self, report, lines, options):

        def get_country_and_vat(line, colname_to_idx):
            country = line.columns[colname_to_idx['country_code']].name
            vat = line.columns[colname_to_idx['vat_number']].name

            country = (country or '').strip().upper()
            vat = (vat or '').strip().upper()
            vat = re.sub(r'[^A-Z0-9]', '', vat)

            return country, vat

        def update_icp_context(contexts_map, country, vat):
            key = (country, vat)
            if key in contexts_map:
                return contexts_map[key]['contextRef']

            ctx_id = f"ICP_{country}_{vat or 'NOVAT'}"

            contexts_map[key] = {
                'contextRef': ctx_id,
                'country': country,
                'VATIdentificationNumberNational': vat,
            }
            return ctx_id

        codes_values = options.get('codes_values', {})
        vat_identification_division = codes_values.get('VATIdentificationNumberNLFiscalEntityDivision')
        if vat_identification_division is None:
            sender_vat = report._get_sender_company_for_export(options).vat
            vat_identification_division = split_vat(sender_vat, default_country_code='NL')[1]

        codes_values.update({
            'IntraCommunitySupplies': [],
            'IntraCommunityServices': [],
            'IntraCommunityABCSupplies': [],
            'VATIdentificationNumberNLFiscalEntityDivision': vat_identification_division,
        })

        icp_contexts_map = {}

        colname_to_idx = {col['expression_label']: idx for idx, col in enumerate(options.get('columns', []))}
        company_currency = self.env.company.currency_id

        for line in lines:
            if not line.columns[colname_to_idx['vat_number']].no_format or 0:
                continue

            country, vat = get_country_and_vat(line, colname_to_idx)

            amount_product = line.columns[colname_to_idx['goods']].no_format or 0
            if company_currency.compare_amounts(amount_product, 0):
                ctx_id = update_icp_context(icp_contexts_map, country, vat)
                codes_values['IntraCommunitySupplies'].append({
                    'CountryCodeISO': country,
                    'SuppliesAmount': str(int(amount_product)),
                    'VATIdentificationNumberNational': vat,
                    'contextRef': ctx_id,
                })

            amount_service = line.columns[colname_to_idx['services']].no_format or 0
            if company_currency.compare_amounts(amount_service, 0):
                ctx_id = update_icp_context(icp_contexts_map, country, vat)
                codes_values['IntraCommunityServices'].append({
                    'CountryCodeISO': country,
                    'ServicesAmount': str(int(amount_service)),
                    'VATIdentificationNumberNational': vat,
                    'contextRef': ctx_id,
                })

            amount_triangular = line.columns[colname_to_idx['triangular']].no_format or 0
            if company_currency.compare_amounts(amount_triangular, 0):
                ctx_id = update_icp_context(icp_contexts_map, country, vat)
                codes_values['IntraCommunityABCSupplies'].append({
                    'CountryCodeISO': country,
                    'SuppliesAmount': str(int(amount_triangular)),
                    'VATIdentificationNumberNational': vat,
                    'contextRef': ctx_id,
                })

        codes_values['contexts'] = list(icp_contexts_map.values())

        return codes_values

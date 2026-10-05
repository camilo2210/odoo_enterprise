# Part of Odoo. See LICENSE file for full copyright and licensing details.

from lxml import etree, objectify

from odoo import _, fields, models
from odoo.exceptions import RedirectWarning, UserError
from odoo.tools import float_round


class L10n_EeEcSalesReportHandler(models.AbstractModel):
    _name = 'l10n_ee.ec.sales.report.handler'
    _inherit = ['account.ec.sales.with.tags.report.handler']
    _description = 'Estonian EC Sales Report Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        ee_tax_tags = self._get_ec_sales_tax_tags()
        options.update({
            'sales_report_operation_types': {
                'goods': {
                    'tax_tag_ids': ee_tax_tags['goods'],
                },
                'services': {
                    'tax_tag_ids': ee_tax_tags['services'],
                },
                'triangular': {
                    'tax_tag_ids': ee_tax_tags['triangular'],
                },
            },
        })

        super()._custom_options_initializer(report, options, previous_options)

        options.setdefault('buttons', []).append({
            'name': _('XML'),
            'sequence': 30,
            'action': 'export_file',
            'action_param': 'export_to_xml_sales_report',
            'file_export_type': _('XML'),
        })

    def _get_ec_sales_tax_tags(self):
        # Overrides account_reports
        goods_expression = self.env.ref('l10n_ee.tax_report_line_ec_goods_tag')
        services_expression = self.env.ref('l10n_ee.tax_report_line_ec_services_tag')
        triangular_expression = self.env.ref('l10n_ee.tax_report_line_ec_triangular_tag')

        return {
            'goods': goods_expression._get_matching_tags().ids,
            'services': services_expression._get_matching_tags().ids,
            'triangular': triangular_expression._get_matching_tags().ids,
        }

    def export_to_xml_sales_report(self, options):
        report = self.env['account.report'].browse(options['report_id'])
        date_to = fields.Date.from_string(options['date'].get('date_to'))
        if options['date']['period_type'] != 'month':
            raise UserError(_('Choose a month to export the IC Supply Report'))
        company = self.env.company
        if not company.partner_id._get_additional_identifier('EE_EN'):
            action = self.env.ref('base.action_res_company_form')
            raise RedirectWarning(_('No company registry number associated with your company. Please define one.'), action.id, _("Company Settings"))

        lines = report._get_lines(options)
        colexpr_to_idx = {col['expression_label']: idx for idx, col in enumerate(options.get('columns', []))}
        rows = []
        undefined_vat_partners = []
        for line in lines:
            if report._get_model_info_from_id(line.id)[0] != 'res.partner':
                continue

            vat_number = line.columns[colexpr_to_idx['vat_number']].name
            if not vat_number:
                undefined_vat_partners.append(line.name)
            rows.append({
                'country_code': line.columns[colexpr_to_idx['country_code']].name,
                'vat_number': vat_number,
                'goods': int(float_round(line.columns[colexpr_to_idx['goods']].no_format, precision_digits=0)),
                'triangular': int(float_round(line.columns[colexpr_to_idx['triangular']].no_format, precision_digits=0)),
                'services': int(float_round(line.columns[colexpr_to_idx['services']].no_format, precision_digits=0)),
            })

        if undefined_vat_partners:
            raise UserError(_('No VAT number defined for the following partners: %s', ', '.join(undefined_vat_partners)))

        xml_data = {
            'tax_payer_reg_code': company.partner_id._get_additional_identifier('EE_EN'),
            'year': date_to.year,
            'month': date_to.month,
            'rows': rows,
        }

        rendered_content = self.env['ir.qweb']._render('l10n_ee_reports.ec_sales_report_xml', xml_data)
        tree = objectify.fromstring(rendered_content)

        return {
            'file_name': report.get_default_report_filename(options, 'xml'),
            'file_content': etree.tostring(tree, pretty_print=True, xml_declaration=True, encoding='utf-8'),
            'file_type': 'xml',
        }

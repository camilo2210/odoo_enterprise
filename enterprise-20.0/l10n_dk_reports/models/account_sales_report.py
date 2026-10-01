# Part of Odoo. See LICENSE file for full copyright and licensing details.
import csv
import io

from odoo import _, models
from odoo.exceptions import RedirectWarning


class L10n_DkEcSalesReportHandler(models.AbstractModel):
    _name = 'l10n_dk.ec.sales.report.handler'
    _inherit = ['account.ec.sales.with.tags.report.handler']
    _description = 'Denmark EC Sales Report Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options):

        dk_tax_tags = self._get_ec_sales_tax_tags()
        options.update({
            'sales_report_operation_types': {
                'goods': {
                    'tax_tag_ids': dk_tax_tags['goods'],
                },
                'services': {
                    'tax_tag_ids': dk_tax_tags['services'],
                },
                'triangular': {
                    'tax_tag_ids': dk_tax_tags['triangular'],
                },
            },
        })

        super()._custom_options_initializer(report, options, previous_options)

        options.setdefault('buttons', []).append({
            'name': _('CSV'),
            'sequence': 30,
            'action': 'export_file',
            'action_param': 'export_sales_report_to_csv',
            'file_export_type': _('CSV'),
        })

    def _get_ec_sales_tax_tags(self):
        # Overrides account_reports
        goods_expression = self.env.ref('l10n_dk.account_tax_report_line_section_b_product_eu_tag')
        services_expression = self.env.ref('l10n_dk.account_tax_report_line_section_b_services_tag')
        triangular_expression = self.env.ref('l10n_dk.account_tax_report_line_section_b_triangular_tag')

        return {
            'goods': goods_expression._get_matching_tags().ids,
            'services': services_expression._get_matching_tags().ids,
            'triangular': triangular_expression._get_matching_tags().ids,
        }

    def _report_engine_ec_sales_report(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        results = super()._report_engine_ec_sales_report(options, date_scope, formulas_dict, current_groupby, warnings)
        if current_groupby:
            for key, res in results[next(iter(formulas_dict.values()))]:
                # Denmark government impose that country code for greece is EL
                if res['country_code'] == 'GR':
                    res['country_code'] = 'EL'
        return results

    def export_sales_report_to_csv(self, options):
        colname_to_idx = {col['expression_label']: idx for idx, col in enumerate(options.get('columns', []))}
        report = self.env['account.report'].browse(options['report_id'])

        cvr_number = self.env.company.partner_id._get_additional_identifier('DK_CVR')
        if not cvr_number:
            raise RedirectWarning(
                _("No CVR number associated with your company."),
                self.env.ref('base.action_res_company_form').id,
                _("Add CVR number")
            )

        # First heading line:
        # Always start with 0, then our CVR number, then the word LISTE, rest is empty
        csv_lines = [
            [0, cvr_number, 'LISTE', '', '', '', '', '', ''],
        ]

        lines = report._get_lines(options)

        date_formatted = options['date'].get('date_to')
        index = 0
        for line in lines:
            if report._get_model_info_from_id(line.id)[0] != 'res.partner':
                continue

            customer_vat = line.columns[colname_to_idx['vat_number']].name

            if not customer_vat:
                redirect_action = {
                    'view_mode': 'form',
                    'res_model': 'res.partner',
                    'type': 'ir.actions.act_window',
                    'res_id': int(report._get_model_info_from_id(line.id)[1]),
                    'views': [(False, 'form')]
                }
                raise RedirectWarning(
                    _("Customer's VAT cannot be empty"),
                    redirect_action,
                    _("Change the VAT number")
                )

            country_code = line.columns[colname_to_idx['country_code']].name or ''

            # line entry, should always start with 'id 2' format:
            # 2, id, end date of the report, our company cvr number, the partner country code, partner VAT, amounts for goods, triangular, services
            csv_lines.append(
                [
                    2,
                    index,
                    date_formatted,
                    cvr_number,
                    country_code,
                    customer_vat,
                    round(line.columns[colname_to_idx['goods']].no_format or 0),
                    round(line.columns[colname_to_idx['triangular']].no_format or 0),
                    round(line.columns[colname_to_idx['services']].no_format or 0),
                ]
            )
            index += 1

        # Last line is the total line, first column is always 'id 10', then we get the number of lines with 'id 2' and after that the total balance
        # all the other columns should stay empty
        csv_lines.append(
            [
                10,
                index,
                round(lines[-1].columns[colname_to_idx['balance']].no_format) if lines else 0,
                '',
                '',
                '',
                '',
                '',
                ''
            ]
        )

        buf = io.StringIO()
        writer = csv.writer(buf, delimiter=',')
        writer.writerows(csv_lines)

        return {
            'file_name': report.get_default_report_filename(options, 'csv'),
            'file_content': buf.getvalue().encode(),
            'file_type': 'csv',
        }

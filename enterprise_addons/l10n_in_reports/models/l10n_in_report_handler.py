# Part of Odoo. See LICENSE file for full copyright and licensing details.
import io
from collections import defaultdict

import logging
import re
import xlsxwriter

from odoo import api, models, _
from odoo.fields import Domain
from odoo.tools import SQL

_logger = logging.getLogger(__name__)


class AccountReport(models.Model):
    _inherit = 'account.report'

    def _init_options_buttons(self, options, previous_options):
        super()._init_options_buttons(options, previous_options)
        company = self.env.company
        gstr2b_report = self.env.ref('l10n_in_reports.account_report_gstr2b').id

        # Remove 'Returns' button if company is Indian and eFiling is disabled
        if company.country_id.code == 'IN' and not self.env.company.l10n_in_gst_efiling_feature:
            options['buttons'] = [
                button for button in options['buttons']
                if button.get('action') != 'action_open_returns'
            ]
        if gstr2b_report == options['report_id']:
            for button in options['buttons']:
                if button.get('action') == 'action_open_returns':
                    button['name'] = 'Reconcile'

    def _is_available_for(self, companies):
        in_companies = self.env.companies.filtered(lambda c: c.account_fiscal_country_id.code == 'IN')
        if not in_companies:
            return super()._is_available_for(companies)

        to_exclude = set()

        if not any(c.l10n_in_gst_efiling_feature for c in in_companies):
            to_exclude.update({
                'l10n_in_reports.account_report_gstr1',
                'l10n_in_reports.account_report_gstr2b',
                'l10n_in_reports.account_report_gstr3b',
                'l10n_in_reports.account_report_cmp_08',
                'l10n_in_reports.account_report_gstr4',
            })
        elif any(
            company.l10n_in_gst_registration_type == 'composition'
            for company in in_companies
        ):
            to_exclude.update({
                'l10n_in_reports.account_report_gstr1',
                'l10n_in_reports.account_report_gstr2b',
                'l10n_in_reports.account_report_gstr3b',
            })
        else:
            to_exclude.update({
                'l10n_in_reports.account_report_cmp_08',
                'l10n_in_reports.account_report_gstr4',
            })

        if not any(c.l10n_in_tcs_feature for c in in_companies):
            to_exclude.add('l10n_in.tcs_report')

        if not any(c.l10n_in_tds_feature for c in in_companies):
            to_exclude.add('l10n_in.tds_report')

        external_ids = self._get_external_ids()
        reports = self.filtered(lambda report: (external_ids.get(report.id) or [None])[0] not in to_exclude)
        return super(AccountReport, reports)._is_available_for(companies)


class L10n_InReportHandler(models.AbstractModel):
    _name = 'l10n_in.report.handler'
    _inherit = ['account.generic.tax.report.handler']
    _description = 'Indian Tax Report Custom Handler'

    def _custom_line_postprocessor(self, report, options, lines):
        if (
            report.id == self.env.ref('l10n_in_reports.account_report_gstr1').id
            and self.env.company.l10n_in_disable_b2c_hsn_reporting
        ):
            lines.remove(report._get_line_from_xml_id(lines, 'l10n_in_reports.account_report_gstr1_hsn_b2c'))
        return super()._custom_line_postprocessor(report, options, lines)

    @api.model
    def _get_invalid_intra_state_tax_on_lines(self, aml_domain):
        intra_state_sgst_cgst = self.env['account.move.line'].search(
            aml_domain +
            [
                ('move_id.l10n_in_transaction_type', '=', 'intra_state'),
                ('tax_tag_ids', 'in', self.env.ref('l10n_in.tax_tag_base_igst').id),
                ('move_id.l10n_in_gst_treatment', '!=', 'special_economic_zone')
            ]
        )
        return 'l10n_in_reports.invalid_intra_state_warning', intra_state_sgst_cgst

    @api.model
    def _get_invalid_inter_state_tax_on_lines(self, aml_domain):
        inter_state_igst = self.env['account.move.line'].search(
            aml_domain +
            [
                ('move_id.l10n_in_transaction_type', '=', 'inter_state'),
                ('tax_tag_ids', 'in', (self.env.ref('l10n_in.tax_tag_base_cgst').id, self.env.ref('l10n_in.tax_tag_base_sgst').id)),
            ]
        )
        return 'l10n_in_reports.invalid_inter_state_warning', inter_state_igst

    def _get_invalid_no_hsn_line_domain(self):
        return [
            ('l10n_in_gstr_section', '!=', 'sale_out_of_scope'),
            ('l10n_in_hsn_code', '=', False),
            ('display_type', '!=', 'tax'),
            '|',
            ('company_id.l10n_in_disable_b2c_hsn_reporting', '=', False),
            ('move_id.l10n_in_gst_treatment', 'in', self.env['account.move']._l10n_in_get_b2b_gst_treatments()),
        ]

    @api.model
    def _get_invalid_no_hsn_products(self, aml_domain):
        missing_hsn = self.env['account.move.line'].search(
            aml_domain + self._get_invalid_no_hsn_line_domain()
        )
        return 'l10n_in_reports.missing_hsn_warning', missing_hsn

    @api.model
    def _get_invalid_uqc_codes(self, aml_domain):
        uqc_codes = [
            'BAG-BAGS',
            'BAL-BALE',
            'BDL-BUNDLES',
            'BKL-BUCKLES',
            'BOU-BILLION OF UNITS',
            'BOX-BOX',
            'BTL-BOTTLES',
            'BUN-BUNCHES',
            'CAN-CANS',
            'CBM-CUBIC METERS',
            'CCM-CUBIC CENTIMETERS',
            'CMS-CENTIMETERS',
            'CTN-CARTONS',
            'DOZ-DOZENS',
            'DRM-DRUMS',
            'GGK-GREAT GROSS',
            'GMS-GRAMMES',
            'GRS-GROSS',
            'GYD-GROSS YARDS',
            'KGS-KILOGRAMS',
            'KLR-KILOLITRE',
            'KME-KILOMETRE',
            'LTR-LITRES',
            'MLT-MILILITRE',
            'MTR-METERS',
            'MTS-METRIC TON',
            'NOS-NUMBERS',
            'PAC-PACKS',
            'PCS-PIECES',
            'PRS-PAIRS',
            'QTL-QUINTAL',
            'ROL-ROLLS',
            'SET-SETS',
            'SQF-SQUARE FEET',
            'SQM-SQUARE METERS',
            'SQY-SQUARE YARDS',
            'TBS-TABLETS',
            'TGM-TEN GROSS',
            'THD-THOUSANDS',
            'TON-TONNES',
            'TUB-TUBES',
            'UGS-US GALLONS',
            'UNT-UNITS',
            'YDS-YARDS',
            'OTH-OTHERS',
        ]
        domain = aml_domain + [
                    ('l10n_in_gstr_section', '!=', 'sale_out_of_scope'),
                    ('product_id.l10n_in_hsn_code', 'not =ilike', '99%'),
                    ('product_id.uom_id.l10n_in_code', 'not in', uqc_codes),
                ]
        invalid_uqc_codes = self.env['account.move.line'].search(domain).product_id.uom_id
        return 'l10n_in_reports.invalid_uqc_code_warning', invalid_uqc_codes

    def _get_reversed_moves_domain(self, options):
        return [
            ('date', '>=', options['date']['date_from']),
            ('date', '<=', options['date']['date_to']),
            ('move_type', '=', 'out_refund'),
            ('state', '=', 'posted'),
            '|',
            ('line_ids.tax_ids.l10n_in_tax_type', 'in', ['gst', 'nil_rated', 'exempt', 'non_gst']),
            ('line_ids.tax_line_id.l10n_in_tax_type', 'in', ['gst', 'nil_rated', 'exempt', 'non_gst'])
        ]

    @api.model
    def _get_unlinked_unregistered_inter_state_reversed_moves(self, options):
        unlinked_reversed_moves = self.env['account.move'].search(
            self._get_reversed_moves_domain(options) +
            [
                ('reversed_entry_id', '=', False),
                ('l10n_in_gst_treatment', 'in', ['unregistered', 'consumer']),
                ('l10n_in_transaction_type', '=', 'inter_state'),
            ]
        )
        return 'l10n_in_reports.unlinked_reversed_moves_warning', unlinked_reversed_moves

    @api.model
    def _get_invalid_tds_tcs_moves(self, options, report):
        domain = [
            ('date', '>=', options['date']['date_from']),
            ('date', '<=', options['date']['date_to']),
            ('state', '=', 'posted'),
            ('move_type', '!=', 'entry'),
            ('commercial_partner_id.l10n_in_pan_entity_id', '=', False),
        ]

        if report.id == self.env.ref("l10n_in.tds_report_it_act_25").id:
            domain += [
                ('invoice_line_ids.tax_ids.l10n_in_tax_type', '=', 'tds'),
                ('invoice_line_ids.tax_ids.type_tax_use', '=', 'purchase'),
            ]
        elif report.id == self.env.ref("l10n_in.tcs_report_it_act_25").id:
            domain += [
                ('invoice_line_ids.tax_ids.l10n_in_tax_type', '=', 'tcs'),
                ('invoice_line_ids.tax_ids.type_tax_use', '=', 'sale'),
            ]
        invalid_move_ids = self.env['account.move'].search(domain).ids

        return 'l10n_in_reports.missing_pan_tds_tcs_warning', invalid_move_ids

    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals, warnings=None):
        if warnings is not None:
            hsn_base_line_domain = [
                ('l10n_in_gstr_section', '=like', 'sale%'),
                ('display_type', '=', 'product'),
            ]

            options_domain = report._get_options_domain(options, date_scope='strict_range')

            aml_domain = Domain.AND([
                options_domain,
                hsn_base_line_domain,
            ])
            all_checks = []
            if report.id == self.env.ref("l10n_in_reports.account_report_gstr1").id:
                all_checks = [
                    self._get_invalid_intra_state_tax_on_lines(aml_domain),
                    self._get_invalid_inter_state_tax_on_lines(aml_domain),
                    self._get_invalid_no_hsn_products(aml_domain),
                    self._get_invalid_uqc_codes(aml_domain),
                    self._get_unlinked_unregistered_inter_state_reversed_moves(options),
                ]
                all_checks = [
                    (xml_id, obj.ids)
                    for xml_id, obj in all_checks
                ]
            elif report.id in (self.env.ref("l10n_in.tds_report_it_act_25").id, self.env.ref("l10n_in.tcs_report_it_act_25").id):
                all_checks = [
                    self._get_invalid_tds_tcs_moves(options, report),
                ]

            for warning_template_ref, wrong_data in all_checks:
                if wrong_data:
                    warnings[warning_template_ref] = {'ids': wrong_data, 'alert_type': 'warning'}
        return []

    def _l10n_in_open_action(self, name, res_model, views, params):
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': res_model,
            'views': views,
            'domain': [('id', 'in', params['ids'])],
            'context': {
                'create': False,
                'delete': False,
                'expand': True,
            },
        }

    @api.model
    def open_invalid_intra_state_lines(self, options, params):
        return self._l10n_in_open_action(_('Invalid tax for Intra State Transaction'), 'account.move.line', [(False, 'list')], params)

    @api.model
    def open_invalid_inter_state_lines(self, options, params):
        return self._l10n_in_open_action(_('Invalid tax for Inter State Transaction'), 'account.move.line', [(False, 'list')], params)

    @api.model
    def open_missing_hsn_products(self, options, params):
        return self._l10n_in_open_action(_('Missing HSN for Journal Items'), 'account.move.line', [(False, 'list'), (False, 'form')], params)

    @api.model
    def open_invalid_uqc_codes(self, options, params):
        return self._l10n_in_open_action(_('Invalid UQC Code'), 'uom.uom', [(False, 'list'), (False, 'form')], params)

    @api.model
    def open_unlinked_reversed_moves(self, options, params):
        return self._l10n_in_open_action(_('Unlinked Credit Notes'), 'account.move', [(False, 'list'), (False, 'form')], params)

    @api.model
    def open_missing_pan_tds_tcs_moves(self, options, params):
        return self._l10n_in_open_action(_('Journal Entries'), 'account.move', [(False, 'list'), (False, 'form')], params)

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options)

        if self.env.company.account_fiscal_country_id.code != 'IN':
            return
        if report in (self.env.ref('l10n_in.tds_report'), self.env.ref('l10n_in.tcs_report'), self.env.ref('l10n_in.tcs_report_it_act_25'), self.env.ref('l10n_in.tds_report_it_act_25')):
            xlsx_button_option = next(button_opt for button_opt in options['buttons'] if button_opt.get('action_param') == 'export_to_xlsx')
            xlsx_button_option['action_param'] = 'tds_tcs_export_to_xlsx'

    @api.model
    def tds_tcs_export_to_xlsx(self, options):
        is_tds_report = options['report_id'] in (
            self.env.ref('l10n_in.tds_report').id,
            self.env.ref('l10n_in.tds_report_it_act_25').id,
        )
        with io.BytesIO() as output:
            with xlsxwriter.Workbook(output, {
                'in_memory': True,
                'strings_to_formulas': False,
            }) as workbook:
                self._tds_tcs_inject_report_into_xlsx_sheet(options, workbook, is_tds_report)
            report_period = options['date']['string']
            file_name = f"{re.sub(r'[^a-z0-9_]', '', report_period.lower().replace(' - ', '_').replace(' ', '_'))}_{'tds' if is_tds_report else 'tcs'}_report.xlsx"
            return {
                'file_name': file_name,
                'file_content': output.getvalue(),
                'file_type': 'xlsx',
            }

    @api.model
    def _tds_tcs_inject_report_into_xlsx_sheet(self, options, workbook, is_tds_report):
        def write_header(sheet, header):
            for i, val in enumerate(header):
                sheet.write(i, 0, val, title_style)

        def write_rows(sheet, start_row, rows, style_func):
            for i, row in enumerate(rows):
                style = style_func(i)
                for j, val in enumerate(row):
                    sheet.write(start_row + i, j, val, style)

        report = self.env['account.report'].browse(options['report_id'])
        company_name = self.env.company.name
        report_date = options['date']['string']

        title_style = workbook.add_format({'bold': True, 'font_name': 'Arial'})
        line_style = workbook.add_format({'font_name': 'Arial', 'font_size': 11, 'align': 'left'})

        colname_to_idx = {col['expression_label']: idx for idx, col in enumerate(options.get('columns', []))}
        lines_mapping = {
            line['name']: ("{:.2f}".format(float(line.columns[colname_to_idx['balance']].no_format)))
            for line in report._get_lines(options)
        }

        # Add Summary Sheet
        summary_sheet = workbook.add_worksheet('Summary')
        summary_sheet.set_column(0, 0, 60)
        summary_sheet.set_column(1, 1, 15)
        write_header(summary_sheet, [report_date, company_name])

        summary_rows = [[name, balance] for name, balance in lines_mapping.items()]
        summary_rows.insert(0, ['Section', 'Balance'])
        write_rows(summary_sheet, 3, summary_rows, lambda i: title_style if i == 0 else line_style)

        # Add Section Sheets
        section_data = self._prepare_tds_tcs_report_data(options, is_tds_report)
        col_widths = [6, 16, 12, 18, 14, 18, 16, 14, 10]
        if is_tds_report:
            col_widths.insert(1, 16)
            col_widths.insert(3, 22)
            col_widths.insert(10, 14)
            col_widths.insert(11, 12)
            col_widths.insert(12, 12)
        for section_name, section_info in section_data.items():
            sheet = workbook.add_worksheet(section_name)
            for i, width in enumerate(col_widths):
                sheet.set_column(i, i, width)
            write_header(sheet, [report_date, section_info['description']])
            write_rows(sheet, 3, section_info['moves'], lambda i: title_style if i == 0 else line_style)

    @api.model
    def _prepare_tds_tcs_report_data(self, options, is_tds_report):
        columns = [
            _("Sr. No."),
            _("Bill") if is_tds_report else _("Journal Entry"),
            _("PAN"),
            _("Vendor") if is_tds_report else _("Customer"),
            _("Bill/Payment Date") if is_tds_report else _("Payment Date"),
            _("Bill/Payment Amount") if is_tds_report else _("Payment Amount"),
            _("Credit Note/Refund/TDS Cr. Amount") if is_tds_report else _("TCS Cr. Amount"),
            _("TDS Dr. Amount") if is_tds_report else _("TCS Dr. Amount"),
            _("TDS Rate") if is_tds_report else _("TCS Rate"),
        ]

        # -----------------------------------
        # Step 1: Map report tags to section metadata (name & description)
        # -----------------------------------
        report = self.env['account.report'].browse(options['report_id'])

        tag_to_section = {}
        all_tag_ids = set()

        for line in report.line_ids:
            tags = line.expression_ids._get_matching_tags()

            for tag in tags:
                tag_to_section[tag.id] = {
                    'code': tag.name,
                    'description': line.name,
                }
                all_tag_ids.add(tag.id)

        # -----------------------------------
        # Step 2: Query
        # -----------------------------------

        domain = [
            ('move_id.date', '>=', options['date']['date_from']),
            ('move_id.date', '<=', options['date']['date_to']),
            ('move_id.state', '=', 'posted'),
            ('tax_line_id.l10n_in_tax_type', '=', 'tds' if is_tds_report else 'tcs'),
            ('tax_tag_ids', 'in', all_tag_ids),
        ]
        if is_tds_report:
            domain += [
                ('tax_line_id.l10n_in_tax_type', '=', 'tds'),
            ]
        else:
            domain += [
                ('tax_line_id.l10n_in_tax_type', '=', 'tcs'),
            ]
        query = self.env['account.move.line']._search(domain)
        aml_t = query.table._sudo()
        am_t = aml_t._join('move_id', kind='JOIN')
        tax_t = aml_t._join('tax_line_id', kind='JOIN')
        tag_t = aml_t._join('tax_tag_ids')
        partner = aml_t.partner_id
        pan_entity = partner.l10n_in_pan_entity_id

        # -----------------------------------
        # Step 3: Select
        # -----------------------------------
        common_cols = [
            SQL("%s AS partner_name", partner.name),
            SQL("%s AS partner_pan", pan_entity.name),
            SQL("%s AS tag_id", tag_t.id),
            SQL("COALESCE(%s, 0) AS tax_debit_amount", aml_t.debit),
            SQL("COALESCE(%s, 0) AS tax_credit_amount", aml_t.credit),
            SQL("COALESCE(%s, 0) AS amount", aml_t.tax_base_amount),
        ]

        if is_tds_report:
            columns.insert(1, _("Journal Entry"))
            columns.insert(3, _("Bill Ref. (Supplier Inv. No.)"))
            columns.insert(10, _("Deduction Date"))
            columns.insert(11, _("Remarks (Reason for non-deduction/lower deduction/higher deduction/threshold)"))
            columns.insert(12, _("Deductee Code (1. Company, 2. Other than Company)"))

            payment_t = am_t._join('origin_payment_id', kind='JOIN')
            bill_move = payment_t._join('invoice_ids', kind='JOIN')

            qu = query.select(
                *common_cols,
                SQL("%s AS tds_remarks", pan_entity.tds_deduction),
                SQL("%s AS deductee_code", pan_entity.type),
                SQL("%s AS wh_move_name", am_t.name),
                SQL("%s AS move_name", bill_move.name),
                bill_move.invoice_date,
                SQL("%s AS bill_ref", bill_move.ref),
                SQL("ABS(%s) AS tax_rate", tax_t.amount),
                SQL("%s AS deduction_date", am_t.date),
            )
        else:
            qu = query.select(
                *common_cols,
                SQL("%s AS move_name", am_t.name),
                am_t.invoice_date,
                SQL("%s AS tax_rate", tax_t.amount),
            )

        rows = self.env.execute_query_dict(qu)

        # -----------------------------------
        # Step 4: Group by Section
        # -----------------------------------
        section_data = defaultdict(lambda: {'description': '', 'moves': [], 'row_count': 0})
        for row in rows:
            section = tag_to_section.get(row['tag_id'])
            section_key = section['code']
            data = section_data[section_key]

            data['row_count'] += 1
            sr_no = data['row_count']

            data['description'] = section['description']
            if not data['moves']:
                data['moves'].append(columns)

            line = [
                sr_no,
                row['move_name'] or '',
                row['partner_pan'] or '',
                row['partner_name'] or '',
                row['invoice_date'].strftime("%d/%m/%y") if row['invoice_date'] else '',
                f"{row['amount']:.2f}",
                f"{row['tax_credit_amount']:.2f}",
                f"{row['tax_debit_amount']:.2f}",
                f"{row['tax_rate']}%",
            ]
            if is_tds_report:
                line.insert(1, row['wh_move_name'])
                line.insert(3, row['bill_ref'])
                line.insert(10, row['deduction_date'].strftime("%d/%m/%y") if row['deduction_date'] else '')
                line.insert(11, row['tds_remarks'])
                line.insert(12, '' if not row['deductee_code'] else (1 if row['deductee_code'] == 'c' else 2))
            data['moves'].append(line)

        return section_data

    def _report_engine_outward_supplies_tax_amounts(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        tax_total = 0.0
        report = self.env['account.report'].browse(options['report_id'])
        for company_data in options['companies']:
            company = self.env['res.company'].browse(company_data['id'])

            if company.l10n_in_gst_registration_type != 'composition' or not company.l10n_in_composition_tax_rate:
                continue

            domain = [
                ('l10n_in_gstr_section', '=', 'sale_composition_supplies'),
                ('display_type', '=', 'product')
            ]
            domain = report._get_options_domain(options, date_scope) & Domain(domain)

            taxable_result = self.env['account.move.line']._read_group(
                domain,
                aggregates=['balance:sum'],
            )
            taxable_base = -taxable_result[0][0]
            tax_rate = float(company.l10n_in_composition_tax_rate) / 2 / 100
            tax_total += taxable_base * tax_rate

        return {
            next(iter(formulas_dict.values())): {
                'tax_amount': tax_total,
            }
        }

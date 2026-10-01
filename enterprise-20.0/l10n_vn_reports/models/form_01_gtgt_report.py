
from lxml import etree

from odoo import _, fields, models, release
from odoo.exceptions import UserError
from odoo.tools import float_round
from odoo.tools.misc import default_parser, file_path

from odoo.addons.l10n_vn_reports.models.appendix142 import (
    VAT_8_PURCHASE_BASE_TAGS,
    VAT_8_PURCHASE_TAX_TAGS,
    VAT_8_SALE_BASE_TAGS,
    VAT_8_SALE_TAX_TAGS,
)


class L10nVnReportsForm01GtgtHandler(models.AbstractModel):
    _name = 'l10n_vn_reports.form_01_gtgt.report.handler'
    _inherit = 'account.tax.report.handler'
    _description = 'Vietnam Form 01/GTGT Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        options.setdefault('buttons', []).append({
            'name': _('XML'),
            'sequence': 30,
            'action': 'print_tax_report_to_xml',
            'file_export_type': _('XML'),
        })

    def print_tax_report_to_xml(self, options):
        view_id = self.env.ref('l10n_vn_reports.form_01_gtgt_xml_export_wizard_view').id
        return {
            'name': _('01/GTGT Export Options'),
            'view_mode': 'form',
            'views': [[view_id, 'form']],
            'res_model': 'l10n_vn_reports.form_01_gtgt.export.wizard',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': dict(self.env.context, l10n_vn_reports_form_01_gtgt_options=options),
        }

    def export_tax_report_to_xml(self, options):
        report = self.env['account.report'].browse(options['report_id'])

        company = report._get_sender_company_for_export(options)
        if not company.has_vat:
            raise UserError(_("Please set a VAT number on the company before exporting the Vietnamese Tax Report."))

        xml_export_data = self._l10n_vn_get_xml_export_data(options)
        rendered = self.env['ir.qweb']._render('l10n_vn_reports.form_01_gtgt_xml_export_template', xml_export_data)
        tree = etree.fromstring(str(rendered).encode(), parser=default_parser)
        if error := self._l10n_vn_validate_xml(tree):
            raise UserError(_("The generated XML failed XSD validation:\n%s", error))
        xml_content = etree.tostring(tree, pretty_print=True, xml_declaration=True, encoding='UTF-8', standalone=True)

        period_label = xml_export_data['period_label'].replace('/', '_')
        vat = xml_export_data['taxpayer_vat']
        return {
            'file_name': f'01_GTGT_{period_label}_{vat}.xml',
            'file_content': xml_content,
            'file_type': 'xml',
        }

    def _l10n_vn_validate_xml(self, xml_root):
        schema_path = file_path('l10n_vn_reports/data/xml_schema/01_gtgt.xsd')
        schema = etree.XMLSchema(etree.parse(schema_path))
        try:
            schema.assertValid(xml_root)
            return None
        except etree.DocumentInvalid as err:
            return err

    def _l10n_vn_format_amount(self, value):
        """Round and cast an amount to int, as required by the XSD. Returns 0 for falsy input."""
        return int(float_round(value or 0, precision_digits=0))

    # ---------------------------------------------------------------
    # Data preparation
    # ---------------------------------------------------------------
    def _l10n_vn_get_xml_export_data(self, options):
        report = self.env['account.report'].browse(options['report_id'])
        company = report._get_sender_company_for_export(options)
        wizard_data = options.get('l10n_vn_xml_export') or {}

        period = self._l10n_vn_compute_period(report, options)
        line_values = self._l10n_vn_collect_main_lines(report, options)
        appendix = self._l10n_vn_collect_appendix_142(options)

        show_dependent = wizard_data.get('show_dependent_unit', False)
        ward = wizard_data.get('ward', '') if show_dependent else ''
        district = wizard_data.get('district', '') if show_dependent else ''
        province_code = wizard_data.get('province_code', '') if show_dependent else ''
        province_name = wizard_data.get('province_name', '') if show_dependent else ''

        today = fields.Date.context_today(self)
        complete_address = ', '.join(p for p in [company.street, company.street2] if p)

        return {
            # Service provider (Odoo)
            'service_provider_code': 'ODOO',
            'service_provider_name': 'Odoo',
            'service_provider_version': release.series,
            'service_provider_info': 'Odoo S.A.',

            # Declaration header
            'declaration_code': '842',
            'declaration_name': 'TỜ KHAI THUẾ GIÁ TRỊ GIA TĂNG (MẪU SỐ 01/GTGT)',
            'declaration_xml_version': '2.7.4',
            'declaration_type': 'C' if wizard_data.get('first_time', True) else 'B',
            'submission_count': str(int(wizard_data.get('adjustment_no') or 0)),
            'period_type': period['period_type'],
            'period_label': period['period_label'],
            'period_date_from': period['date_from'],
            'period_date_to': period['date_to'],
            'declaration_date': today.strftime('%d/%m/%Y'),
            'signatory': self.env.user.name or '',
            'sign_date': today.strftime('%Y-%m-%d'),

            # Taxpayer
            'taxpayer_vat': company.vat or '',
            'taxpayer_name': company.name or '',
            'taxpayer_address': complete_address or '',
            'taxpayer_city_code': company.city or '',
            'taxpayer_city_name': company.city or '',
            'taxpayer_state_code': company.state_id.name or '',
            'taxpayer_state_name': company.state_id.name or '',
            'taxpayer_phone': company.phone or '',
            'taxpayer_email': company.email or '',

            # Business activity / dependent unit
            'business_activity_code': wizard_data.get('business_activity_code', '00'),
            'business_activity_label': wizard_data.get('business_activity_label', ''),
            'show_dependent_unit': show_dependent,
            'ct09': wizard_data.get('dependent_unit_name', '') if show_dependent else '',
            'ct10': wizard_data.get('dependent_unit_tax_code', '') if show_dependent else '',
            'ct11a_code': ward,
            'ct11a_name': ward,
            'ct11b_code': district,
            'ct11b_name': district,
            'ct11c_code': province_code,
            'ct11c_name': province_name,

            # Main section line values (ct21..ct43)
            'lines': line_values,

            # Appendix 142 (only when 8% activity exists)
            'appendix_142': appendix,
        }

    def _l10n_vn_compute_period(self, report, options):
        date_from = fields.Date.from_string(options['date']['date_from'])
        date_to = fields.Date.from_string(options['date']['date_to'])
        formatted_date_from = date_from.strftime('%d/%m/%Y')
        formatted_date_to = date_to.strftime('%d/%m/%Y')

        inferred_type = report._infer_period_type_from_dates(options, date_from, date_to)

        if inferred_type == 'month':
            period_type = 'M'
            period_label = date_from.strftime('%m/%Y')
        elif inferred_type == 'quarter':
            period_type = 'Q'
            quarter = (date_from.month - 1) // 3 + 1
            period_label = f'{quarter}/{date_from.year}'
        else:
            # Fallback to monthly representation of the end month (HTKK still lets the user adjust).
            period_type = 'M'
            period_label = date_to.strftime('%m/%Y')

        return {
            'period_type': period_type,
            'period_label': period_label,
            'date_from': formatted_date_from,
            'date_to': formatted_date_to,
        }

    def _l10n_vn_collect_main_lines(self, report, options):
        """Return a dict mapping XSD ct field names to integer values, sourced from the report's expression totals."""
        gtgt_report = self.env.ref('l10n_vn.form_01_gtgt_report')
        fresh_options = gtgt_report.get_options(previous_options={'date': options['date']})
        report_lines = gtgt_report._get_lines(fresh_options)
        col_idx = {col['expression_label']: idx for idx, col in enumerate(fresh_options['columns'])}

        line_by_code = {}
        for line_data in report_lines:
            model, record_id = gtgt_report._get_model_info_from_id(line_data.id)
            if model == 'account.report.line' and record_id:
                line_by_code[line_data.code] = line_data

        def _get(code, label):
            """Return the formatted integer amount for the report line identified by code and column label, or 0 if absent."""
            line = line_by_code.get(code)
            if not line:
                return 0
            idx = col_idx.get(label)
            if idx is None or idx >= len(line.columns):
                return 0
            try:
                return self._l10n_vn_format_amount(line.columns[idx].no_format)
            except (TypeError, ValueError):
                return 0

        return {
            'ct21': 0,  # Set to 0 as there are buying/selling activities during the period
            'ct22': _get('22', 'balance'),
            'ct23': _get('2324', 'amount_untaxed'),
            'ct24': _get('2324', 'balance'),
            'ct23a': _get('23a24a', 'amount_untaxed'),
            'ct24a': _get('23a24a', 'balance'),
            'ct25': _get('25', 'balance'),
            'ct26': _get('26', 'amount_untaxed'),
            'ct27': _get('2728', 'amount_untaxed'),
            'ct28': _get('2728', 'balance'),
            'ct29': _get('29', 'amount_untaxed'),
            'ct30': _get('3031', 'amount_untaxed'),
            'ct31': _get('3031', 'balance'),
            'ct32': _get('3233', 'amount_untaxed'),
            'ct33': _get('3233', 'balance'),
            'ct32a': _get('32a', 'amount_untaxed'),
            'ct34': _get('3435', 'amount_untaxed'),
            'ct35': _get('3435', 'balance'),
            'ct36': _get('36', 'balance'),
            'ct37': _get('37', 'balance'),
            'ct38': _get('38', 'balance'),
            'ct39a': _get('39a', 'balance'),
            'ct40a': _get('40a', 'balance'),
            'ct40b': _get('40b', 'balance'),
            'ct40': _get('40', 'balance'),
            'ct41': _get('41', 'balance'),
            'ct42': _get('42', 'balance'),
            'ct43': _get('43', 'balance'),
        }

    def _l10n_vn_collect_appendix_142(self, options):
        """Return appendix-142 payload dict, or None when there is no 8% activity in the period."""
        appendix_report = self.env.ref('l10n_vn_reports.appendix_142_report')
        appendix_handler = self.env[appendix_report.custom_handler_model_id.model]
        appendix_options = appendix_report.get_options(previous_options={'date': options['date']})

        purchases, total_base_purchases, total_vat_purchases = appendix_handler._get_month_data(
            appendix_report,
            appendix_options,
            VAT_8_PURCHASE_BASE_TAGS,
            VAT_8_PURCHASE_TAX_TAGS,
            False,
        )
        sales, total_base_sales, total_vat_sales = appendix_handler._get_month_data(
            appendix_report,
            appendix_options,
            VAT_8_SALE_BASE_TAGS,
            VAT_8_SALE_TAX_TAGS,
            True,
        )

        if not purchases and not sales:
            return None

        def _row_amounts(row):
            cols = row.get('columns', {}).get(0, {})
            return {
                'name': row['name'] or '',
                'base': self._l10n_vn_format_amount(cols.get('base_amount')),
                'vat': self._l10n_vn_format_amount(cols.get('vat_amount')),
            }

        purchase_rows = [_row_amounts(r) for r in purchases]
        sale_rows = [_row_amounts(r) for r in sales]
        total_vat_purchases = self._l10n_vn_format_amount(total_vat_purchases)
        total_vat_sales = self._l10n_vn_format_amount(total_vat_sales)

        return {
            'purchases': purchase_rows,
            'purchases_total_base': self._l10n_vn_format_amount(total_base_purchases),
            'purchases_total_vat': total_vat_purchases,
            'sales': sale_rows,
            'sales_total_base': self._l10n_vn_format_amount(total_base_sales),
            'sales_total_vat': total_vat_sales,
            'difference': total_vat_sales - total_vat_purchases,
        }

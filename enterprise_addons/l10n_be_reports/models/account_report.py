# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import calendar
import io
import re
import zipfile
from markupsafe import Markup

from odoo import models, _
from odoo.exceptions import RedirectWarning, UserError
from odoo.tools import BinaryBytes
from odoo.tools.business_data import split_vat


def _raw_phonenumber(phonenumber):
    return re.sub("[^+0-9]", "", phonenumber)[:20]

def _get_xml_export_representative_node(report):
    """ The <Representative> node is common to XML exports made for VAT Listing, VAT Intra,
    and tax declaration. It is used in case the company isn't submitting its report directly,
    but through an external accountant.

    :return: The string containing the complete <Representative> node or an empty string,
             in case no representative has been configured.
    """
    representative = report.env.company.account_representative_id
    if representative:
        country_from_vat, vat_no = split_vat(representative.vat, default_country_code=representative.country_id.code or 'be')
        country = report.env['res.country'].search([('code', '=', country_from_vat)], limit=1)
        phone = representative.phone or ''
        node_values = {
            'vat': vat_no,
            'name': representative.name,
            'street': "%s %s" % (representative.street or "", representative.street2 or ""),
            'zip': representative.zip,
            'city': representative.city,
            'country_code': (country or representative.country_id).code,
            'email': representative.email,
            'phone': _raw_phonenumber(phone)
        }

        missing_fields = [k for k, v in node_values.items() if not v or v == ' ']
        if missing_fields:
            message = _('Some fields required for the export are missing. Please specify them.')
            action = {
                'name': _("Company: %s", representative.name),
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'res.partner',
                'views': [[False, 'form']],
                'target': 'new',
                'res_id': representative.id,
                'context': {'create': False},
            }
            button_text = _('Specify')
            additional_context = {'required_fields': missing_fields}
            raise RedirectWarning(message, action, button_text, additional_context)

        return Markup("""<ns2:Representative>
    <RepresentativeID identificationType="NVAT" issuedBy="%(country_code)s">%(vat)s</RepresentativeID>
    <Name>%(name)s</Name>
    <Street>%(street)s</Street>
    <PostCode>%(zip)s</PostCode>
    <City>%(city)s</City>
    <CountryCode>%(country_code)s</CountryCode>
    <EmailAddress>%(email)s</EmailAddress>
    <Phone>%(phone)s</Phone>
</ns2:Representative>""") % node_values

    return Markup()


class L10n_BeTaxReportHandler(models.AbstractModel):
    _name = 'l10n_be.tax.report.handler'
    _inherit = ['account.tax.report.handler']
    _description = 'Belgian Tax Report Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)

        # Export options set by the return submission wizard ; we need them here so that they're not reset in
        # the pdf generation, when calling _get_options()
        options.update({
            'l10n_be_closing_vat_return': previous_options.get('l10n_be_closing_vat_return'),
            'closing_entry': previous_options.get('closing_entry'),
            'ask_restitution': previous_options.get('ask_restitution'),
            'client_nihil': previous_options.get('client_nihil'),
        })

        options['custom_display_config']['pdf_export'] = {'pdf_export_filters': 'l10n_be_reports.pdf_export_filters'}

    def open_account_report_sales(self, options):
        action = self.env['ir.actions.actions']._for_xml_id('account_reports.action_account_report_sales')
        action['params'] = {
            'options': options,
            'ignore_session': True,
        }

        return action

    def export_tax_report_to_xml(self, options):
        report = self.env['account.report'].browse(options['report_id'])
        country_from_vat, vat_no = split_vat(report.get_vat_for_export(options))
        sender_company = report._get_sender_company_for_export(options)
        default_address = sender_company.partner_id.address_get()
        address = self.env['res.partner'].browse(default_address.get("default")) or sender_company.partner_id

        if not address.email:
            raise UserError(_('No email address associated with company %s.', sender_company.name))

        if not address.phone:
            raise UserError(_('No phone associated with company %s.', sender_company.name))

        # Compute xml
        issued_by = vat_no
        dt_from = options['date'].get('date_from')
        dt_to = options['date'].get('date_to')
        send_ref = str(sender_company.partner_id.id) + str(dt_from[5:7]) + str(dt_to[:4])
        starting_month = dt_from[5:7]
        ending_month = dt_to[5:7]
        quarter = str(((int(starting_month) - 1) // 3) + 1)

        date_from = dt_from[0:7] + '-01'
        date_to = dt_to[0:7] + '-' + str(calendar.monthrange(int(dt_to[0:4]), int(ending_month))[1])

        deduction_text = self._get_deduction_text(options)

        complete_vat = (country_from_vat or (address.country_id and address.country_id.code or "")) + vat_no
        file_data = {
            'issued_by': issued_by,
            'vat_no': complete_vat,
            'only_vat': vat_no,
            # Company name can contain only latin characters
            'company_name': sender_company.name,
            'address': "%s %s" % (address.street or "", address.street2 or ""),
            'post_code': address.zip or "",
            'city': address.city or "",
            'country_code': address.country_id and address.country_id.code or "",
            'email': address.email or "",
            'phone': _raw_phonenumber(address.phone),
            'send_ref': send_ref,
            'quarter': quarter,
            'month': starting_month,
            'year': str(dt_to[:4]),
            'client_nihil': options.get('client_nihil', False) and 'YES' or 'NO',
            'ask_restitution': options.get('ask_restitution', False) and 'YES' or 'NO',
            'comment': options.get('comment'),
            'prorata_deduction': deduction_text,
            'representative_node': _get_xml_export_representative_node(report),
        }

        rslt = Markup(f"""<?xml version="1.0"?>
<ns2:VATConsignment xmlns="http://www.minfin.fgov.be/InputCommon" xmlns:ns2="http://www.minfin.fgov.be/VATConsignment" VATDeclarationsNbr="1">
    %(representative_node)s
    <ns2:VATDeclaration SequenceNumber="1" DeclarantReference="%(send_ref)s">""") % file_data

        rslt += Markup(f"""<ns2:Declarant>
            <VATNumber xmlns="http://www.minfin.fgov.be/InputCommon">%(only_vat)s</VATNumber>
            <Name>%(company_name)s</Name>
            <Street>%(address)s</Street>
            <PostCode>%(post_code)s</PostCode>
            <City>%(city)s</City>
            <CountryCode>%(country_code)s</CountryCode>
            <EmailAddress>%(email)s</EmailAddress>
            <Phone>%(phone)s</Phone>
        </ns2:Declarant>
        <ns2:Period>
            {"<ns2:Quarter>%(quarter)s</ns2:Quarter>" if starting_month != ending_month else "<ns2:Month>%(month)s</ns2:Month>"}
            <ns2:Year>%(year)s</ns2:Year>
        </ns2:Period>
        %(prorata_deduction)s
        <ns2:Data>""") % file_data

        grids_list = []
        currency_id = self.env.company.currency_id

        options = report.get_options({'no_format': True, 'date': {'date_from': date_from, 'date_to': date_to}, 'filter_unfold_all': True, 'export_mode': 'file'})
        lines = report._get_lines(options)

        # Create a mapping between report line ids and actual grid names
        non_compound_rep_lines = report.line_ids.expression_ids.filtered(
                lambda x: x.formula not in {'48s44', '48s46L', '48s46T', '-46L', '-46T'})
        lines_grids_map = {
            expr.report_line_id.id: expr.formula.split('.')[0].replace('c', '') for expr in non_compound_rep_lines
        }
        lines_grids_map[self.env.ref('l10n_be.tax_report_title_operations_sortie_46').id] = '46'
        lines_grids_map[self.env.ref('l10n_be.tax_report_title_operations_sortie_48').id] = '48'
        lines_grids_map[self.env.ref('l10n_be.tax_report_line_71').id] = '71'
        lines_grids_map[self.env.ref('l10n_be.tax_report_line_72').id] = '72'
        colname_to_idx = {col['expression_label']: idx for idx, col in enumerate(options.get('columns', []))}

        # Iterate on the report lines, using this mapping
        for line in lines:
            model, line_id = report._parse_line_id(line.id)[-1][1:]
            if (
                    model == 'account.report.line'
                    and line_id in lines_grids_map
                    and not currency_id.is_zero(line.columns[colname_to_idx['balance']].no_format)
            ):
                grids_list.append((lines_grids_map[line_id].lstrip('-'),
                                   line.columns[colname_to_idx['balance']].no_format))

        # We are ignoring all grids that have 0 as values, but the belgian government always require a value at
        # least in either the grid 71 or 72. So in the case where both are set to 0, we are adding the grid 71 in the
        # xml with 0 as a value.
        if len([item for item in grids_list if item[0] == '71' or item[0] == '72']) == 0:
            grids_list.append(('71', 0))

        # Government expects a value also in grid '00' in case of vat_unit
        if options.get('tax_unit') and options.get('tax_unit') != 'company_only' and len([item for item in grids_list if item[0] == '00']) == 0:
            grids_list.append(('00', 0))

        grids_list = sorted(grids_list, key=lambda a: a[0])
        for code, amount in grids_list:
            # These tags are carried over the next period, they should not appear in the xml if amount is below 0
            if code not in ('81', '82', '83', '86', '87', '88') or currency_id.compare_amounts(amount, 0) == 1:
                grid_amount_data = {
                    'code': code,
                    'amount': '%.2f' % amount,
                }
                rslt += Markup("""
                <ns2:Amount GridNumber="%(code)s">%(amount)s</ns2:Amount>""") % grid_amount_data

        rslt += Markup("""
        </ns2:Data>
        <ns2:ClientListingNihil>%(client_nihil)s</ns2:ClientListingNihil>
        <ns2:Ask Restitution="%(ask_restitution)s"/>
        """) % file_data

        if file_data['comment']:
            rslt += Markup("""
        <ns2:Comment>%(comment)s</ns2:Comment>
            """) % file_data

        rslt += Markup("""
    </ns2:VATDeclaration>
</ns2:VATConsignment>
        """)

        return {
            'file_name': report.get_default_report_filename(options, 'xml'),
            'file_content': rslt.encode(),
            'file_type': 'xml',
        }

    def _get_deduction_text(self, options):
        # To Override to include deductions in XML
        deduction_dict = options.get('prorata_deduction', {})
        if not deduction_dict.get('prorata'):
            return ''

        return self.env['ir.qweb']._render('l10n_be_reports.vat_export_prorata', deduction_dict)

    def _customize_warnings(self, report, options, all_column_groups_expression_totals, warnings):

        def val(expr_totals, code):
            return expr_totals[expr_map[code]]['value']

        def sum_vals(expr_totals, *codes):
            return sum(val(expr_totals, c) for c in codes)

        def evaluate(check):
            return all(check(expr_totals) for expr_totals in all_column_groups_expression_totals.values())

        super()._customize_warnings(report, options, all_column_groups_expression_totals, warnings)

        expr_map = {
            line.code: line.expression_ids.filtered(lambda x: x.label == 'balance')
            for line in report.line_ids
            if line.code
        }
        currency = self.env.company.currency_id
        rounding_tolerance = 62.0

        checks = [
            (
                # Code 13
                self.env._("Negative amounts not allowed"),
                lambda e: all(
                    currency.compare_amounts(val(e, code), 0.0) >= 0
                    for code, expr in expr_map.items()
                    if code not in ('c81', 'c82', 'c83', 'c86', 'c87', 'c88')  # carryover lines
                ),
            ),
            (
                # Code C
                self.env._('[55] > 0 if [86] > 0 or [88] > 0'),
                lambda e: currency.compare_amounts(val(e, 'c55'), 0.0) > 0
                if currency.compare_amounts(val(e, 'c86'), 0.0) > 0 or currency.compare_amounts(val(e, 'c88'), 0.0) > 0 else True,
            ),
            (
                # Code D
                self.env._('[56] + [57] > 0 if [87] > 0'),
                lambda e: currency.round(sum_vals(e, 'c56', 'c57')) > 0 if val(e, 'c87') > 0 else True,
            ),
            (
                # Code O
                '[01] * 6% + [02] * 12% + [03] * 21% = [54] ± 62',
                lambda e: currency.compare_amounts(rounding_tolerance, abs(
                    val(e, 'c01') * 0.06 +
                    val(e, 'c02') * 0.12 +
                    val(e, 'c03') * 0.21 -
                    val(e, 'c54')
                )) >= 0,
            ),
            (
                # Code P
                '([84] + [86] + [88]) * 21% >= [55] - 62',
                lambda e: currency.compare_amounts(sum_vals(e, 'c84', 'c86', 'c88') * 0.21, val(e, 'c55') - rounding_tolerance) >= 0,
            ),
            (
                # Code Q
                '([85] + [87]) * 21% >= ([56] + [57]) - 62',
                lambda e: currency.compare_amounts(sum_vals(e, 'c85', 'c87') * 0.21, sum_vals(e, 'c56', 'c57') - rounding_tolerance) >= 0,
            ),
            (
                # Code S
                '([81] + [82] + [83] + [84] + [85]) * 50% >= [59]',
                lambda e: currency.compare_amounts(sum_vals(e, 'c81', 'c82', 'c83', 'c84', 'c85') * 0.5, val(e, 'c59')) >= 0,
            ),
            (
                # Code T
                '[85] * 21% >= [63] - 62',
                lambda e: currency.compare_amounts(val(e, 'c85') * 0.21, val(e, 'c63') - rounding_tolerance) >= 0,
            ),
            (
                # Code U
                '[49] * 21% >= [64] - 62',
                lambda e: currency.compare_amounts(val(e, 'c49') * 0.21, val(e, 'c64') - rounding_tolerance) >= 0,
            ),
            (
                # Code AC
                self.env._('[88] < ([81] + [82] + [83] + [84]) * 100 if [88] > 99,999'),
                lambda e: currency.compare_amounts(val(e, 'c88'), sum_vals(e, 'c81', 'c82', 'c83', 'c84') * 100) == -1
                if currency.compare_amounts(val(e, 'c88'), 99_999) > 0 else True,
            ),
            (
                # Code AD
                self.env._('[44] < ([00] + [01] + [02] + [03] + [45] + [46] + [47] + [48] + [49]) * 200 if [44] > 99,999'),
                lambda e: currency.compare_amounts(val(e, 'c44'), sum_vals(e, 'c00', 'c01', 'c02', 'c03', 'c45', 'c46', 'c47', 'c48', 'c49') * 200) == -1
                if currency.compare_amounts(val(e, 'c44'), 99_999) > 0 else True,
            ),
        ]

        failed_controls = [name for name, check in checks if not evaluate(check)]
        if failed_controls:
            warnings['l10n_be_reports.tax_report_warning_checks'] = {
                'failed_controls': failed_controls,
                'alert_type': 'danger',
            }

    def generate_zip_file_from_intervat(self, options):
        """ Fetch pdf and xml file from intervat for one vat declaration.

        :return: Zip file with both pdf and xml file of the declaration.
        """
        tax_return = self.env['account.return'].browse(options['return_id'])
        vat_declaration = self.env['l10n_be.vat.declaration'].search([
            ('return_id', '=', tax_return.id),
            ('rectification_declaration_id', '=', False),
        ], limit=1)
        if not vat_declaration:
            raise UserError(self.env._("No VAT declaration found for this period."))

        file_name = f"intervat_{options['date']['date_from']}_{options['date']['date_to']}"
        if not vat_declaration.declaration_file:
            pdf_file = vat_declaration.return_id.company_id._l10n_be_fetch_document_from_myminfin(vat_declaration.pdf_ref)
            xml_file = vat_declaration.return_id.company_id._l10n_be_fetch_document_from_myminfin(vat_declaration.xml_ref)

            with io.BytesIO() as buffer:
                with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as zipfile_obj:
                    zipfile_obj.writestr(f"{file_name}.pdf", pdf_file)
                    zipfile_obj.writestr(f"{file_name}.xml", xml_file)

                file = {
                    'file_name': f"{file_name}.zip",
                    'file_content': buffer.getvalue(),
                    'file_type': 'zip',
                }
                tax_return._add_attachment(file)
                vat_declaration.declaration_file = BinaryBytes(file['file_content'])

                return file

        return {
            'file_name': f"{file_name}.zip",
            'file_content': vat_declaration.declaration_file.content,
            'file_type': 'zip',
        }

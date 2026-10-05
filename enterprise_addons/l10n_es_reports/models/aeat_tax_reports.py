# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import re
import unicodedata
from collections import defaultdict
from datetime import datetime
from dateutil.relativedelta import relativedelta

import odoo.release
from odoo import fields, models, _
from odoo.exceptions import UserError
from odoo.tools import SQL, float_is_zero, frozendict
from odoo.tools.business_data import split_vat
from odoo.tools.float_utils import float_split_str

from odoo.addons.account_reports.utils.report_data_objects import AccountReportLineData


SPANISH_PROVINCES_REPORT_CODES = {
    'VI': '01',
    'AB': '02',
    'A': '03',
    'AL': '04',
    'AV': '05',
    'BA': '06',
    'PM': '07',
    'B': '08',
    'BU': '09',
    'CC': '10',
    'CA': '11',
    'CS': '12',
    'CR': '13',
    'CO': '14',
    'C': '15',
    'CU': '16',
    'GI': '17',
    'GR': '18',
    'GU': '19',
    'SS': '20',
    'H': '21',
    'HU': '22',
    'J': '23',
    'LE': '24',
    'L': '25',
    'LO': '26',
    'LU': '27',
    'M': '28',
    'MA': '29',
    'MU': '30',
    'NA': '31',
    'OR': '32',
    'O': '33',
    'P': '34',
    'GC': '35',
    'PO': '36',
    'SA': '37',
    'TF': '38',
    'S': '39',
    'SG': '40',
    'SE': '41',
    'SO': '42',
    'T': '43',
    'TE': '44',
    'TO': '45',
    'V': '46',
    'VA': '47',
    'BI': '48',
    'ZA': '49',
    'Z': '50',
    'CE': '51',
    'ME': '52',
}

# including retention tax lines as we need to get the amounts before retention
MOD_347_CUSTOM_ENGINES_DOMAINS = {
    '_report_engine_threshold_insurance_bought': [
        ('move_id.l10n_es_reports_mod347_invoice_type', '=', 'insurance'),
        ('move_id.move_type', 'in', ('in_invoice', 'in_refund', 'in_receipt')),
        '|',
        ('account_type', '=', 'liability_payable'),
        ('tax_line_id.l10n_es_type', '=', 'retencion'),
    ],

    '_report_engine_threshold_insurance_sold': [
        ('move_id.l10n_es_reports_mod347_invoice_type', '=', 'insurance'),
        ('move_id.move_type', 'in', ('out_invoice', 'out_refund', 'out_receipt')),
        '|',
        ('account_type', '=', 'asset_receivable'),
        ('tax_line_id.l10n_es_type', '=', 'retencion'),
    ],

    '_report_engine_threshold_regular_bought': [
        ('move_id.l10n_es_reports_mod347_invoice_type', '=', 'regular'),
        ('move_id.move_type', 'in', ('in_invoice', 'in_refund', 'in_receipt')),
        '|',
        ('account_type', '=', 'liability_payable'),
        ('tax_line_id.l10n_es_type', '=', 'retencion'),
    ],

    '_report_engine_threshold_regular_sold': [
        ('move_id.l10n_es_reports_mod347_invoice_type', '=', 'regular'),
        ('move_id.move_type', 'in', ('out_invoice', 'out_refund', 'out_receipt')),
        '|',
        ('account_type', '=', 'asset_receivable'),
        ('tax_line_id.l10n_es_type', '=', 'retencion'),
    ],

    '_report_engine_threshold_all_operations': [
        ('move_id.l10n_es_reports_mod347_invoice_type', '!=', None),
        '|',
        ('account_type', 'in', ('asset_receivable', 'liability_payable')),
        ('tax_line_id.l10n_es_type', '=', 'retencion'),
    ],
}

MOD_349_KEYS = ('A', 'E', 'T', 'S', 'I', 'M', 'H', 'R', 'D', 'C')

MOD_349_CUSTOM_ENGINES_SPLIT_REGEX = re.compile(r'_report_engine_modelo349_(invoice|refund)_([eatsimhrdc])')


class AccountReport(models.Model):
    _inherit = 'account.report'

    def _get_expression_audit_aml_domain(self, expression, options):
        if expression.engine == 'custom':
            # Allow auditing mod347's threshold lines (for consistency: this way all the lines of the report are audited in the same way)
            if expression.formula in MOD_347_CUSTOM_ENGINES_DOMAINS:
                return MOD_347_CUSTOM_ENGINES_DOMAINS[expression.formula]

            # Allow audition mod115 N* of recipients line
            if expression.formula in '_report_engine_number_of_recipients':
                mod115_02_tags = self.env.ref('l10n_es.mod_115_casilla_02_balance')._get_matching_tags()
                mod115_03_tags = self.env.ref('l10n_es.mod_115_casilla_03_balance')._get_matching_tags()
                return [('tax_tag_ids', 'in', (mod115_02_tags + mod115_03_tags).ids)]

            # Allow auditing mod349 summary lines
            matching = MOD_349_CUSTOM_ENGINES_SPLIT_REGEX.fullmatch(expression.formula)
            if matching:
                move_type = matching.group(1)
                return self.env[self.custom_handler_model_name]._get_modelo349_audit_aml_domain(options, move_type)

        return super()._get_expression_audit_aml_domain(expression, options)


class L10n_EsTaxReportHandler(models.AbstractModel):
    _name = 'l10n_es.tax.report.handler'
    _inherit = ['account.tax.report.handler']
    _description = 'Spanish Tax Report Custom Handler'

    def _get_mod_period_and_year(self, options):
        """
        Returns a tuple (period, year) corresponding to this specific report's periodicity options.
        """
        date_to = datetime.strptime(options['date']['date_to'], '%Y-%m-%d')

        periodicity = options.get('return_periodicity').get('periodicity')
        if periodicity == 'trimester':
            return '%01dT' % (1 + ((date_to.month - 1) // 3)), str(date_to.year)
        elif periodicity == 'year':
            return None, str(date_to.year)
        elif periodicity == 'monthly':
            return '%02d' % date_to.month, str(date_to.year)
        else:
            raise UserError(_("The chosen periodicity for the return is not available for this report."))

    def _l10n_es_normalize_string(self, string):
        """
        Removes accentuated characters from a string.
        """
        string = string and string.upper() or ''
        rslt = ''
        for char in unicodedata.normalize('NFKC', string):  # We use a normalized version of the string here so that we are sure accentuated characters are each time encoded with only one character (and not a regular character followed by a combining one)
            if char not in ('Ñ', 'Ç'):
                normalized_char = unicodedata.normalize('NFD', char)  # Decompose accents
                # Combinable accentuation characters are not supported
                filtered = ''.join(
                    c for c in normalized_char
                    if not unicodedata.combining(c) and ord(c) <= 255  # Ignore accents('combining') and character not available in ISO-8859-1 (Latin-1, unicode <= 255)
                )
                rslt += filtered
            else:
                rslt += char
        return rslt

    def _l10n_es_boe_format_string(self, string, length=-1, align='left', fill_char=' '):
        """ Formats a string so that it is BOE-compatible.
        :param string: the string to format
        :param length: the desired length of the resulting string, or -1 if there is not
        :param align: 'left' or 'right', depending on the side of the result string where string must placed (no effect if no length is given)
        :param fill_char: the character that will be used to bring the result string to a size of length (no effect if length is not specified)
        """
        rslt = self._l10n_es_normalize_string(string)
        if length > -1:
            rslt = rslt[:length]
            if align == 'left':
                rslt = rslt.ljust(length, fill_char)
            elif align == 'right':
                rslt = rslt.rjust(length, fill_char)
        return rslt

    def _l10n_es_boe_format_number(self, options, number, length=-1, decimal_places=0, signed=False, sign_neg='N', sign_pos='', in_currency=False):
        """ Formats a number to a BOE-compatible string.

        :param number: the number to format
        :param length: the desired length for the resulting string, or -1, to just use the number of characters of the number.
        :param decimal_places: the number of decimal places to use (these characters are part of the length limit)
        :param signed: whether or not the number must be signed in the resulting string
        :param sign_neg: the character to use as the first character of the resulting string if signed is True and
                         the number was negative (the resulting string will contain no additional - sign)
        :param sign_pos: same as sign_neg, but if number is positive
        :param in_currency: True iff number is expressed in company currency (and thus needs to be converted in €)
        """
        company = self.env.company

        if in_currency:
            # If number is an amount expressed in company currency, we ensure that it
            # is written in € in BOE file
            conversion_date = options['date']['date_to']
            curr_eur = self.env["res.currency"].search([('name', '=', 'EUR')], limit=1)
            number = company.currency_id._convert(number, curr_eur, company, conversion_date)

        if isinstance(number, float):
            split_number = float_split_str(abs(number), decimal_places)
            str_number = split_number[0] + split_number[1]
        else:
            str_number = str(abs(number)) + '0' * decimal_places

        negative_amount = in_currency and company.currency_id.compare_amounts(number, 0.0) == -1 or number < 0
        sign_str = signed and (negative_amount and sign_neg or sign_pos) or ''

        # Done in two parts, so that sign str is always in front of the filling characters
        return self._l10n_es_boe_format_string(sign_str) + self._l10n_es_boe_format_string(str_number, length=length - len(sign_str), align='right', fill_char='0')

    def _l10n_es_format_currency(self, content, options, length=17, signed=True):
        """Applies the most common formatting on currency casillas:
            length=17
            decimal_place=2
            in_currency=True
            signed=True
            returns the formatted currency
        """
        return self._l10n_es_boe_format_number(options, content, length=length, decimal_places=2, in_currency=True, signed=signed)

    def _l10n_es_get_blanks(self, nb_blanks):
        """ Returns a string composed of blank spaces of length nb_blanks
        """
        return ' ' * nb_blanks

    def _l10n_es_get_string_of_length(self, content, length):
        """
        Returns content as a normalized string of specified length
        by adding blank spaces to the left of the string if needed.
        """
        return self._l10n_es_normalize_string(content)[:length].ljust(length, ' ')

    def _retrieve_casilla_lines(self, report_lines):
        """ Retrieves the values of the casillas contained in report_lines, using
        the fact that these lines' names are prefixed by their number between [] to
        identify them. Returns a dictionnary, with casillas as keys and their values
        as values.
        """
        casilla_pattern = re.compile(r'\[(?P<casilla>.*)\]')
        rslt = {}
        for line in report_lines:
            matcher = casilla_pattern.match(line.name)
            if matcher:
                casilla = matcher.group('casilla')
                casilla_value = line.columns[0].no_format  # Element [0] is the current period, in case we are comparing

                rslt[casilla] = casilla_value

        return rslt

    def _retrieve_report_expression(self, options, xmlid):
        """ Retrieves the data of the report line denoted by xmlid, with respect
        to the given options.
        """
        expression = self.env.ref(xmlid)
        expression_totals = self.env['account.report'].browse(options['report_id'])._compute_expression_totals_for_each_column_group(expression._expand_aggregations(), options)
        # This considers we have but one column group
        return next(expr_total[expression]['value'] for expr_total in expression_totals.values())

    def _get_bic_and_iban(self, res_partner_bank):
        """ Convenience method returning (bic,iban) of the given account if
        this account exists, or a tuple of empty strings otherwise.
        """
        if res_partner_bank:
            return res_partner_bank.bank_bic or "", res_partner_bank.sanitized_account_number

        return '', ''

    def _retrieve_boe_manual_wizard(self, options, modelo_number):
        """
        Retrieves a BOE manual wizard object from its id, contained within the options dict.
        """
        return self.env[f'l10n_es_reports.mod{modelo_number}.submission.wizard'].browse(options['l10n_es_reports_boe_wizard_id'])

    def _call_on_partner_sublines(self, report_options, line_xml_id, fun_to_call, required_ids_set=None):
        """ Calls a function on the data of all the sublines generated by a
        groupby parameter for a report line (except the one giving the total).

        :param report_options: the options to use to generate line data
        :param line_xml_id: the xml id of the report line whose children we want to call our function on
        :param fun_to_call: the function to call on sublines. It must take only one argument, the data dictionary of the subline.
        :param required_ids_set: a set containing ids on which we want fun_to_call to be called.
                                 This is used to generate data for models that are not present
                                 in the grouped line displayed on the report. (this can for example
                                 happen if they have no operation in this year; but
                                 some data to be added into BOE make in necessary to still include
                                 them in the file). This set will be modified by the function.
        """
        if required_ids_set is None:
            required_ids_set = set()
        rslt = self._l10n_es_boe_format_string('')
        report = self.env['account.report'].browse(report_options['report_id'])
        report_line = self.env.ref(line_xml_id)
        line_dict_id = report._get_generic_line_id('account.report.line', report_line.id)
        for subline in report._report_expand_unfoldable_line_with_groupby(line_dict_id, report_line.groupby, report_options, None, 0):
            subline_model, subline_model_id = report._get_model_info_from_id(subline.id)

            if subline_model == 'res.partner':
                rslt += fun_to_call({'line_data': subline, 'line_xml_id': line_xml_id, 'report_options': report_options})
                if subline_model_id in required_ids_set:
                    required_ids_set.remove(subline_model_id)

        for element in required_ids_set:  # These elements are the ones for wich no line was generated, but that were into the original required ids set. So, we still treat them.
            rslt += fun_to_call({
                'line_data': AccountReportLineData(id=report._get_generic_line_id('res.partner', element)),
                'line_xml_id': line_xml_id,
                'report_options': report_options
            })

        return rslt

    def _get_partner_subline(self, report_options, line_xml_id, partner_id):
        """ Returns the data of a subline generated by a groupby parameter, if its
        'id' (i.e. the actual id of the model denoted by groupby represented by the
        line) is equal to a given value.

        :param report_options: the options to use to generate data
        :param line_xml_id: the xml id of the parent line
        :param sub_line_id: the id of the "grouped by" model corresponding to the subline we want to retrieve
        """
        report = self.env['account.report'].browse(report_options['report_id'])
        report_line = self.env.ref(line_xml_id)
        line_dict_id = report._get_generic_line_id('account.report.line', report_line.id)
        for subline in report._report_expand_unfoldable_line_with_groupby(line_dict_id, report_line.groupby, report_options, None, 0):
            subline_model, model_id = report._get_model_info_from_id(subline['id'])
            if subline_model == 'res.partner' and model_id == partner_id:
                return subline

    def _extract_tin(self, partner, error_if_no_tin=True):
        if not partner.vat:
            if error_if_no_tin:
                raise UserError(_(
                    "No TIN set for partner %(name)s (id %(id)d). Please define one.",
                    name=partner.name,
                    id=partner.id,
                ))
            else:
                return ''

        country_code, number = split_vat(partner.vat)
        return country_code.upper() + number

    def _extract_spanish_tin(self, partner, except_if_foreign=False):
        formatted_tin = self._extract_tin(partner, error_if_no_tin=True)
        is_spanish = formatted_tin[:2] == 'ES' or not partner.country_id or partner.country_code == 'ES'
        if is_spanish:
            return formatted_tin.removeprefix('ES')
        elif except_if_foreign:
            raise UserError(_("Reading a non-Spanish TIN as a Spanish TIN."))
        return ''

    def _generate_111_115_common_header(self, options, period, year, modelo_number):
        # Wizard with manually-entered data
        boe_wizard = self._retrieve_boe_manual_wizard(options, modelo_number)
        # Header
        current_company = self.env.company
        boe_content = [
                f"<T{modelo_number}0{year}{period}0000>",
                '<AUX>',
                self._l10n_es_get_blanks(70),   # Reserved for AEAT
                self._l10n_es_get_string_of_length(''.join(odoo.release.version.split('.')[:2]), 4),
                self._l10n_es_get_blanks(4),    # Reserved for AEAT
                self._l10n_es_get_string_of_length(self._extract_spanish_tin(current_company.partner_id), 9),
                self._l10n_es_get_blanks(213),  # Reserved for AEAT
                '</AUX>',
                f"<T{modelo_number}01000>",
                self._l10n_es_get_blanks(1),
                boe_wizard.declaration_type,
                self._l10n_es_get_string_of_length(self._extract_spanish_tin(current_company.partner_id), 9),
                self._l10n_es_get_string_of_length(current_company.name, 60),
                self._l10n_es_get_blanks(20),   # We keep the name of the declaring party blank here, as it is a company
                str(year),
                str(period),
            ]
        return ''.join(boe_content)

    def _l10n_es_common_count_rows(self, options, current_groupby, count_field, domain):
        report = self.env['account.report'].browse(options['report_id'])
        if current_groupby:
            report._check_groupby_fields([current_groupby])

        query = report._get_report_query(options, 'strict_range', domain=domain)
        groupby_field = self.env['account.move.line']._field_to_sql('account_move_line', current_groupby, query) if current_groupby else SQL()
        select_count_field = self.env['account.move.line']._field_to_sql('account_move_line', count_field, query)

        query = SQL(
            """
                SELECT
                    %(select_from_groupby)s
                    COUNT(DISTINCT %(select_count_field)s) AS count_rows
                FROM %(tables)s
                WHERE %(search_condition)s
                %(groupby_clause)s
                %(orderby_clause)s
            """,
            select_from_groupby=SQL('%s AS grouping_key,', groupby_field) if groupby_field else SQL(''),
            select_count_field=select_count_field,
            tables=query.from_clause,
            search_condition=query.where_clause,
            groupby_clause=SQL('GROUP BY %s', groupby_field) if groupby_field else SQL(''),
            orderby_clause=SQL('ORDER BY %s', groupby_field) if groupby_field else SQL(''),
        )
        self.env.cr.execute(query)
        query_res_lines = self.env.cr.dictfetchall()

        if not current_groupby:
            count_rows = query_res_lines[0]['count_rows'] if query_res_lines else 0
            return {'count_rows': count_rows, 'has_sublines': count_rows > 0}

        return [
            (
                line['grouping_key'], {
                    'count_rows': line['count_rows'],
                    'has_sublines': bool(line['count_rows'] > 0)
                }
            )
            for line in query_res_lines
        ]

    def action_audit_cell(self, options, params):
        report = self.env['account.report'].browse(options['report_id'])
        action = report.action_audit_cell(options, params)

        report_line = self.env['account.report.line'].browse(params['report_line_id'])
        expression_label = params['expression_label']
        expression = report_line.expression_ids.filtered(lambda x: x.label == expression_label)

        group_by_partner_formulas = {
            '_report_engine_threshold_all_operations',
            '_report_engine_number_of_recipients',
        }
        if expression.engine == 'custom' and expression.formula in group_by_partner_formulas:
            # the domain used for filtering the records showed is added in _get_expression_audit_aml_domain
            action['context']['search_default_group_by_partner'] = True

        return action


class L10n_EsMod111TaxReportHandler(models.AbstractModel):
    _name = 'l10n_es.mod111.tax.report.handler'
    _inherit = ['l10n_es.tax.report.handler']
    _description = 'Spanish Tax Report Custom Handler (Mod111)'

    def export_boe(self, options):
        period, year = self._get_mod_period_and_year(options)
        boe_wizard = self._retrieve_boe_manual_wizard(options, 111)
        header = self._generate_111_115_common_header(options, period, year, 111)
        report = self.env['account.report'].browse(options['report_id'])
        report_lines = report._get_lines(options)
        casilla_lines_map = self._retrieve_casilla_lines(report_lines)
        dummy, iban = self._get_bic_and_iban(boe_wizard.partner_bank_id)
        complementary_declaration = boe_wizard.complementary_declaration and 'X' or ' '
        previous_report_number = boe_wizard.complementary_declaration and boe_wizard.previous_report_number or ''

        # Content of the report
        boe_content = [
            header,
            self._l10n_es_boe_format_number(options, casilla_lines_map['01'], length=8, signed=True),
            self._l10n_es_format_currency(casilla_lines_map['02'], options),
            self._l10n_es_format_currency(casilla_lines_map['03'], options),
            self._l10n_es_boe_format_number(options, casilla_lines_map['04'], length=8, signed=True),
            self._l10n_es_format_currency(casilla_lines_map['05'], options),
            self._l10n_es_format_currency(casilla_lines_map['06'], options),
            self._l10n_es_boe_format_number(options, casilla_lines_map['07'], length=8, signed=True),
            self._l10n_es_format_currency(casilla_lines_map['08'], options),
            self._l10n_es_format_currency(casilla_lines_map['09'], options),
            self._l10n_es_boe_format_number(options, casilla_lines_map['10'], length=8, signed=True),
            self._l10n_es_format_currency(casilla_lines_map['11'], options),
            self._l10n_es_format_currency(casilla_lines_map['12'], options),
            self._l10n_es_boe_format_number(options, casilla_lines_map['13'], length=8, signed=True),
            self._l10n_es_format_currency(casilla_lines_map['14'], options),
            self._l10n_es_format_currency(casilla_lines_map['15'], options),
            self._l10n_es_boe_format_number(options, casilla_lines_map['16'], length=8, signed=True),
            self._l10n_es_format_currency(casilla_lines_map['17'], options),
            self._l10n_es_format_currency(casilla_lines_map['18'], options),
            self._l10n_es_boe_format_number(options, casilla_lines_map['19'], length=8, signed=True),
            self._l10n_es_format_currency(casilla_lines_map['20'], options),
            self._l10n_es_format_currency(casilla_lines_map['21'], options),
            self._l10n_es_boe_format_number(options, casilla_lines_map['22'], length=8, signed=True),
            self._l10n_es_format_currency(casilla_lines_map['23'], options),
            self._l10n_es_format_currency(casilla_lines_map['24'], options),
            self._l10n_es_boe_format_number(options, casilla_lines_map['25'], length=8, signed=True),
            self._l10n_es_format_currency(casilla_lines_map['26'], options),
            self._l10n_es_format_currency(casilla_lines_map['27'], options),
            self._l10n_es_format_currency(casilla_lines_map['28'], options),
            self._l10n_es_format_currency(casilla_lines_map['29'], options),
            self._l10n_es_format_currency(casilla_lines_map['30'], options),
            complementary_declaration,
            self._l10n_es_get_string_of_length(previous_report_number, 13),
            self._l10n_es_get_blanks(1),    # Reserved for AEAT
            self._l10n_es_get_string_of_length(iban, 34),
            self._l10n_es_get_blanks(389),  # Reserved for AEAT
            self._l10n_es_get_blanks(13),   # Reserved for AEAT
            # We close the tags... (They have been opened by _generate_111_115_common_header)
            '</T11101000>',
            f"</T1110{year}{period}0000>",
            ]
        return {
            'file_name': report.get_default_report_filename(options, 'txt'),
            'file_content': ''.join(boe_content).encode(),
            'file_type': 'txt',
        }


class L10n_EsMod115TaxReportHandler(models.AbstractModel):
    _name = 'l10n_es.mod115.tax.report.handler'
    _inherit = ['l10n_es.tax.report.handler']
    _description = 'Spanish Tax Report Custom Handler (Mod115)'

    def export_boe(self, options):
        boe_wizard = self._retrieve_boe_manual_wizard(options, 115)
        period, year = self._get_mod_period_and_year(options)

        header = self._generate_111_115_common_header(options, period, year, 115)
        report = self.env['account.report'].browse(options['report_id'])
        report_lines = report._get_lines(options)
        casilla_lines_map = self._retrieve_casilla_lines(report_lines)
        complementary_declaration = boe_wizard.complementary_declaration and 'X' or ' '
        previous_report_number = boe_wizard.complementary_declaration and boe_wizard.previous_report_number or ''
        dummy, iban = self._get_bic_and_iban(boe_wizard.partner_bank_id)

        # Content of the report
        boe_content = [
            header,
            self._l10n_es_boe_format_number(options, casilla_lines_map['01'], length=15, signed=True),
            self._l10n_es_format_currency(casilla_lines_map['02'], options),
            self._l10n_es_format_currency(casilla_lines_map['03'], options),
            self._l10n_es_format_currency(casilla_lines_map['04'], options),
            self._l10n_es_format_currency(casilla_lines_map['05'], options),
            complementary_declaration,
            self._l10n_es_get_string_of_length(previous_report_number, 13),
            self._l10n_es_get_string_of_length(iban, 34),
            self._l10n_es_get_blanks(236),   # Reserved for AEAT
            self._l10n_es_get_blanks(13),   # Reserved for AEAT
            # We close the tags... (They have been opened by _generate_111_115_common_header)
            '</T11501000>',
            f'</T1150{year}{period}0000>',
        ]

        return {
            'file_name': report.get_default_report_filename(options, 'txt'),
            'file_content': ''.join(boe_content).encode(),
            'file_type': 'txt',
        }

    def _report_engine_number_of_recipients(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        mod115_02_tags = self.env.ref('l10n_es.mod_115_casilla_02_balance')._get_matching_tags()
        mod115_03_tags = self.env.ref('l10n_es.mod_115_casilla_03_balance')._get_matching_tags()
        domain = [('tax_tag_ids', 'in', (mod115_02_tags + mod115_03_tags).ids)]
        return {next(iter(formulas_dict.values())):  self._l10n_es_common_count_rows(options, current_groupby, 'partner_id', domain)}


class L10n_EsMod130TaxReportHandler(models.AbstractModel):
    _name = 'l10n_es.mod130.tax.report.handler'
    _inherit = ['l10n_es.tax.report.handler']
    _description = 'Spanish Tax Report Custom Handler (Mod130)'

    def export_boe(self, options):
        boe_wizard = self._retrieve_boe_manual_wizard(options, 130)
        period, year = self._get_mod_period_and_year(options)
        # Legal requirement for the export of boe file for modelo 130
        boe_modelo_id = 'T13001000'

        rslt = f"<{boe_modelo_id}>"
        report = self.env['account.report'].browse(options['report_id'])
        report_lines = report._get_lines(options)
        casilla_lines_map = self._retrieve_casilla_lines(report_lines)

        rslt += self._l10n_es_boe_format_string(' ' * 1)
        rslt += self._l10n_es_boe_format_string(f'{boe_wizard.declaration_type}')
        rslt += self._l10n_es_boe_format_string(boe_wizard.taxpayer_id or 'n/a', length=9)
        rslt += self._l10n_es_boe_format_string(boe_wizard.taxpayer_last_name or 'n/a', length=60)
        rslt += self._l10n_es_boe_format_string(boe_wizard.taxpayer_first_name or 'n/a', length=20)
        rslt += self._l10n_es_boe_format_string(year, length=4)
        rslt += self._l10n_es_boe_format_string(period, length=2)

        # Content of the report
        for casilla in casilla_lines_map.values():
            rslt += self._l10n_es_format_currency(casilla, options)

        rslt += self._l10n_es_boe_format_string(boe_wizard.complementary_declaration and 'X' or ' ')
        rslt += self._l10n_es_boe_format_string(boe_wizard.complementary_declaration and boe_wizard.previous_report_number or '', length=13)
        _, iban = self._get_bic_and_iban(boe_wizard.partner_bank_id)
        rslt += self._l10n_es_boe_format_string(iban, length=34)
        rslt += self._l10n_es_boe_format_string(' ' * 96)
        rslt += self._l10n_es_boe_format_string(' ' * 13)

        rslt += self._l10n_es_boe_format_string(f'</{boe_modelo_id}>')

        return {
            'file_name': report.get_default_report_filename(options, 'txt'),
            'file_content': rslt.encode(),
            'file_type': 'txt',
        }


class L10n_EsMod303TaxReportHandler(models.AbstractModel):
    _name = 'l10n_es.mod303.tax.report.handler'
    _inherit = 'l10n_es.tax.report.handler'
    _description = 'Spanish Tax Report Custom Handler (Mod303)'

    def export_boe(self, options):
        boe_wizard = self._retrieve_boe_manual_wizard(options, 303)
        period, year = self._get_mod_period_and_year(options)
        report = self.env['account.report'].browse(options['report_id'])
        report_lines = report._get_lines(options)
        casilla_lines_map = self._retrieve_casilla_lines(report_lines)
        current_company = self.env.company
        did_page = ''
        if options['date']['date_from'] >= '2023-01-01':
            did_page = self._generate_page_did(report, boe_wizard, options, current_company, period, year, casilla_lines_map)

        # Header
        boe_content = [
            f'<T3030{year}{period}0000>',
            '<AUX>',
            self._l10n_es_get_blanks(70),
            self._l10n_es_get_string_of_length(''.join(odoo.release.version.split('.')[:2]), 4),
            self._l10n_es_get_blanks(4),
            self._l10n_es_get_string_of_length(self._extract_spanish_tin(current_company.partner_id), 9),
            self._l10n_es_get_blanks(213),
            '</AUX>',
            # We don't need page 2 and 4 (specified in AEAT doc)
            self._generate_page1(report, boe_wizard, options, current_company, period, year, casilla_lines_map),
            self._generate_page3(report, boe_wizard, options, current_company, period, year, casilla_lines_map),
            did_page,
            f'</T3030{year}{period}0000>',
        ]

        return {
            'file_name': report.get_default_report_filename(options, 'txt'),
            'file_content': ''.join(boe_content).encode(),
            'file_type': 'txt',
        }

    def _generate_page1(self, report, boe_wizard, options, current_company, period, year, casilla_lines_map):
        monthly_return = boe_wizard.monthly_return and '1' or '2'
        exonerated_from_mod_390 = boe_wizard._get_exonerated_from_mod_390_2021_value(period)
        if exonerated_from_mod_390 == 1:
            profit_and_loss_report = self.env.ref('l10n_es_reports.financial_report_es_profit_and_loss')
            end_date = fields.Date.from_string(options['date']['date_to'])
            transactions_volume_options = profit_and_loss_report.get_options({
                'date': {
                    'date_from': '%s-01-01' % end_date.year,
                    'date_to': '%s-12-31' % end_date.year,
                },
            })
            transactions_volume = self._retrieve_report_expression(transactions_volume_options, 'l10n_es_reports.es_profit_and_loss_line_1_balance')
            annual_volume_indicator = current_company.currency_id.is_zero(transactions_volume) and 2 or 1
        else:
            annual_volume_indicator = 0

        casillas_regulation = defaultdict(str)
        casillas_regulation['17'] = '00050'
        eof_empty_spaces = 600

        if options['date']['date_from'] >= '2023-01-01':
            casillas_regulation.update({
                '150': self._l10n_es_format_currency(casilla_lines_map.get('150', 0), options, signed=False),
                '151': '00000',
                '152': self._l10n_es_format_currency(casilla_lines_map.get('152', 0), options, signed=False),
                '153': self._l10n_es_format_currency(casilla_lines_map.get('153', 0), options),
                '154': '00500',
                '156': self._l10n_es_format_currency(casilla_lines_map.get('156', 0), options),
                '157': '00175',  # Casilla 157 is constant
                '158': self._l10n_es_format_currency(casilla_lines_map.get('158', 0), options),
            })
        if options['date']['date_from'] >= '2024-10-01':
            casillas_regulation.update({
                '17': '00100',
                '154': '00750',
                '165': self._l10n_es_format_currency(casilla_lines_map.get('153', 0), options, signed=False),
                '166': '00200',
                '167': self._l10n_es_format_currency(casilla_lines_map.get('167', 0), options, signed=False),
                '168': self._l10n_es_format_currency(casilla_lines_map.get('168', 0), options, signed=False),
                '169': '00026',
            })
            eof_empty_spaces = 522
        if options['date']['date_from'] >= '2025-01-01':
            casillas_regulation.update({
                '17': '00000',
                '154': '00000',
                '155': self._l10n_es_format_currency(casilla_lines_map.get('155', 0), options),
                '166': '00000',
                '169': '00050',
                '170': self._l10n_es_format_currency(casilla_lines_map.get('170', 0), options, signed=False),
            })
        if int(year) >= 2026:
            eof_empty_spaces = 521

        boe_page_1 = [
            '<T30301000>',
            self._l10n_es_get_blanks(1),
            boe_wizard.declaration_type,
            self._l10n_es_get_string_of_length(self._extract_spanish_tin(current_company.partner_id), 9),
            self._l10n_es_get_string_of_length(current_company.name, 80),
            year,
            period,
            # Identification
            '2',   # Tributación exclusivamente foral => Always "no", for simplicity
            monthly_return,
            '3',
            '222222',
            self._l10n_es_get_blanks(8),
            self._l10n_es_get_blanks(1),
            str(boe_wizard._get_using_sii_2021_value()),
            str(exonerated_from_mod_390),
            str(annual_volume_indicator),
        ]

        if int(year) >= 2026:
            number = period not in ('01', '1T', '2T', '3T', '4T') and '2' or '0'
            boe_page_1 += [number]

        boe_page_1 += [
            # Casillas
            casillas_regulation['150'],
            casillas_regulation['151'],
            casillas_regulation['152'],
        ]
        if int(year) >= 2026:
            boe_page_1 += [
                casillas_regulation['165'],
                casillas_regulation['166'],
                casillas_regulation['167'],
            ]
        boe_page_1 += [
            self._l10n_es_format_currency(casilla_lines_map.get('01', 0), options, signed=False),
            '00400',  # Casilla 02 is constant
            self._l10n_es_format_currency(casilla_lines_map.get('03', 0), options, signed=False),
            casillas_regulation['153'],
            casillas_regulation['154'],
            casillas_regulation['155'],
            self._l10n_es_format_currency(casilla_lines_map.get('04'), options, signed=False),
            '01000',  # Casilla 05 is constant
            self._l10n_es_format_currency(casilla_lines_map.get('06'), options, signed=False),
            self._l10n_es_format_currency(casilla_lines_map.get('07'), options, signed=False),
            '02100',  # Casilla 08 is constant
            self._l10n_es_format_currency(casilla_lines_map.get('09'), options, signed=False),
            self._l10n_es_format_currency(casilla_lines_map.get('10'), options, signed=False),
            self._l10n_es_format_currency(casilla_lines_map.get('11'), options, signed=False),
            self._l10n_es_format_currency(casilla_lines_map.get('12'), options, signed=False),
            self._l10n_es_format_currency(casilla_lines_map.get('13'), options, signed=False),
            self._l10n_es_format_currency(casilla_lines_map.get('14'), options),
            self._l10n_es_format_currency(casilla_lines_map.get('15'), options),
            casillas_regulation['156'],
            casillas_regulation['157'],
            casillas_regulation['158'],
        ]
        if int(year) >= 2026:
            boe_page_1 += [
                casillas_regulation['168'],
                casillas_regulation['169'],
                casillas_regulation['170'],
            ]
        boe_page_1 += [
            self._l10n_es_format_currency(casilla_lines_map.get('16'), options, signed=False),
            casillas_regulation['17'],
            self._l10n_es_format_currency(casilla_lines_map.get('18'), options, signed=False),
            self._l10n_es_format_currency(casilla_lines_map.get('19'), options, signed=False),
            '00140',  # Casilla 20 is constant
            self._l10n_es_format_currency(casilla_lines_map.get('21'), options, signed=False),
            self._l10n_es_format_currency(casilla_lines_map.get('22'), options, signed=False),
            '00520',  # Casilla 23 is constant
            self._l10n_es_format_currency(casilla_lines_map.get('24'), options, signed=False),
            self._l10n_es_format_currency(casilla_lines_map.get('25'), options),
            self._l10n_es_format_currency(casilla_lines_map.get('26'), options),
            self._l10n_es_format_currency(casilla_lines_map.get('27'), options),
        ]
        for casilla in range(28, 40):
            boe_page_1.append(self._l10n_es_format_currency(casilla_lines_map.get(str(casilla)), options, signed=False))

        for casilla in range(40, 47):
            boe_page_1.append(self._l10n_es_format_currency(casilla_lines_map.get(str(casilla)), options))

        if int(year) < 2026:
            boe_page_1 += [
                casillas_regulation['165'],
                casillas_regulation['166'],
                casillas_regulation['167'],
                casillas_regulation['168'],
                casillas_regulation['169'],
                casillas_regulation['170'],
            ]
        boe_page_1 += [
            # Footer of page 1
            self._l10n_es_get_blanks(eof_empty_spaces),
            self._l10n_es_get_blanks(13),  # Reserved for AEAT
            '</T30301000>'
        ]
        return ''.join(boe_page_1)

    def _generate_page3(self, report, boe_wizard, options, current_company, period, year, casilla_lines_map):
        boe_wizard_fields = boe_wizard.fields_get()

        casillas_regulation = defaultdict(str)
        casillas_regulation.update({
            '70': self._l10n_es_format_currency(casilla_lines_map['70'], options),
            'extra_info_part1': boe_wizard.complementary_declaration and 'X' or ' ',
            'extra_info_part2': self._l10n_es_get_string_of_length(boe_wizard.complementary_declaration and boe_wizard.previous_report_number or '', 13),
            'extra_info_part3': casilla_lines_map['71'] == 0 and 'X' or ' ',
        })
        reserved_empty_chars = 600

        if options['date']['date_from'] < '2022-01-01':
            casillas_regulation.update({
                '121': self._l10n_es_boe_format_number(options, 0, length=17),
            })
            reserved_empty_chars = 445
        if options['date']['date_from'] < '2023-01-01':
            gov_giving_back = current_company.currency_id.compare_amounts(casilla_lines_map['71'], 0) == -1
            partner_bank = boe_wizard.partner_bank_id
            bic, iban = self._get_bic_and_iban(partner_bank)
            devolucion_before_2023 = \
                self._l10n_es_get_string_of_length(bic if gov_giving_back and iban and iban[:2] != 'ES' else '', 11) + \
                self._l10n_es_get_string_of_length(iban, 34) + \
                self._l10n_es_get_blanks(17)  # Reserved by AEAT

            # Devolución
            if gov_giving_back:
                devolucion_before_2023 += self._l10n_es_get_string_of_length(partner_bank.bank_name or '', 70) + \
                    self._l10n_es_get_string_of_length(' '.join([partner_bank.street or '', partner_bank.street2 or '']), 35) + \
                    self._l10n_es_get_string_of_length(partner_bank.city or '', 30) + \
                    self._l10n_es_get_string_of_length(partner_bank.country_id.code or '', 2)
                # Marca SEPA
                if iban and boe_wizard.declaration_type != 'N':
                    iban_country_code = iban[:2]
                    if iban_country_code == 'ES':
                        marca = '1'
                    elif iban_country_code in self.env.ref('base.sepa_zone').mapped('country_ids.code'):
                        marca = '2'
                    else:
                        marca = '3'
                else:
                    marca = '0'
                devolucion_before_2023 += marca
                casillas_regulation.update({'devolucion_before_2023': devolucion_before_2023})

            else:
                # All those fields must be empty if the report for the current period isn't a return (Devolución),
                # the file is rejected if they are not.
                casillas_regulation.update({'devolucion_before_2023': self._l10n_es_get_blanks(138)})

        if options['date']['date_from'] >= '2023-01-01':
            casillas_regulation.update({
                '70': self._l10n_es_format_currency(casilla_lines_map['70'], options, signed=False),  # Unsigned from 2023 on
                '109': self._l10n_es_format_currency(casilla_lines_map.get('109', 0.0), options, signed=False),
                'extra_info_part1': casilla_lines_map['71'] == 0 and 'X' or ' ',
                'extra_info_part2': boe_wizard.complementary_declaration and 'X' or ' ',
                'extra_info_part3': self._l10n_es_get_string_of_length(boe_wizard.complementary_declaration and boe_wizard.previous_report_number or '', 13),
            })
        if options['date']['date_to'] >= '2024-09-30':
            rectification_details_2024 = 'rectification_direct_debit' in boe_wizard_fields and boe_wizard.rectification_direct_debit and 'X' or ' '
            if int(year) < 2026:
                rectification_details_2024 += self._l10n_es_format_currency(casilla_lines_map.get('108', 0), options)
            rectification_details_2024 += self._l10n_es_format_currency(casilla_lines_map.get('111', 0), options)
            if int(year) < 2026:
                rectification_details_2024 += self._l10n_es_get_blanks(120)
            rectification_details_2024 += 'rectification_motive_rectifications' in boe_wizard_fields and boe_wizard.rectification_motive_rectifications and 'X' or ' '
            rectification_details_2024 += 'rectification_motive_discrepancy_adm_crit' in boe_wizard_fields and boe_wizard.rectification_motive_discrepancy_adm_crit and 'X' or ' '
            casillas_regulation.update({'rectification_details_2024': rectification_details_2024})
            reserved_empty_chars = 443 if int(year) < 2026 else 546

        boe_page_3 = [
            '<T30303000>',
            self._l10n_es_format_currency(casilla_lines_map.get('59'), options),
            self._l10n_es_format_currency(casilla_lines_map.get('60'), options),
            self._l10n_es_format_currency(casilla_lines_map.get('120'), options),
            casillas_regulation['121'],
            self._l10n_es_format_currency(casilla_lines_map.get('122'), options),
            self._l10n_es_format_currency(casilla_lines_map.get('123'), options),
            self._l10n_es_format_currency(casilla_lines_map.get('124'), options),
            self._l10n_es_format_currency(casilla_lines_map.get('62'), options),
            self._l10n_es_format_currency(casilla_lines_map.get('64'), options),
            self._l10n_es_format_currency(casilla_lines_map.get('74'), options),
            self._l10n_es_format_currency(casilla_lines_map.get('75'), options),
            self._l10n_es_boe_format_number(options, 0, length=17),  # Normally casilla 76 (Regularization of quotas art. 80.Cinco.5ª LIVA)
            self._l10n_es_format_currency(casilla_lines_map.get('46'), options),  # Should normally be casilla 64 (= sum of casillas 46, 58 and 76), but only casilla 46 is in our version of the report
            self._l10n_es_boe_format_number(options, casilla_lines_map['65'], length=5, decimal_places=2),
            self._l10n_es_format_currency(casilla_lines_map.get('66'), options),
            self._l10n_es_format_currency(casilla_lines_map.get('77'), options),
            self._l10n_es_format_currency(casilla_lines_map.get('110', 0), options, signed=False),
            self._l10n_es_format_currency(casilla_lines_map.get('78', 0), options, signed=False),
            self._l10n_es_format_currency(casilla_lines_map.get('87', 0), options, signed=False),
            self._l10n_es_format_currency(casilla_lines_map.get('68'), options),
        ]
        if int(year) >= 2026:
            boe_page_3 += [self._l10n_es_format_currency(casilla_lines_map.get('108'), options)]
        boe_page_3 += [
            self._l10n_es_format_currency(casilla_lines_map.get('69'), options),
            casillas_regulation['70'],
            casillas_regulation['109'],
        ]
        if int(year) >= 2026:
            boe_page_3 += [self._l10n_es_format_currency(0, options)]
        boe_page_3 += [
            self._l10n_es_format_currency(casilla_lines_map.get('71'), options),
            # Information about declaration
            casillas_regulation['extra_info_part1'],
            casillas_regulation['extra_info_part2'],
            casillas_regulation['extra_info_part3'],
            casillas_regulation['devolucion_before_2023'],
            casillas_regulation['rectification_details_2024'],
            self._l10n_es_get_blanks(reserved_empty_chars),  # Reserved by AEAT
            '</T30303000>',  # Footer of page 3
        ]
        return ''.join(boe_page_3)

    def _generate_page_did(self, report, boe_wizard, options, current_company, period, year, casilla_lines_map):
        partner_bank = boe_wizard.partner_bank_id
        bic, iban = self._get_bic_and_iban(partner_bank)

        # Return in foreign bank account
        if boe_wizard.declaration_type == 'X':
            return_in_foreign_bank_acc = \
                self._l10n_es_get_string_of_length(partner_bank.bank_name or '', 70) + \
                self._l10n_es_get_string_of_length(' '.join([partner_bank.street or '', partner_bank.street2 or '']), 35) + \
                self._l10n_es_get_string_of_length(partner_bank.city or '', 30) + \
                self._l10n_es_get_string_of_length(partner_bank.country_id.code or '', 2)
        else:
            return_in_foreign_bank_acc = self._l10n_es_get_blanks(137)

        # Marca SEPA
        if iban and (boe_wizard.declaration_type in ('D', 'X') or casilla_lines_map.get('111')):
            iban_country_code = iban[:2]
            if iban_country_code == 'ES':
                marca = '1'
            elif iban_country_code in self.env.ref('base.sepa_zone').mapped('country_ids.code'):
                marca = '2'
            else:
                marca = '3'
        else:
            marca = '0'

        boe_page_did = [
            '<T303DID00>',
            self._l10n_es_get_string_of_length(bic if boe_wizard.declaration_type == 'X' else '', 11),
            self._l10n_es_get_string_of_length(iban, 34),
            return_in_foreign_bank_acc,
            marca,
            self._l10n_es_get_blanks(617),  # Reserved by AEAT
            '</T303DID00>',
        ]
        return ''.join(boe_page_did)


class L10n_EsMod347TaxReportHandler(models.AbstractModel):
    _name = 'l10n_es.mod347.tax.report.handler'
    _inherit = ['l10n_es.tax.report.handler']
    _description = 'Spanish Tax Report Custom Handler (Mod347)'

    def _report_engine_threshold_insurance_sold(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        domain = MOD_347_CUSTOM_ENGINES_DOMAINS['_report_engine_threshold_insurance_sold']
        return self._custom_threshold_common(domain, next(iter(formulas_dict.values())), options, date_scope, current_groupby)

    def _report_engine_threshold_insurance_bought(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        domain = MOD_347_CUSTOM_ENGINES_DOMAINS['_report_engine_threshold_insurance_bought']
        return self._custom_threshold_common(domain, next(iter(formulas_dict.values())), options, date_scope, current_groupby)

    def _report_engine_threshold_regular_bought(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        domain = MOD_347_CUSTOM_ENGINES_DOMAINS['_report_engine_threshold_regular_bought']
        return self._custom_threshold_common(domain, next(iter(formulas_dict.values())), options, date_scope, current_groupby)

    def _report_engine_threshold_regular_sold(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        domain = MOD_347_CUSTOM_ENGINES_DOMAINS['_report_engine_threshold_regular_sold']
        return self._custom_threshold_common(domain, next(iter(formulas_dict.values())), options, date_scope, current_groupby)

    def _report_engine_threshold_all_operations(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        domain = MOD_347_CUSTOM_ENGINES_DOMAINS['_report_engine_threshold_all_operations']
        domain_options = self._custom_threshold_common_forced_domain(domain, options, date_scope)
        return {next(iter(formulas_dict.values())):  self._l10n_es_common_count_rows(domain_options, current_groupby, 'partner_id', domain)}

    def _custom_threshold_common_forced_domain(self, domain, options, date_scope):
        from_fy_dates = self.env.company.compute_fiscalyear_dates(fields.Date.from_string(options['date']['date_from']))
        to_fy_dates = self.env.company.compute_fiscalyear_dates(fields.Date.from_string(options['date']['date_to']))
        fy_options = {**options, 'date': options['date'].copy()}

        # Only adapt dates for the threshold if from and to dates belong to the same fiscal year.
        if from_fy_dates == to_fy_dates:
            fy_options['date'].update({
                'date_from': fields.Date.to_string(from_fy_dates['date_from']),
                'date_to': fields.Date.to_string(from_fy_dates['date_to']),
                'mode': 'range',
            })

        # First get all the partners that match the domain but don't reach the threshold. We'll have to exclude them
        report = self.env['account.report'].browse(options['report_id'])
        query = report._get_report_query(fy_options, date_scope, domain=domain + options.get('forced_domain', []))
        threshold_value = self._convert_threshold_to_company_currency(3005.06, options)
        partners_to_exclude_query = """
            SELECT account_move_line.partner_id
            FROM %(table_references)s
            WHERE %(search_condition)s
            AND account_move_line.partner_id IS NOT NULL
            GROUP BY account_move_line.partner_id
            HAVING
                ABS(COALESCE(SUM(%(balance_select)s)
                    FILTER (WHERE account_move_line__move_id.move_type IN ('out_invoice', 'out_refund', 'out_receipt')),
                0)) <= %(threshold_value)s
            AND
                ABS(COALESCE(SUM(%(balance_select)s)
                    FILTER (WHERE account_move_line__move_id.move_type IN ('in_invoice', 'in_refund', 'in_receipt')),
                0)) <= %(threshold_value)s
        """

        # Then, add a forced domain because it could be too long later when ast.literal_eval will be applied on it
        forced_domain = [
            *options.get('forced_domain', []),
            ('partner_id', 'not in', SQL(
                f"({partners_to_exclude_query})",
                balance_select=query.table.consolidation_balance,
                table_references=query.from_clause,
                search_condition=query.where_clause,
                threshold_value=threshold_value,
            ))
        ]
        return {**options, 'forced_domain': forced_domain}

    def _custom_threshold_common(self, domain, expressions, options, date_scope, current_groupby):
        """ Some lines of mod 347 report need to be grouped by partner, only keeping the partners whose balance for the line is above 3005.06€.
        This function serves as a common helper to the custom engines handling these lines.
        """
        report = self.env['account.report'].browse(options['report_id'])

        domain_options = self._custom_threshold_common_forced_domain(domain, options, date_scope)
        domain_formulas_dict = {str(domain): expressions}

        return report._report_engine_domain(domain_options, date_scope, domain_formulas_dict, current_groupby)

    def _convert_threshold_to_company_currency(self, threshold, options):
        """ Returns a EUR threshold to company currency, using the options' date_to for conversion
        """
        threshold_currency = self.env.ref('base.EUR')

        if not threshold_currency.active:
            raise UserError(_("Currency %s, used for a threshold in this report, is either nonexistent or inactive. Please create or activate it.", threshold_currency.name))

        company_currency = self.env.company.currency_id
        return threshold_currency._convert(threshold, company_currency, self.env.company, options['date']['date_to'])

    def _build_boe_report_options(self, options, year):
        return self.env['account.report'].browse(options['report_id']).get_options(
            previous_options={
                **options,

                'date': {'date_from': year + '-10-01', 'date_to': year + '-12-31'},

                'comparison': {
                    'date_to': year + '-09-30',
                    'periods': [
                        {'date_to': year + '-09-30', 'date_from': year + '-07-01', 'string': 'Q3 ' + year, 'mode': 'range'},
                        {'date_to': year + '-06-30', 'date_from': year + '-04-01', 'string': 'Q2 ' + year, 'mode': 'range'},
                        {'date_to': year + '-03-31', 'date_from': year + '-01-01', 'string': 'Q1 ' + year, 'mode': 'range'}
                    ],
                    'number_period': 3,
                    'string': f'Q3 {year}',
                    'filter': 'previous_period',
                    'date_from': f'{year}-07-01',
                },
            }
        )

    def _get_required_partner_ids_for_boe(self, mod_invoice_type, date_from, date_to, boe_wizard, operation_key, operation_class):
        cash_basis_manual_data = boe_wizard.cash_basis_mod347_data.filtered(lambda x: x.operation_key == operation_key and x.operation_class == operation_class)
        all_partners = cash_basis_manual_data.mapped('partner_id')
        return set(all_partners.ids)

    def _write_type2_header_record(self, current_company, boe_wizard, boe_report_options, year=None):
        if not year:
            year = str(fields.Date.today().year)

        # The header is there once for the whole year. It should use the year as date range and not quarterly. No comparison.
        yearly_options = boe_report_options.copy()
        del yearly_options['comparison']
        yearly_options = self.env['account.report'].browse(boe_report_options['report_id']).get_options(
            previous_options={
                **yearly_options,
                'date': {'date_from': '%s-01-01' % year, 'date_to': '%s-12-31' % year},
            }
        )

        rslt = self._l10n_es_boe_format_number(yearly_options, 1)
        rslt += self._l10n_es_boe_format_number(yearly_options, 347)
        rslt += self._l10n_es_boe_format_string(year, length=4)
        rslt += self._l10n_es_boe_format_string(self._extract_spanish_tin(current_company.partner_id), length=9)
        rslt += self._l10n_es_boe_format_string(current_company.name, length=40)
        rslt += self._l10n_es_boe_format_string('T')
        rslt += self._l10n_es_boe_format_string(boe_wizard.get_formatted_contact_phone(), length=9)
        rslt += self._l10n_es_boe_format_string(boe_wizard.contact_person_name, length=40)
        mod_347_boe_sequence = current_company.sudo()._get_mod_boe_sequence("347")
        rslt += self._l10n_es_boe_format_number(yearly_options, 347) + self._l10n_es_boe_format_string(mod_347_boe_sequence.next_by_id(), length=10)
        rslt += self._l10n_es_boe_format_string(boe_wizard.complementary_declaration and 'C' or ' ')
        rslt += self._l10n_es_boe_format_string(boe_wizard.substitutive_declaration and 'S' or ' ')
        rslt += self._l10n_es_boe_format_string(boe_wizard.previous_report_number or '', length=13, fill_char='0', align='right')

        declarados_count = self._retrieve_report_expression(yearly_options, 'l10n_es_reports.mod_347_statistics_operations_count_balance')
        rslt += self._l10n_es_boe_format_number(yearly_options, declarados_count, length=9)
        declarados_total = self._retrieve_report_expression(yearly_options, 'l10n_es_reports.mod_347_operations_title_balance')
        rslt += self._l10n_es_boe_format_number(yearly_options, declarados_total, length=16, decimal_places=2, signed=True, sign_pos=' ', in_currency=True)

        real_estates_data = self._get_real_estates_data(yearly_options, current_company.currency_id)
        rslt += self._l10n_es_boe_format_number(yearly_options, real_estates_data['count'], length=9)

        rslt += self._l10n_es_boe_format_number(yearly_options, real_estates_data['total'], length=16, decimal_places=2, signed=True, sign_pos=' ', in_currency=True)

        rslt += self._l10n_es_boe_format_string(' ' * 205)
        rslt += self._l10n_es_boe_format_string(' ' * 9)  # TIN of the legal representant; blank if 14 years or older
        rslt += self._l10n_es_boe_format_string(' ' * 88)
        rslt += self._l10n_es_boe_format_string(' ' * 13)  # "Sello Electronico" => for administration
        rslt += '\r\n'

        return rslt

    def _get_real_estates_data(self, boe_report_options, currency_id):
        """ Real estates are not directly supported by l10n_es_reports, but by the
        submodule l10n_es_real_estates. This function is used as a hook, so that we
        don't have to access the result of _write_type2_header_record by indexes
        in order to write the real estates data at the right place in the BOE
        (which is better in case the code of the header function needs to be extended).
        """
        return {'count': 0, 'total': 0}

    def _get_invoice_types_xmlids(self):
        return {
            'l10n_es_reports.mod_347_operations_insurance_bought': 'insurance',
            'l10n_es_reports.mod_347_operations_insurance_sold': 'insurance',
            'l10n_es_reports.mod_347_operations_regular_sold': 'regular',
            'l10n_es_reports.mod_347_operations_regular_bought': 'regular',
        }

    def _write_type2_partner_record(self, options, report_data, year, current_company, operation_key, manual_parameters_map, insurance=False, local_negocio=False):
        currency_id = current_company.currency_id
        line_partner = self.env['res.partner'].browse(self.env['account.report']._get_model_info_from_id(report_data['line_data'].id)[1])

        rslt = self._l10n_es_boe_format_number(options, 2)
        rslt += self._l10n_es_boe_format_number(options, 347)
        rslt += self._l10n_es_boe_format_string(year, length=4)
        rslt += self._l10n_es_boe_format_string(self._extract_spanish_tin(current_company.partner_id), length=9)
        rslt += self._l10n_es_boe_format_string(line_partner.country_id.code == 'ES' and self._extract_spanish_tin(line_partner) or '', length=9)
        rslt += self._l10n_es_boe_format_string(' ' * 9)  # TIN of the legal representant; blank if 14 years or older
        rslt += self._l10n_es_boe_format_string(line_partner.display_name, length=40)
        rslt += self._l10n_es_boe_format_string('D')  # 'Tipo de hoja', constant

        province_code = line_partner.state_id and SPANISH_PROVINCES_REPORT_CODES.get(line_partner.state_id.code) or '99'
        rslt += self._l10n_es_boe_format_string(province_code, length=2)
        # The country code is only mandatory if there is no province code (hence: no head office in Spain)
        if province_code == '99':
            if not line_partner.country_id or not line_partner.country_id.code:
                raise UserError(_("Partner %(name)s (id %(id)d) is not associated to any Spanish province, and should hence have a country code. For this, fill in its 'country' field.", name=line_partner.name, id=line_partner.id))

            if line_partner.country_id.code == 'ES':
                raise UserError(_("Partner %(name)s (id %(id)d) is located in Spain but does not have any province. Please set one.", name=line_partner.name, id=line_partner.id))

        partner_country_code = line_partner.country_id.code
        rslt += self._l10n_es_boe_format_string(partner_country_code if partner_country_code and partner_country_code != 'ES' else '', length=2)
        rslt += self._l10n_es_boe_format_string(' ')  # Constant
        rslt += self._l10n_es_boe_format_string(operation_key, length=1)

        # Total amount of operations over the year
        year_operations_sum = currency_id.round(sum(i.no_format for i in report_data['line_data'].columns or []))
        rslt += self._l10n_es_boe_format_number(options, year_operations_sum, length=16, decimal_places=2, signed=True, sign_pos=' ', in_currency=True)

        rslt += self._l10n_es_boe_format_string(insurance and 'X' or ' ')
        rslt += self._l10n_es_boe_format_string(local_negocio and 'X' or ' ')

        # En metálico
        invoice_types_by_xmlid = self._get_invoice_types_xmlids()
        current_invoice_type = invoice_types_by_xmlid[report_data['line_xml_id']]

        account_type = operation_key == 'B' and 'asset_receivable' or 'liability_payable'
        matching_field = operation_key == 'B' and 'debit' or 'credit'
        cash_payments_lines_in_period = self.env['account.move.line'].search([('date', '<=', year + '-12-31'), ('date', '>=', year + '-01-01'), ('journal_id.type', '=', 'cash'), ('payment_id', '!=', False), ('partner_id', '=', line_partner.id), ('account_type', '=', account_type), ('company_id', '=', current_company.id)])
        metalico_amount = 0
        for cash_payment_aml in cash_payments_lines_in_period:
            partial_reconcile_ids = cash_payment_aml['matched_' + matching_field + '_ids']
            partial_rec_on_inv_type = partial_reconcile_ids.filtered(lambda x: x[matching_field + '_move_id'].move_id.l10n_es_reports_mod347_invoice_type == current_invoice_type)
            for partial_rec in partial_rec_on_inv_type:
                metalico_amount += partial_rec.amount

        # Context key used for conversion date is set in get_txt.
        curr_eur = self.env["res.currency"].search([('name', '=', 'EUR')], limit=1)
        threshold = curr_eur._convert(6000, currency_id, current_company, options['date']['date_to'])
        if currency_id.compare_amounts(metalico_amount, threshold) == 1:  # We only must report this amount if it is above 6000 €
            rslt += self._l10n_es_boe_format_number(options, metalico_amount, length=15, decimal_places=2, in_currency=True)
        else:
            rslt += self._l10n_es_boe_format_number(options, 0, length=15)

        # Inmuebles sujetas a la IVA
        operation_class = insurance and 'seguros' or local_negocio and 'local_negocio' or 'otras'
        real_estates_vat_year_total = 0
        real_estates_vat_by_trimester = []
        for trimester in range(1, 5):
            # This module does not support real estates on its own, but we give the possibility
            # to add a real_estates_vat key to the manual parameters map with the needed data,
            # through anoter module (l10n_es_real_estates does that)
            real_estates_vat_partner_dict = manual_parameters_map.get('real_estates_vat', {}).get(line_partner.id)
            real_estates_vat_amount = real_estates_vat_partner_dict and real_estates_vat_partner_dict[str(trimester)][operation_class][operation_key] or 0
            real_estates_vat_year_total += real_estates_vat_amount
            real_estates_vat_by_trimester.append(real_estates_vat_amount)

        real_estates_vat_year_total = currency_id.round(real_estates_vat_year_total)
        rslt += self._l10n_es_boe_format_number(options, real_estates_vat_year_total, length=16, decimal_places=2, signed=True, sign_pos=' ', in_currency=True)

        rslt += self._l10n_es_boe_format_string('0000', length=4)  # Ejercicio for metalico operations ; automatic computation not supported

        for trimester_index in range(3, -1, -1):  # 4th trimester is at position 0 ; 1st at position 3
            trimester_total = (report_data['line_data'].columns or [{} for i in range(0, 4)])[trimester_index].no_format or 0
            rslt += self._l10n_es_boe_format_number(options, trimester_total, length=16, decimal_places=2, signed=True, sign_pos=' ', in_currency=True)
            rslt += self._l10n_es_boe_format_number(options, real_estates_vat_by_trimester[trimester_index], length=16, decimal_places=2, signed=True, sign_pos=' ', in_currency=True)

        # 'NIF Operador Comunitario'
        europe_countries = self.env.ref('base.europe').country_ids - self.env.ref('base.es')
        intracom_tin = ''
        if line_partner.country_id in europe_countries:
            intracom_tin = self._extract_tin(line_partner, error_if_no_tin=False)
        rslt += self._l10n_es_boe_format_string(intracom_tin.upper(), length=17)

        # Cash Basis (Regimen Especial de Caja)
        cash_basis_partner = manual_parameters_map['cash_basis'].get(line_partner.id)
        cash_basis_data = cash_basis_partner and cash_basis_partner[operation_class][operation_key] or None
        rslt += self._l10n_es_boe_format_string(cash_basis_data is not None and 'X' or ' ')

        rslt += self._l10n_es_boe_format_string(line_partner == current_company.partner_id and 'X' or ' ')

        rslt += self._l10n_es_boe_format_string(' ')  # Not supported by Odoo; according to the partners, too few people need this option

        rslt += self._l10n_es_boe_format_number(options, cash_basis_data or 0, length=16, decimal_places=2, signed=True, sign_pos=' ', in_currency=True)

        rslt += self._l10n_es_boe_format_string('000000', length=6)
        rslt += self._l10n_es_boe_format_string(' ' * 195)
        rslt += '\r\n'

        return rslt

    def export_boe(self, options):
        self.env.flush_all()
        boe_wizard = self._retrieve_boe_manual_wizard(options, 347)
        _period, year = self._get_mod_period_and_year(options)
        year = str(boe_wizard.return_id.date_from.year)
        current_company = self.env.company
        report = self.env['account.report'].browse(options['report_id'])

        # Report options to use to retrieve data for the BOE
        boe_report_options = self._build_boe_report_options(options, year)

        manual_params = boe_wizard.l10n_es_get_partners_manual_parameters_map()

        # Header
        rslt = self._write_type2_header_record(current_company, boe_wizard, boe_report_options, year=year)
        seguros_required_a = self._get_required_partner_ids_for_boe('insurance', year + '-01-01', year + '-12-31', boe_wizard, 'A', 'seguros')
        rslt += self._call_on_partner_sublines(
            boe_report_options,
            'l10n_es_reports.mod_347_operations_insurance_bought',
            lambda report_data: self._write_type2_partner_record(boe_report_options, report_data, year, current_company, 'A',
                                                                 manual_parameters_map=manual_params, insurance=True),
            required_ids_set=seguros_required_a
        )

        seguros_required_b = self._get_required_partner_ids_for_boe('insurance', year + '-01-01', year + '-12-31', boe_wizard, 'B', 'seguros')
        rslt += self._call_on_partner_sublines(
            boe_report_options,
            'l10n_es_reports.mod_347_operations_insurance_sold',
            lambda report_data: self._write_type2_partner_record(boe_report_options, report_data, year, current_company, 'B',
                                                                manual_parameters_map=manual_params, insurance=True),
            required_ids_set=seguros_required_b
        )

        otras_required_a = self._get_required_partner_ids_for_boe('regular', year + '-01-01', year + '-12-31', boe_wizard, 'B', 'otras')
        rslt += self._call_on_partner_sublines(
            boe_report_options,
            'l10n_es_reports.mod_347_operations_regular_sold',
            lambda report_data: self._write_type2_partner_record(boe_report_options, report_data, year, current_company, 'B',
                                                                 manual_parameters_map=manual_params),
            required_ids_set=otras_required_a
        )

        otras_required_b = self._get_required_partner_ids_for_boe('regular', year + '-01-01', year + '-12-31', boe_wizard, 'A', 'otras')
        rslt += self._call_on_partner_sublines(
            boe_report_options,
            'l10n_es_reports.mod_347_operations_regular_bought',
            lambda report_data: self._write_type2_partner_record(boe_report_options, report_data, year, current_company, 'A',
                                                                 manual_parameters_map=manual_params),
            required_ids_set=otras_required_b
        )

        return {
            'file_name': report.get_default_report_filename(options, 'txt'),
            'file_content': rslt.encode(),
            'file_type': 'txt',
        }

    def action_audit_cell(self, options, params):
        report_line = self.env['account.report.line'].browse(params['report_line_id'])
        action = report_line.report_id.action_audit_cell(options, params)
        action['context'] = {
            **(action.get('context') or {}),
            'group_by': ['move_type', 'invoice_date:quarter'],
        }
        return action


class L10n_EsMod349TaxReportHandler(models.AbstractModel):
    _name = 'l10n_es.mod349.tax.report.handler'
    # Still inherit the l10n_es common behaviour, hence the tax report handler. To be removed after v19
    _inherit = ['l10n_es.tax.report.handler', 'account.ec.sales.with.tags.report.handler']
    _description = 'Spanish Tax Report Custom Handler (Mod349)'

    def _wrap_mod349_value_for_report(self, value, current_groupby):
        if not current_groupby:
            return {'value': value, 'has_sublines': not float_is_zero(value, precision_rounding=2)}
        return [(group_id, {'value': val, 'has_sublines': not float_is_zero(val, precision_rounding=2)}) for group_id, val in value]

    def _report_engine_modelo349_invoice_e(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        tax_ids = frozenset()
        if current_groupby:
            tax_ids = self.env['account.tax.repartition.line'].search([('tag_ids', 'any', [('name', '=', 'mod349[E]')])]).mapped('tax_id')
        res = self._custom_modelo349_query(frozendict(options), current_groupby, tax_ids)['invoice', 'E']
        return {next(iter(formulas_dict.values())):  self._wrap_mod349_value_for_report(res, current_groupby)}

    def _report_engine_modelo349_invoice_a(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        tax_ids = frozenset()
        if current_groupby:
            tax_ids = self.env['account.tax.repartition.line'].search([('tag_ids', 'any', [('name', '=', 'mod349[A]')])]).mapped('tax_id')
        res = self._custom_modelo349_query(frozendict(options), current_groupby, tax_ids)['invoice', 'A']
        return {next(iter(formulas_dict.values())):  self._wrap_mod349_value_for_report(res, current_groupby)}

    def _report_engine_modelo349_invoice_t(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        tax_ids = frozenset()
        if current_groupby:
            tax_ids = self.env['account.tax.repartition.line'].search([('tag_ids', 'any', [('name', '=', 'mod349[T]')])]).mapped('tax_id')
        res = self._custom_modelo349_query(frozendict(options), current_groupby, tax_ids)['invoice', 'T']
        return {next(iter(formulas_dict.values())):  self._wrap_mod349_value_for_report(res, current_groupby)}

    def _report_engine_modelo349_invoice_s(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        tax_ids = frozenset()
        if current_groupby:
            tax_ids = self.env['account.tax.repartition.line'].search([('tag_ids', 'any', [('name', '=', 'mod349[S]')])]).mapped('tax_id')
        res = self._custom_modelo349_query(frozendict(options), current_groupby, tax_ids)['invoice', 'S']
        return {next(iter(formulas_dict.values())):  self._wrap_mod349_value_for_report(res, current_groupby)}

    def _report_engine_modelo349_invoice_i(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        tax_ids = frozenset()
        if current_groupby:
            tax_ids = self.env['account.tax.repartition.line'].search([('tag_ids', 'any', [('name', '=', 'mod349[I]')])]).mapped('tax_id')
        res = self._custom_modelo349_query(frozendict(options), current_groupby, tax_ids)['invoice', 'I']
        return {next(iter(formulas_dict.values())):  self._wrap_mod349_value_for_report(res, current_groupby)}

    def _report_engine_modelo349_invoice_m(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        tax_ids = frozenset()
        if current_groupby:
            tax_ids = self.env['account.tax.repartition.line'].search([('tag_ids', 'any', [('name', '=', 'mod349[M]')])]).mapped('tax_id')
        res = self._custom_modelo349_query(frozendict(options), current_groupby, tax_ids)['invoice', 'M']
        return {next(iter(formulas_dict.values())):  self._wrap_mod349_value_for_report(res, current_groupby)}

    def _report_engine_modelo349_invoice_h(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        tax_ids = frozenset()
        if current_groupby:
            tax_ids = self.env['account.tax.repartition.line'].search([('tag_ids', 'any', [('name', '=', 'mod349[H]')])]).mapped('tax_id')
        res = self._custom_modelo349_query(frozendict(options), current_groupby, tax_ids)['invoice', 'H']
        return {next(iter(formulas_dict.values())):  self._wrap_mod349_value_for_report(res, current_groupby)}

    def _report_engine_modelo349_invoice_r(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        tax_ids = frozenset()
        if current_groupby:
            tax_ids = self.env['account.tax.repartition.line'].search([('tag_ids', 'any', [('name', '=', 'mod349[R]')])]).mapped('tax_id')
        res = self._custom_modelo349_query(frozendict(options), current_groupby, tax_ids)['invoice', 'R']
        return {next(iter(formulas_dict.values())):  self._wrap_mod349_value_for_report(res, current_groupby)}

    def _report_engine_modelo349_invoice_d(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        tax_ids = frozenset()
        if current_groupby:
            tax_ids = self.env['account.tax.repartition.line'].search([('tag_ids', 'any', [('name', '=', 'mod349[D]')])]).mapped('tax_id')
        res = self._custom_modelo349_query(frozendict(options), current_groupby, tax_ids)['invoice', 'D']
        return {next(iter(formulas_dict.values())):  self._wrap_mod349_value_for_report(res, current_groupby)}

    def _report_engine_modelo349_invoice_c(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        tax_ids = frozenset()
        if current_groupby:
            tax_ids = self.env['account.tax.repartition.line'].search([('tag_ids', 'any', [('name', '=', 'mod349[C]')])]).mapped('tax_id')
        res = self._custom_modelo349_query(frozendict(options), current_groupby, tax_ids)['invoice', 'C']
        return {next(iter(formulas_dict.values())):  self._wrap_mod349_value_for_report(res, current_groupby)}

    def _report_engine_modelo349_refund_e(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        tax_ids = frozenset()
        if current_groupby:
            tax_ids = self.env['account.tax.repartition.line'].search([('tag_ids', 'any', [('name', '=', 'mod349[E]')])]).mapped('tax_id')
        res = self._custom_modelo349_query(frozendict(options), current_groupby, tax_ids)['refund', 'E']
        return {next(iter(formulas_dict.values())):  self._wrap_mod349_value_for_report(res, current_groupby)}

    def _report_engine_modelo349_refund_a(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        tax_ids = frozenset()
        if current_groupby:
            tax_ids = self.env['account.tax.repartition.line'].search([('tag_ids', 'any', [('name', '=', 'mod349[A]')])]).mapped('tax_id')
        res = self._custom_modelo349_query(frozendict(options), current_groupby, tax_ids)['refund', 'A']
        return {next(iter(formulas_dict.values())):  self._wrap_mod349_value_for_report(res, current_groupby)}

    def _report_engine_modelo349_refund_t(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        tax_ids = frozenset()
        if current_groupby:
            tax_ids = self.env['account.tax.repartition.line'].search([('tag_ids', 'any', [('name', '=', 'mod349[T]')])]).mapped('tax_id')
        res = self._custom_modelo349_query(frozendict(options), current_groupby, tax_ids)['refund', 'T']
        return {next(iter(formulas_dict.values())):  self._wrap_mod349_value_for_report(res, current_groupby)}

    def _report_engine_modelo349_refund_s(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        tax_ids = frozenset()
        if current_groupby:
            tax_ids = self.env['account.tax.repartition.line'].search([('tag_ids', 'any', [('name', '=', 'mod349[S]')])]).mapped('tax_id')
        res = self._custom_modelo349_query(frozendict(options), current_groupby, tax_ids)['refund', 'S']
        return {next(iter(formulas_dict.values())):  self._wrap_mod349_value_for_report(res, current_groupby)}

    def _report_engine_modelo349_refund_i(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        tax_ids = frozenset()
        if current_groupby:
            tax_ids = self.env['account.tax.repartition.line'].search([('tag_ids', 'any', [('name', '=', 'mod349[I]')])]).mapped('tax_id')
        res = self._custom_modelo349_query(frozendict(options), current_groupby, tax_ids)['refund', 'I']
        return {next(iter(formulas_dict.values())):  self._wrap_mod349_value_for_report(res, current_groupby)}

    def _report_engine_modelo349_refund_m(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        tax_ids = frozenset()
        if current_groupby:
            tax_ids = self.env['account.tax.repartition.line'].search([('tag_ids', 'any', [('name', '=', 'mod349[M]')])]).mapped('tax_id')
        res = self._custom_modelo349_query(frozendict(options), current_groupby, tax_ids)['refund', 'M']
        return {next(iter(formulas_dict.values())):  self._wrap_mod349_value_for_report(res, current_groupby)}

    def _report_engine_modelo349_refund_h(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        tax_ids = frozenset()
        if current_groupby:
            tax_ids = self.env['account.tax.repartition.line'].search([('tag_ids', 'any', [('name', '=', 'mod349[H]')])]).mapped('tax_id')
        res = self._custom_modelo349_query(frozendict(options), current_groupby, tax_ids)['refund', 'H']
        return {next(iter(formulas_dict.values())):  self._wrap_mod349_value_for_report(res, current_groupby)}

    def _report_engine_modelo349_refund_r(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        tax_ids = frozenset()
        if current_groupby:
            tax_ids = self.env['account.tax.repartition.line'].search([('tag_ids', 'any', [('name', '=', 'mod349[R]')])]).mapped('tax_id')
        res = self._custom_modelo349_query(frozendict(options), current_groupby, tax_ids)['refund', 'R']
        return {next(iter(formulas_dict.values())):  self._wrap_mod349_value_for_report(res, current_groupby)}

    def _report_engine_modelo349_refund_d(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        tax_ids = frozenset()
        if current_groupby:
            tax_ids = self.env['account.tax.repartition.line'].search([('tag_ids', 'any', [('name', '=', 'mod349[D]')])]).mapped('tax_id')
        res = self._custom_modelo349_query(frozendict(options), current_groupby, tax_ids)['refund', 'D']
        return {next(iter(formulas_dict.values())):  self._wrap_mod349_value_for_report(res, current_groupby)}

    def _report_engine_modelo349_refund_c(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        tax_ids = frozenset()
        if current_groupby:
            tax_ids = self.env['account.tax.repartition.line'].search([('tag_ids', 'any', [('name', '=', 'mod349[C]')])]).mapped('tax_id')
        res = self._custom_modelo349_query(frozendict(options), current_groupby, tax_ids)['refund', 'C']
        return {next(iter(formulas_dict.values())):  self._wrap_mod349_value_for_report(res, current_groupby)}

    def _report_engine_modelo349_invoice_totals(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        res = self._custom_modelo349_query(frozendict(options), 'partner_id', frozenset())['invoice', 'total']
        if not current_groupby:
            res = sum(x[1] for x in res)
        return {next(iter(formulas_dict.values())):  self._wrap_mod349_value_for_report(res, current_groupby)}

    def _report_engine_modelo349_refund_totals(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        res = self._custom_modelo349_query(frozendict(options), 'partner_id', frozenset())['refund', 'total']
        if not current_groupby:
            res = sum(x[1] for x in res)
        return {next(iter(formulas_dict.values())):  self._wrap_mod349_value_for_report(res, current_groupby)}

    def _get_modelo349_audit_aml_domain(self, options, move_type):
        res = self._custom_modelo349_query(frozendict(options), 'move_id', frozenset())
        result = [
            ('move_id', 'in', [x[0] for x in res[move_type, 'total']]),
            ('account_type', 'in', ('asset_receivable', 'liability_payable'))
        ]
        return result

    def _custom_modelo349_query(self, options, current_groupby, tax_ids=frozenset()):
        # method parameter need to be hashable for being cached, so the dict 'options' is
        # passed as a frozendict, and 'tax_ids' as a recordset/frozenset
        cache_key = (options, current_groupby, tax_ids)
        if '_custom_modelo349_query' in self.env.cr.cache and cache_key in self.env.cr.cache['_custom_modelo349_query']:
            return self.env.cr.cache['_custom_modelo349_query'][cache_key]
        report = self.env['account.report'].browse(options['report_id'])
        if current_groupby:
            report._check_groupby_fields([current_groupby])

        if not tax_ids:
            # all the taxes having a tag 'mod349[x]'
            tax_ids = self.env['account.tax.repartition.line'].search([('tag_ids', 'any', [('name', '=like', 'mod349%')])]).mapped('tax_id')

        group_operations_count = defaultdict(lambda: defaultdict(lambda: 0.0))
        if not current_groupby:
            result = defaultdict(lambda: 0.0)
        else:
            result = defaultdict(lambda: defaultdict(lambda: 0.0))

        if tax_ids:
            # Build query
            # domain on taxes is applied manually in the query because it can't be applied on the with_statement (reconciled lines don't have the tax)
            query = report._get_report_query(options, 'strict_range', domain=[])
            groupby_field_sql = self.env['account.move.line']._field_to_sql('account_move_line', current_groupby, query) if current_groupby else SQL()
            where_clause = query.where_clause
            counterpart_where_clause = SQL(where_clause._sql_tuple[0].replace('"account_move_line".', '"counterpart".'), *where_clause._sql_tuple[1])  # pylint: disable=sql-injection
            self.env.flush_all()
            query = SQL("""
                WITH ref_table AS (
                    SELECT account_move_line.move_id AS m1,
                           counterpart.move_id AS m2,
                           p.amount AS partial_amount,
                           account_move_line.balance AS m1_balance,
                           counterpart.balance AS m2_balance
                      FROM %(tables)s
                 LEFT JOIN account_partial_reconcile p ON p.debit_move_id = account_move_line.id
                 LEFT JOIN account_move_line counterpart ON p.credit_move_id = counterpart.id
                 LEFT JOIN account_move counterpart_move ON counterpart_move.id IN (counterpart.move_id, account_move_line.move_id)
                     WHERE %(where_clause)s
                       AND %(counterpart_where_clause)s
                       AND counterpart_move.move_type ILIKE '%%refund%%'
                ), to_cancel_moves AS (
                    SELECT m1 AS move_id,
                           SUM(partial_amount / ABS(m1_balance)) AS percentage
                      FROM ref_table
                  GROUP BY move_id

                     UNION ALL

                    SELECT m2 AS move_id,
                           SUM(partial_amount / ABS(m2_balance)) AS percentage
                      FROM ref_table
                  GROUP BY move_id
                )

                SELECT %(select_from_groupby)s
                       COUNT(account_move.id) AS group_count,
                       tax_rel.account_tax_id as tax_id,
                       account_move.move_type AS move_type,
                       SUM(account_move_line.balance * (CASE WHEN account_move.move_type IN ('in_invoice', 'out_refund') THEN 1 ELSE -1 END)) AS total_amount_untaxed
                  FROM %(tables)s
                  JOIN account_move ON account_move.id = account_move_line.move_id
             LEFT JOIN account_move_line_account_tax_rel tax_rel ON tax_rel.account_move_line_id = account_move_line.id
                  JOIN account_tax tax ON tax.id = tax_rel.account_tax_id
                 WHERE %(where_clause)s
                   AND tax_rel.account_tax_id IN %(tax_ids)s
              GROUP BY %(group_by)s
                       account_move.move_type,
                       tax_rel.account_tax_id

                -- remove the credit notes ad invoices that are reconciled together and both in the date range
                 UNION ALL

                SELECT %(select_from_groupby)s
                       - SUM(CASE WHEN(to_cancel_moves.percentage = 1) THEN 1 ELSE 0 END) AS group_count,
                       tax_rel.account_tax_id as tax_id,
                       account_move.move_type AS move_type,
                       - SUM(to_cancel_moves.percentage * ABS(account_move_line.balance)) AS total_amount_untaxed
                  FROM %(tables)s
                  JOIN account_move ON account_move.id = account_move_line.move_id
             LEFT JOIN account_move_line_account_tax_rel tax_rel ON tax_rel.account_move_line_id = account_move_line.id
                  JOIN to_cancel_moves ON (account_move_line.move_id = to_cancel_moves.move_id)
                 WHERE %(where_clause)s
                   AND tax_rel.account_tax_id IN %(tax_ids)s
              GROUP BY %(group_by)s
                       account_move.move_type,
                       tax_rel.account_tax_id
                """,
                select_from_groupby=SQL("%s AS grouping_key,", groupby_field_sql) if groupby_field_sql else SQL(),
                tables=query.from_clause,
                where_clause=query.where_clause,
                counterpart_where_clause=counterpart_where_clause,
                tax_ids=tuple(tax_ids.ids),
                group_by=SQL("%s,", groupby_field_sql) if groupby_field_sql else SQL(),
            )
            self.env.cr.execute(query)
            query_res_lines = self.env.cr.dictfetchall()

            # the SQL query makes the union of the 1) invoices & refunds within the date range, 2) invoices & refunds within the range that
            # are reconciled together. Those must 'cancel' the original rows added in 1), up to the reconciled amount. Hence we post-process
            # the result of the query to get the exact amount and number of operations.
            for row in query_res_lines:
                tax = self.env['account.tax'].with_prefetch(tax_ids.ids).browse(row['tax_id'])
                tag_names = [t.name for t in tax.invoice_repartition_line_ids.tag_ids | tax.refund_repartition_line_ids.tag_ids if t.name.startswith('mod349')]
                for tag_name in tag_names:
                    tag_key = re.search(r'mod349\[(.?)\]', tag_name)
                    if tag_key:
                        section = 'invoice' in row['move_type'] and 'invoice' or 'refund'
                        dict_key = section, tag_key.groups(1)[0]
                        if not current_groupby:
                            result[dict_key] += row['total_amount_untaxed']
                        else:
                            result[dict_key][row['grouping_key']] += row['total_amount_untaxed']
                            group_operations_count[row['grouping_key']][dict_key] += row['group_count']

        if current_groupby:
            # transform the result in a list, as expected by the report engine
            tmp_res = defaultdict(lambda: defaultdict(lambda: 0.0))
            for key, group_dict in result.items():
                tmp_res[key] = [(k, v) for k, v in group_dict.items()]

            # compute the total number of operators
            tmp_res['invoice', 'total'] = []
            tmp_res['refund', 'total'] = []
            for group_id in group_operations_count:
                inv_total = 0
                ref_total = 0
                for (section, tag_key), op_count in group_operations_count[group_id].items():
                    if not op_count:
                        continue
                    if section == 'invoice':
                        inv_total += 1
                    else:
                        ref_total += 1
                if inv_total:
                    tmp_res['invoice', 'total'].append((group_id, inv_total))
                if ref_total:
                    tmp_res['refund', 'total'].append((group_id, ref_total))

            result = tmp_res

        # store the method result in a cache that lasts the current transaction only
        if '_custom_modelo349_query' not in self.env.cr.cache:
            self.env.cr.cache['_custom_modelo349_query'] = {}
        self.env.cr.cache['_custom_modelo349_query'][cache_key] = result
        return result

    def _write_type1_header_record(self, options, period, year, current_company, boe_wizard):
        rslt = self._l10n_es_boe_format_string('1349')
        rslt += self._l10n_es_boe_format_string(year, length=4)
        rslt += self._l10n_es_boe_format_string(self._extract_spanish_tin(current_company.partner_id), length=9)
        rslt += self._l10n_es_boe_format_string(current_company.name, length=40)
        rslt += self._l10n_es_boe_format_string('T')
        rslt += self._l10n_es_boe_format_string(boe_wizard.get_formatted_contact_phone(), length=9)
        rslt += self._l10n_es_boe_format_string(boe_wizard.contact_person_name, length=40)
        mod_349_boe_sequence = current_company.sudo()._get_mod_boe_sequence("349")
        rslt += self._l10n_es_boe_format_number(options, 349) + self._l10n_es_boe_format_string(mod_349_boe_sequence.next_by_id(), length=10)
        rslt += self._l10n_es_boe_format_string(boe_wizard.complementary_declaration and 'C' or ' ')
        rslt += self._l10n_es_boe_format_string(boe_wizard.substitutive_declaration and 'S' or ' ')
        rslt += self._l10n_es_boe_format_string(boe_wizard.previous_report_number or '', length=13, fill_char='0', align='right')
        rslt += self._l10n_es_boe_format_string(period, length=2)
        rslt += self._l10n_es_boe_format_number(options, self._retrieve_report_expression(options, 'l10n_es_reports.mod_349_statistics_invoices_partners_count_balance'), length=9)
        rslt += self._l10n_es_boe_format_number(options, self._retrieve_report_expression(options, 'l10n_es_reports.mod_349_statistics_invoices_total_amount_balance'), length=15, in_currency=True, decimal_places=2)
        rslt += self._l10n_es_boe_format_number(options, self._retrieve_report_expression(options, 'l10n_es_reports.mod_349_statistics_refunds_partners_count_balance'), length=9)
        rslt += self._l10n_es_boe_format_number(options, self._retrieve_report_expression(options, 'l10n_es_reports.mod_349_statistics_refunds_total_amount_balance'), length=15, in_currency=True, decimal_places=2)
        rslt += self._l10n_es_boe_format_string(boe_wizard.trimester_2months_report and 'X' or ' ')
        rslt += self._l10n_es_boe_format_string(' ' * 204)
        rslt += self._l10n_es_boe_format_string(' ' * 9)  # TIN of the legal representative, if under 14 years old
        rslt += self._l10n_es_boe_format_string(' ' * 101)  # Constant
        rslt += '\r\n'
        return rslt

    def _write_type2_invoice_record(self, options, report_data, year, key, current_company):
        rslt = ''
        if report_data['line_data'].columns[0].no_format > 0:
            line_partner = self.env['res.partner'].browse(self.env['account.report']._get_model_info_from_id(report_data['line_data'].id)[1])
            rslt += self._l10n_es_boe_format_string('2349')
            rslt += self._l10n_es_boe_format_string(year, length=4)
            rslt += self._l10n_es_boe_format_string(self._extract_spanish_tin(current_company.partner_id), length=9)
            rslt += self._l10n_es_boe_format_string(' ' * 58)
            rslt += self._l10n_es_boe_format_string(self._extract_tin(line_partner), length=17)
            rslt += self._l10n_es_boe_format_string(line_partner.name, length=40)
            rslt += self._l10n_es_boe_format_string(key, length=1)
            rslt += self._l10n_es_boe_format_number(options, report_data['line_data'].columns[0].no_format, length=13, decimal_places=2, in_currency=True)
            rslt += self._l10n_es_boe_format_string(' ' * 354)
            rslt += '\r\n'

        return rslt

    def _write_type2_refund_records(self, options, report_data, current_company, mod_349_type, invoice_report_line_xml_id, report_period, report_year):
        line_partner = self.env['res.partner'].browse(self.env['account.report']._get_model_info_from_id(report_data['line_data'].id)[1])
        report_date_from = options['date']['date_from']
        report_date_to = options['date']['date_to']

        matched_moves = []
        period_dict = {}
        for refund_invoice in self.env['account.move'].search([
            ('date', '<=', report_date_to),
            ('date', '>=', report_date_from),
            ('move_type', 'in', ['in_refund', 'out_refund']),
            ('partner_id', '=', line_partner.id),
            ('state', '=', 'posted'),
        ]):
            original_invoice = refund_invoice.reversed_entry_id

            if not original_invoice:
                raise UserError(_('Refund Invoice %s was created without a link to the original invoice that was credited, '
                                  'while we need that information for this report. ', refund_invoice.display_name))

            tax_return_periodicity = options.get('return_periodicity').get('periodicity')
            if tax_return_periodicity == 'monthly':
                invoice_period, invoice_year = '%02d' % original_invoice.date.month, str(original_invoice.date.year)
            elif tax_return_periodicity == 'trimester':
                invoice_period, invoice_year = '%01dT' % (1 + ((original_invoice.date.month - 1) // 3)), str(original_invoice.date.year)
            else:
                # The mod349 is only valid at the monthly or quarterly periodicity.
                raise UserError(_('The tax return periodicity is set to %s. '
                                  'You cannot generate a BOE file for the Modelo349 report for this periodicity.', tax_return_periodicity))

            if (original_invoice.date <= datetime.strptime(report_date_to, '%Y-%m-%d').date() and
                    original_invoice.date >= datetime.strptime(report_date_from, '%Y-%m-%d').date()):
                continue

            if f"{invoice_period}{invoice_year}" not in period_dict:
                period_dict[f"{invoice_period}{invoice_year}"] = {
                    'old_balance': 0,
                    'new_balance': 0,
                }

            if original_invoice.id not in matched_moves:
                period_dict[f"{invoice_period}{invoice_year}"]['old_balance'] += original_invoice.amount_total
                period_dict[f"{invoice_period}{invoice_year}"]['new_balance'] += original_invoice.amount_total - sum(refund.amount_total for refund in original_invoice.reversal_move_ids)
                matched_moves.append(original_invoice.id)

        rslt = self._l10n_es_boe_format_string('')

        # Now, we can report the record !
        for period, line_vals in period_dict.items():
            rslt += self._l10n_es_boe_format_string('2349')
            rslt += self._l10n_es_boe_format_string(report_year, length=4)
            rslt += self._l10n_es_boe_format_string(self._extract_spanish_tin(current_company.partner_id), length=9)
            rslt += self._l10n_es_boe_format_string(' ' * 58)
            rslt += self._l10n_es_boe_format_string(self._extract_tin(line_partner), length=17)
            rslt += self._l10n_es_boe_format_string(line_partner.name, length=40)
            rslt += self._l10n_es_boe_format_string(mod_349_type, length=1)
            rslt += self._l10n_es_boe_format_string(' ' * 13)  # Constant
            rslt += self._l10n_es_boe_format_string(period[2:6], length=4)
            rslt += self._l10n_es_boe_format_string(period[0:2], length=2)
            rslt += self._l10n_es_boe_format_number(options, line_vals['new_balance'], length=13, decimal_places=2, in_currency=True)
            rslt += self._l10n_es_boe_format_number(options, line_vals['old_balance'], length=13, decimal_places=2, in_currency=True)
            rslt += self._l10n_es_boe_format_string(' ' * 322)
            rslt += '\r\n'

        return rslt

    def export_boe(self, options):
        period, year = self._get_mod_period_and_year(options)
        current_company = self.env.company
        boe_wizard = self._retrieve_boe_manual_wizard(options, 349)
        options['export_mode'] = 'file'
        if boe_wizard.trimester_2months_report:
            options = options.copy()
            end_date = datetime.strptime(options['date']['date_to'], '%Y-%m-%d')
            options['date']['date_to'] = (end_date + relativedelta(day=31, months=-1)).strftime('%Y-%m-%d')

        # Header
        rslt = self._write_type1_header_record(options, period, year, current_company, boe_wizard)

        # Invoices lines
        rslt += self._call_on_partner_sublines(options, 'l10n_es_reports.mod_349_supplies', lambda report_data: self._write_type2_invoice_record(options, report_data, year, 'E', current_company))
        rslt += self._call_on_partner_sublines(options, 'l10n_es_reports.mod_349_acquisitions', lambda report_data: self._write_type2_invoice_record(options, report_data, year, 'A', current_company))
        rslt += self._call_on_partner_sublines(options, 'l10n_es_reports.mod_349_triangular', lambda report_data: self._write_type2_invoice_record(options, report_data, year, 'T', current_company))
        rslt += self._call_on_partner_sublines(options, 'l10n_es_reports.mod_349_services_sold', lambda report_data: self._write_type2_invoice_record(options, report_data, year, 'S', current_company))
        rslt += self._call_on_partner_sublines(options, 'l10n_es_reports.mod_349_services_acquired', lambda report_data: self._write_type2_invoice_record(options, report_data, year, 'I', current_company))
        rslt += self._call_on_partner_sublines(options, 'l10n_es_reports.mod_349_supplies_without_taxes', lambda report_data: self._write_type2_invoice_record(options, report_data, year, 'M', current_company))
        rslt += self._call_on_partner_sublines(options, 'l10n_es_reports.mod_349_supplies_without_taxes_legal_representative', lambda report_data: self._write_type2_invoice_record(options, report_data, year, 'H', current_company))
        rslt += self._call_on_partner_sublines(options, 'l10n_es_reports.mod_349_consignment_sales_agreements', lambda report_data: self._write_type2_invoice_record(options, report_data, year, 'R', current_company))
        rslt += self._call_on_partner_sublines(options, 'l10n_es_reports.mod_349_returns_goods_consignment', lambda report_data: self._write_type2_invoice_record(options, report_data, year, 'D', current_company))
        rslt += self._call_on_partner_sublines(options, 'l10n_es_reports.mod_349_substitutions', lambda report_data: self._write_type2_invoice_record(options, report_data, year, 'C', current_company))

        # Refunds lines
        rslt += self._call_on_partner_sublines(options, 'l10n_es_reports.mod_349_supplies_refunds', lambda report_data: self._write_type2_refund_records(options, report_data, current_company, 'E', 'l10n_es_reports.mod_349_supplies', period, year))
        rslt += self._call_on_partner_sublines(options, 'l10n_es_reports.mod_349_acquisitions_refunds', lambda report_data: self._write_type2_refund_records(options, report_data, current_company, 'A', 'l10n_es_reports.mod_349_acquisitions', period, year))
        rslt += self._call_on_partner_sublines(options, 'l10n_es_reports.mod_349_triangular_refunds', lambda report_data: self._write_type2_refund_records(options, report_data, current_company, 'T', 'l10n_es_reports.mod_349_triangular', period, year))
        rslt += self._call_on_partner_sublines(options, 'l10n_es_reports.mod_349_services_sold_refunds', lambda report_data: self._write_type2_refund_records(options, report_data, current_company, 'S', 'l10n_es_reports.mod_349_services_sold', period, year))
        rslt += self._call_on_partner_sublines(options, 'l10n_es_reports.mod_349_services_acquired_refunds', lambda report_data: self._write_type2_refund_records(options, report_data, current_company, 'I', 'l10n_es_reports.mod_349_services_acquired', period, year))
        rslt += self._call_on_partner_sublines(options, 'l10n_es_reports.mod_349_supplies_without_taxes_refunds', lambda report_data: self._write_type2_refund_records(options, report_data, current_company, 'M', 'l10n_es_reports.mod_349_supplies_without_taxes', period, year))
        rslt += self._call_on_partner_sublines(options, 'l10n_es_reports.mod_349_supplies_without_taxes_legal_representative_refunds', lambda report_data: self._write_type2_refund_records(options, report_data, current_company, 'H', 'l10n_es_reports.mod_349_supplies_without_taxes_legal_representative', period, year))
        rslt += self._call_on_partner_sublines(options, 'l10n_es_reports.mod_349_consignment_sales_agreements_refunds', lambda report_data: self._write_type2_refund_records(options, report_data, current_company, 'R', 'l10n_es_reports.mod_349_consignment_sales_agreements', period, year))
        rslt += self._call_on_partner_sublines(options, 'l10n_es_reports.mod_349_returns_goods_consignment_refunds', lambda report_data: self._write_type2_refund_records(options, report_data, current_company, 'D', 'l10n_es_reports.mod_349_returns_goods_consignment', period, year))
        rslt += self._call_on_partner_sublines(options, 'l10n_es_reports.mod_349_substitutions_refunds', lambda report_data: self._write_type2_refund_records(options, report_data, current_company, 'C', 'l10n_es_reports.mod_349_substitutions', period, year))

        return {
            'file_name': self.env['account.report'].browse(options['report_id']).get_default_report_filename(options, 'txt'),
            'file_content': rslt.encode(),
            'file_type': 'txt',
        }

    def _custom_options_initializer(self, report, options, previous_options):
        es_mod_349_tax_tags = self._get_ec_sales_tax_tags()
        options.update({
            'sales_report_operation_types': {
                'goods': {
                    'tax_tag_ids': es_mod_349_tax_tags['goods'],
                },
                'services': {
                    'tax_tag_ids': es_mod_349_tax_tags['services'],
                },
                'triangular': {
                    'tax_tag_ids': es_mod_349_tax_tags['triangular'],
                },
            },
        })
        super()._custom_options_initializer(report, options, previous_options)

    def _get_ec_sales_tax_tags(self):
        # Overrides account_reports
        goods_expression = (
            self.env.ref('l10n_es_reports.aeat_mod_349_supplies_balance')
            + self.env.ref('l10n_es_reports.mod_349_supplies_without_taxes_balance')
            + self.env.ref('l10n_es_reports.mod_349_supplies_without_taxes_legal_representative_balance')
            + self.env.ref('l10n_es_reports.mod_349_consignment_sales_agreements_balance')
            + self.env.ref('l10n_es_reports.mod_349_returns_goods_consignment_balance')
            + self.env.ref('l10n_es_reports.mod_349_substitutions_balance')
        )
        services_expression = self.env.ref('l10n_es_reports.mod_349_services_sold_balance')
        triangular_expression = self.env.ref('l10n_es_reports.mod_349_triangular_balance')

        return {
            'goods': goods_expression._get_matching_tags().ids,
            'services': services_expression._get_matching_tags().ids,
            'triangular': triangular_expression._get_matching_tags().ids,
        }


class L10n_EsMod390TaxReportHandler(models.AbstractModel):
    _name = 'l10n_es.mod390.tax.report.handler'
    _inherit = ['l10n_es.tax.report.handler']
    _description = 'Spanish Tax Report Custom Handler (Mod390)'

    def export_boe(self, options):
        _period, year = self._get_mod_period_and_year(options)
        boe_wizard = self._retrieve_boe_manual_wizard(options, 390)
        current_company = self.env.company
        casilla_lines_map = {}
        for section in options['sections']:
            section_report = self.env['account.report'].browse(section['id'])
            report_lines = section_report._get_lines({**options, 'report_id': section_report.id})
            casilla_lines_map.update(self._retrieve_casilla_lines(report_lines))

        # Header
        rslt = self._l10n_es_boe_format_string('<T3900' + year + '0A0000>')
        rslt += self._l10n_es_boe_format_string('<AUX>')
        rslt += self._l10n_es_boe_format_string(' ' * 70)
        odoo_version = odoo.release.version.split('.')
        rslt += self._l10n_es_boe_format_string(str(odoo_version[0]) + str(odoo_version[1]), length=4)
        rslt += self._l10n_es_boe_format_string(' ' * 4)
        rslt += self._l10n_es_boe_format_string(self._extract_spanish_tin(current_company.partner_id), length=9)
        rslt += self._l10n_es_boe_format_string(' ' * 213)
        rslt += self._l10n_es_boe_format_string('</AUX>')

        rslt += self._generate_mod_390_page1(options, current_company, year, boe_wizard)
        rslt += self._generate_mod_390_page2(options, casilla_lines_map)
        rslt += self._generate_mod_390_page2b(options, casilla_lines_map)
        rslt += self._generate_mod_390_page3(options, casilla_lines_map)
        rslt += self._generate_mod_390_page4(options, casilla_lines_map)
        # We don't handle page 5 for now (Simplified regime operations, including agricultural, livestock and forestry)
        rslt += self._generate_mod_390_page6(options, casilla_lines_map)
        rslt += self._generate_mod_390_page7(options, casilla_lines_map)
        rslt += self._generate_mod_390_page8(options, casilla_lines_map)

        rslt += self._l10n_es_boe_format_string('</T3900' + year + '0A0000>')

        return {
            'file_name': self.env['account.report'].browse(options['report_id']).get_default_report_filename(options, 'txt'),
            'file_content': rslt.encode(),
            'file_type': 'txt',
        }

    def _generate_mod_390_page1(self, options, current_company, year, boe_wizard):
        # Main info regarding the company, the representant, the dates and the report itself
        # Header
        rslt = self._l10n_es_boe_format_string('<T39001000>  ')
        rslt += self._l10n_es_boe_format_string(self._extract_spanish_tin(current_company.partner_id), length=9)
        rslt += self._l10n_es_boe_format_string(current_company.name, length=60)
        rslt += self._l10n_es_boe_format_string(boe_wizard.physical_person_name, length=20)

        rslt += self._l10n_es_boe_format_string(year)
        rslt += self._l10n_es_boe_format_string('  ')

        rslt += self._l10n_es_boe_format_string('1' if boe_wizard.monthly_return else '0')

        tax_unit_option = options.get('tax_unit')
        group_of_entities = True if tax_unit_option and tax_unit_option != 'company_only' else False

        rslt += self._l10n_es_boe_format_string('1' if group_of_entities else '0')  # Part of a group of entities
        rslt += self._l10n_es_boe_format_string(boe_wizard.group_number, length=7) if boe_wizard.group_number else self._l10n_es_boe_format_string(' ' * 7)
        rslt += self._l10n_es_boe_format_string('1' if group_of_entities else '0')  # Dominant --> True if we're in a tax unit
        rslt += self._l10n_es_boe_format_string('0')  # Dependant --> always False
        rslt += self._l10n_es_boe_format_string('1' if boe_wizard.special_regime_applicable_163 else '0')
        # "NIF de la entidad dominante" must only be filled if the declarant is not the dominant entity
        # see official documentation : https://sede.agenciatributaria.gob.es/static_files/Sede/Procedimiento_ayuda/G412/instr390.pdf
        rslt += self._l10n_es_boe_format_string(' ' * 9)
        rslt += self._l10n_es_boe_format_string('2')  # Bankrupcy
        rslt += self._l10n_es_boe_format_string('1' if boe_wizard.special_cash_basis else '2')
        rslt += self._l10n_es_boe_format_string('1' if boe_wizard.special_cash_basis_beneficiary else '2')
        rslt += self._l10n_es_boe_format_string('1' if boe_wizard.is_substitute_declaration else '0')
        rslt += self._l10n_es_boe_format_string('1' if boe_wizard.is_substitute_decl_by_rectif_of_quotas else '0')
        rslt += self._l10n_es_boe_format_string(boe_wizard.previous_decl_number, length=13) if boe_wizard.previous_decl_number else self._l10n_es_boe_format_string(' ' * 13)
        rslt += self._l10n_es_boe_format_string(boe_wizard.principal_activity, length=40)
        rslt += self._l10n_es_boe_format_string(boe_wizard.principal_code_activity, length=3)
        rslt += self._l10n_es_boe_format_string(boe_wizard.principal_iae_epigrafe, length=4)

        # Other Activities
        for _i in range(0, 5):
            # Activity name (40), activity code (3) & activity epigrafe (4)
            rslt += self._l10n_es_boe_format_string(' ' * (40 + 3 + 4))

        # Joint Declaration
        rslt += self._l10n_es_boe_format_string('0')
        rslt += self._l10n_es_boe_format_string(' ' * (9 + 37))

        # Representant
        rslt += self._l10n_es_boe_format_string(' ' * (9 + 80 + 2 + 17 + 5 + 2 + 2 + 2 + 9 + 20 + 15 + 5))

        # Personas Jurídicas
        # Only one persona juridica is mandatory, the others are left blank
        rslt += self._l10n_es_boe_format_string(boe_wizard.judicial_person_name, length=80)
        rslt += self._l10n_es_boe_format_string(boe_wizard.judicial_person_nif, length=9)
        date = boe_wizard.judicial_person_procuration_date
        rslt += self._l10n_es_boe_format_string(datetime.strftime(date, "%d%m%Y") if date else '00000000', length=8)
        rslt += self._l10n_es_boe_format_string(boe_wizard.judicial_person_notary, length=12)
        rslt += self._l10n_es_boe_format_string(((' ' * (80 + 9)) + '00000000' + (' ' * 12)) * 2)

        # Footer of page 1
        rslt += self._l10n_es_boe_format_string(' ' * (21 + 13 + 20 + 150))  # Reserved for AEAT
        rslt += self._l10n_es_boe_format_string('</T39001000>')

        return rslt

    def _generate_mod_390_page2(self, options, casilla_lines_map):
        # Operations carried out under the general regime : accrued VAT
        # Header
        rslt = self._l10n_es_boe_format_string('<T39002000> ')
        casillas = [700, 701, 667, 668, 1, 2, 702, 703, 669, 670, 3, 4, 5, 6, 704, 705, 671, 672,
        500, 501, 706, 707, 673, 674, 502, 503, 504, 505, 708, 709, 675, 676, 643, 644, 710, 711,
        677, 678, 645, 646, 647, 648, 712, 713, 679, 680, 7, 8, 714, 715, 681, 682, 9, 10, 11, 12,
        13, 14, 716, 717, 683, 684, 21, 22, 718, 719, 685, 686, 23, 24, 25, 26, 720, 721, 687, 688,
        545, 546, 722, 723, 689, 690, 547, 548, 551, 552, 27, 28, 29, 30, 649, 650, 31, 32, 33, 34]
        for casilla in casillas:
            rslt += self._l10n_es_boe_format_number(options, casilla_lines_map[f'{casilla:02d}'],
                                                    length=17, decimal_places=2, signed=True, in_currency=True)
        # Blank space for AEAT
        rslt += self._l10n_es_boe_format_string(' ' * 150)
        # Footer
        rslt += self._l10n_es_boe_format_string('</T39002000>')

        return rslt

    def _generate_mod_390_page2b(self, options, casilla_lines_map):
        # Header
        rslt = self._l10n_es_boe_format_string('<T39002B00> ')
        rslt += self._l10n_es_boe_format_string('0' * (17 * 4))  # Reserve space for fields 663, 664, 691, and 692 (4 fixed-width values of 17 characters each)
        casillas = [35, 36]
        for casilla in casillas:
            rslt += self._l10n_es_boe_format_number(options, casilla_lines_map[str(casilla)],
                                                    length=17, decimal_places=2, signed=True, in_currency=True)
        rslt += self._l10n_es_boe_format_string('0' * (17 * 4))  # Reserve space for fields 665, 666, 693, and 694 (4 fixed-width values of 17 characters each)
        casillas = [599, 600, 601, 602, 41, 42, 43, 44, 45, 46, 47]
        for casilla in casillas:
            rslt += self._l10n_es_boe_format_number(options, casilla_lines_map[str(casilla)],
                                                    length=17, decimal_places=2, signed=True, in_currency=True)
        # Blank space for AEAT
        rslt += self._l10n_es_boe_format_string(' ' * 150)
        # Footer
        rslt += self._l10n_es_boe_format_string('</T39002B00>')

        return rslt

    def _generate_mod_390_page3(self, options, casilla_lines_map):
        # Operations carried out under the general regime : VAT deductible
        # Header
        rslt = self._l10n_es_boe_format_string('<T39003000> ')

        # Casillas
        casillas = [695, 696, 190, 191, 724, 725, 697, 698, 603, 604, 605, 606, 48, 49, 745, 746,
        506, 507, 726, 727, 747, 748, 607, 608, 609, 610, 512, 513, 749, 750, 196, 197, 728, 729,
        751, 752, 611, 612, 613, 614, 50, 51, 753, 754, 514, 515, 730, 731, 755, 756, 615, 616, 617,
        618, 520, 521, 757, 758, 202, 203, 732, 733, 759, 760, 619, 620, 621, 622, 52, 53, 761, 762,
        208, 209, 734, 735, 763, 764, 623, 624, 625, 626, 54, 55, 765, 766, 214, 215, 736, 737, 767,
        768, 627, 628, 629, 630, 56, 57]
        for casilla in casillas:
            rslt += self._l10n_es_boe_format_number(options, casilla_lines_map[str(casilla)],
                                                    length=17, decimal_places=2, signed=True, in_currency=True)

        # Blank space for AEAT
        rslt += self._l10n_es_boe_format_string(' ' * 150)
        # Footer
        rslt += self._l10n_es_boe_format_string('</T39003000>')

        return rslt

    def _generate_mod_390_page4(self, options, casilla_lines_map):
        #Header
        rslt = self._l10n_es_boe_format_string('<T39004000> ')
        # Casillas
        casillas = [769, 770, 220, 221, 738, 739, 771, 772, 631, 632, 633, 634, 58, 59, 773, 774,
        587,588, 740, 741, 775, 776, 635, 636, 637, 638, 597, 598, 60, 61, 660, 661, 639, 62, 651,
        652, 63, 522, 64, 65]
        for casilla in casillas:
            rslt += self._l10n_es_boe_format_number(options, casilla_lines_map[str(casilla)],
                                                    length=17, decimal_places=2, signed=True, in_currency=True)
        # Blank space for AEAT
        rslt += self._l10n_es_boe_format_string(' ' * 150)
        # Footer
        rslt += self._l10n_es_boe_format_string('</T39004000>')

        return rslt

    def _generate_mod_390_page6(self, options, casilla_lines_map):
        # Header
        rslt = self._l10n_es_boe_format_string('<T39006000> ')
        # Section 7  : Annual settlement result (Only for taxpayers who are taxed exclusively in common territory)
        # Casillas
        rslt += self._l10n_es_boe_format_number(options, casilla_lines_map['658'], length=17, decimal_places=2, signed=True, in_currency=True)
        rslt += self._l10n_es_boe_format_number(options, casilla_lines_map['84'], length=17, decimal_places=2, signed=True, in_currency=True)
        rslt += self._l10n_es_boe_format_number(options, casilla_lines_map['659'], length=17, decimal_places=2, in_currency=True)
        rslt += self._l10n_es_boe_format_number(options, casilla_lines_map['85'], length=17, decimal_places=2, in_currency=True)
        rslt += self._l10n_es_boe_format_number(options, casilla_lines_map['86'], length=17, decimal_places=2, signed=True, in_currency=True)
        # We don't cover the section 8 of the modelo 390, the casillas are replaced by zeros.
        # 87 --> 91: Administraciones : Territorio commùn (5), Álava (5), Guipúzcoa(5), Vizcaya(5), Navarra(5)
        rslt += self._l10n_es_boe_format_string('0' * 5 * 5)
        # 658 : Administraciones - Regularización cuotas art. 80.Cinco.5ª LIVA (17)
        # 84 : Administraciones - Suma de resultados (17)
        # 92 : Administraciones - Resultado atribuible a territorio común (17)
        # 659 : Administraciones -IVA a la importación liquidado por la Aduana (17)
        # 93 : Administraciones - Compens. cuotas ej. anterior atrib. territ. com. (17)
        # 94 : Administraciones -Resultado liq. anual atribuible territ. comun (17)
        rslt += self._l10n_es_boe_format_string('0' * 17 * 6)
        # Section 9 : Result of settlements
        #   Periods that are not taxed under the Special Regime of the group of entities
        rslt += self._l10n_es_boe_format_number(options, casilla_lines_map['95'], length=17, decimal_places=2, in_currency=True)
        rslt += self._l10n_es_boe_format_number(options, casilla_lines_map['96'], length=17, decimal_places=2, in_currency=True)
        rslt += self._l10n_es_boe_format_number(options, casilla_lines_map['524'], length=17, decimal_places=2, in_currency=True)
        rslt += self._l10n_es_boe_format_number(options, casilla_lines_map['97'], length=17, decimal_places=2, in_currency=True)
        rslt += self._l10n_es_boe_format_number(options, casilla_lines_map['98'], length=17, decimal_places=2, in_currency=True)
        #   Periods that are taxed under the Special Regime of the group of entities
        rslt += self._l10n_es_boe_format_number(options, casilla_lines_map['662'], length=17, decimal_places=2, in_currency=True)
        rslt += self._l10n_es_boe_format_number(options, casilla_lines_map['525'], length=17, decimal_places=2, in_currency=True)
        rslt += self._l10n_es_boe_format_number(options, casilla_lines_map['526'], length=17, decimal_places=2, in_currency=True)
        # Section 10 : Trading volume
        casillas = [99, 653, 103, 104, 105, 110, 125, 126, 127, 128, 100, 101, 102, 227, 228, 106, 107, 108]
        for casilla in casillas:
            rslt += self._l10n_es_boe_format_number(options, casilla_lines_map[str(casilla)], length=17, decimal_places=2, signed=True, in_currency=True)

        # Blank space for AEAT
        rslt += self._l10n_es_boe_format_string(' ' * 150)
        # Footer
        rslt += self._l10n_es_boe_format_string('</T39006000>')

        return rslt

    def _generate_mod_390_page7(self, options, casilla_lines_map):
        # Header
        rslt = self._l10n_es_boe_format_string('<T39007000> ')

        # Casillas
        # Section 11: Specific operations in the carried out during the year
        casillas = [230, 109, 231, 232, 111, 113, 523]
        for casilla in casillas:
            rslt += self._l10n_es_boe_format_number(options, casilla_lines_map[str(casilla)], length=17, decimal_places=2, signed=True, in_currency=True)
        for casilla in range(654, 658):
            rslt += self._l10n_es_boe_format_number(options, casilla_lines_map[str(casilla)], length=17, decimal_places=2, signed=True, in_currency=True)
        # We don't cover the section 12 of the modelo 390, the casillas are replaced by blank spaces
        for _i in range(0, 5):
            rslt += self._l10n_es_boe_format_string(' ' * 40)  # Prorratas - Actividad desarrollada
            rslt += self._l10n_es_boe_format_string(' ' * 3)  # 12. Prorratas - Código CNAE [114]
            rslt += self._l10n_es_boe_format_string('0' * 17)  # 12. Prorratas - Importe de operaciones [115]
            rslt += self._l10n_es_boe_format_string('0' * 17)  # 12. Prorratas - Importe de operaciones con derecho a deducción [116]
            rslt += self._l10n_es_boe_format_string(' ')  # 12. Prorratas - Tipo de prorrata [117]
            rslt += self._l10n_es_boe_format_string('0' * 5)  # 12. Prorratas - % de prorrata [118]

        # Blank space for AEAT
        rslt += self._l10n_es_boe_format_string(' ' * 150)
        # Footer
        rslt += self._l10n_es_boe_format_string('</T39007000>')

        return rslt

    def _generate_mod_390_page8(self, options, casilla_lines_map):
        # Activities with differentiated deduction regimes
        # Header
        rslt = self._l10n_es_boe_format_string('<T39008000> ')

        # Casillas
        for casilla in range(139, 153):
            rslt += self._l10n_es_boe_format_number(options, casilla_lines_map[str(casilla)], length=17, decimal_places=2, signed=True, in_currency=True)
        rslt += self._l10n_es_boe_format_number(options, casilla_lines_map['640'], length=17, decimal_places=2, signed=True, in_currency=True)
        for casilla in range(153, 170):
            rslt += self._l10n_es_boe_format_number(options, casilla_lines_map[str(casilla)], length=17, decimal_places=2, signed=True, in_currency=True)
        rslt += self._l10n_es_boe_format_number(options, casilla_lines_map['641'], length=17, decimal_places=2, signed=True, in_currency=True)
        for casilla in range(170, 187):
            rslt += self._l10n_es_boe_format_number(options, casilla_lines_map[str(casilla)], length=17, decimal_places=2, signed=True, in_currency=True)
        rslt += self._l10n_es_boe_format_number(options, casilla_lines_map['642'], length=17, decimal_places=2, signed=True, in_currency=True)
        for casilla in range(187, 190):
            rslt += self._l10n_es_boe_format_number(options, casilla_lines_map[str(casilla)], length=17, decimal_places=2, signed=True, in_currency=True)

        # Blank space for AEAT
        rslt += self._l10n_es_boe_format_string(' ' * 150)
        # Footer
        rslt += self._l10n_es_boe_format_string('</T39008000>')

        return rslt

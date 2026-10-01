# Part of Odoo. See LICENSE file for full copyright and licensing details.
import csv
import io

from odoo import _, fields, models
from odoo.models import TableSQL
from odoo.exceptions import UserError, ValidationError
from odoo.tools import SQL
from odoo.addons.l10n_co.tools.partner_identifiers import (
    CO_FOREIGN_ID_DIAN_CODE,
    CO_FOREIGN_VAT_DIAN_CODE,
    CO_NIT_DIAN_CODE,
)
from odoo.addons.l10n_co_edi.models.res_partner import FINAL_CONSUMER_VAT

EXOGENOUS_COUNTRY_CODES = {
    'AF': '13', 'AL': '17', 'DZ': '59', 'AD': '37', 'AO': '40', 'AI': '41',
    'AG': '43', 'AR': '63', 'AM': '26', 'AW': '27', 'AU': '69', 'AT': '72',
    'AZ': '74', 'BS': '77', 'BH': '80', 'BD': '81', 'BB': '83', 'BY': '91',
    'BE': '87', 'BZ': '88', 'BJ': '229', 'BM': '90', 'BO': '97', 'BA': '29',
    'BW': '101', 'BR': '105', 'BN': '108', 'BG': '111', 'BF': '31', 'MM': '93',
    'BI': '115', 'KH': '141', 'CM': '145', 'CA': '149', 'CV': '127', 'TD': '203',
    'CL': '211', 'CN': '215', 'CO': '169', 'CG': '177', 'CR': '196', 'HR': '198',
    'CU': '199', 'CY': '221', 'DK': '232', 'DM': '235', 'EC': '239', 'EG': '240',
    'GQ': '331', 'ER': '243', 'EE': '251', 'ET': '253', 'FO': '259', 'FI': '271',
    'FR': '275', 'GF': '325', 'GA': '281', 'GM': '285', 'GE': '287', 'DE': '23',
    'GH': '289', 'GI': '293', 'GR': '301', 'GL': '305', 'GD': '297', 'GP': '309',
    'GU': '313', 'GT': '317', 'GN': '329', 'GW': '334', 'GY': '337', 'HT': '341',
    'VA': '159', 'HN': '345', 'HK': '351', 'HU': '355', 'IS': '379', 'IN': '361',
    'ID': '365', 'IR': '372', 'IQ': '369', 'IE': '375', 'IL': '383', 'IT': '386',
    'CI': '193', 'JM': '391', 'JP': '399', 'JO': '403', 'KZ': '406', 'KE': '410',
    'KI': '411', 'KR': '190', 'KW': '413', 'KG': '412', 'LA': '420', 'LV': '429',
    'LB': '431', 'LS': '426', 'LR': '434', 'LY': '438', 'LI': '440', 'LT': '443',
    'LU': '445', 'MO': '447', 'MK': '448', 'MG': '450', 'MW': '458', 'MY': '455',
    'MV': '461', 'ML': '464', 'MT': '467', 'MX': '493', 'PH': '267', 'SA': '53',
    'SK': '246', 'SI': '247', 'ES': '245', 'TW': '218', 'SV': '242', 'AE': '244',
    'US': '249'
}
MINOR_AMOUNT_VAT = '222222222'
HEADER_ES419 = {
    'concept': 'CONCEPTO',
    'identification_type': 'TIPO DE DOCUMENTO',
    'vat': 'NUMERO DE IDENTIFICACION/NIT',
    'partner_first_last_name': 'PRIMER APELLIDO DEL INFORMADO',
    'partner_second_last_name': 'SEGUNDO APELLIDO DEL INFORMADO',
    'partner_first_name': 'PRIMER NOMBRE DEL INFORMADO',
    'partner_other_name': 'OTROS NOMBRE DEL INFORMADO',
    'business_name': 'RAZON SOCIAL DEL INFORMADO',
    'address': 'DIRECCION',
    'state_code': 'CODIGO DEL DEPARTAMENTO',
    'city_code': 'CODIGO DEL MUNICIPIO',
    'country_code': 'CODIGO DEL PAIS',
    'vd': 'DV',
}


class AccountGeneralLedgerReportHandler(models.AbstractModel):
    _inherit = 'account.general.ledger.report.handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options)
        if self.env.company.account_fiscal_country_id.code == 'CO':
            options['buttons'].append({
                'name': _('Exogenous Report CSV'),
                'sequence': 30,
                'action': 'l10n_co_reports_open_exogenous_report_wizard',
                'branch_allowed': True,
            })

    def l10n_co_reports_open_exogenous_report_wizard(self, options):
        # Selected companies in systray must be within the same company hierarchy
        # In LATAM, branches with differing VAT is not possible, thus parent company and its branches have the same VAT
        selected_companies = {company['id'] for company in options['companies']}
        same_vat_branch_ids = set(self.env.company._get_branches_with_same_vat().ids)
        if selected_companies - same_vat_branch_ids:
            raise UserError(_("Multiple companies have been selected. Please select one company and/or its branches to export the report."))
        return {
            'type': 'ir.actions.act_window',
            'name': 'Exogenous Reports',
            'res_model': 'l10n_co_reports.exogenous_report.wizard',
            'view_mode': 'form',
            'views': [[self.env.ref('l10n_co_reports.exogenous_report_wizard_form').id, 'form']],
            'target': 'new',
            'context': {'options': options},
        }

    def _l10n_co_reports_get_unprocessed_exogenous_report_data(self, options):
        '''
        Return the exogenous report data from SQL based on the report type

        :param  options list[dict]:        The options from the report handler
        :rtype: list[dict]
        '''
        report_type = options['exogenous_report_type']
        report = self.env['account.report'].browse(options['report_id'])
        domain = report._get_options_domain(options, "strict_range")

        # Query and tables
        query = self.env['account.move.line']._search(domain)
        aml_t = query.table
        account_t = aml_t._join('account_id', kind="LEFT JOIN")
        exogenous_config_t = account_t._join('l10n_co_exogenous_config_ids', kind="LEFT JOIN")
        exogenous_category_t = exogenous_config_t._join('exogenous_category_id', kind="LEFT JOIN")
        query.add_where(SQL("%s = %s", exogenous_config_t.report_type, options['exogenous_report_type']))
        partner_t = aml_t.partner_id
        dian_code = partner_t.l10n_co_dian_id_code
        id_number = partner_t.l10n_co_dian_id_value
        business_name_codes = (CO_NIT_DIAN_CODE, CO_FOREIGN_VAT_DIAN_CODE)
        query.add_join(
            kind='LEFT JOIN LATERAL',
            alias='split_name',
            table=SQL(
                "(SELECT CASE WHEN %s NOT IN %s THEN STRING_TO_ARRAY(%s, ' ') END AS parts)",
                dian_code,
                business_name_codes,
                partner_t.name,
            ),
            condition=SQL('TRUE'),
        )
        split_name_t = TableSQL('split_name', None, query)

        # Default groupby for reports with no concepts
        query.groupby = SQL(
            "%s, %s, %s, %s, %s, %s",
            partner_t.id,
            partner_t.country_id.id,
            partner_t.state_id.id,
            partner_t.city_id.id,
            partner_t.l10n_co_dian_id_code,
            split_name_t.parts,
        )

        # Concept specific additions
        concept_select_sql = []
        if report_type not in ["1005", "1006"]:
            query.groupby = SQL(
                "%s, %s, %s, %s, %s, %s, %s",
                exogenous_config_t.concept,
                partner_t.id,
                partner_t.country_id.id,
                partner_t.state_id.id,
                partner_t.city_id.id,
                partner_t.l10n_co_dian_id_code,
                split_name_t.parts,
            )
            concept_select_sql = [SQL("%s AS concept", exogenous_config_t.concept)]

        # Report specific column additions such as VD, categories, address, state, city, country
        vd_select_sql = []
        if report_type not in ['1001', '1007']:
            # Derived SQL clause from _get_vat_verification_code
            vd_select_sql = [
                SQL(
                    '''(CASE
                            WHEN %(dian_code)s != %(nit_code)s THEN ''
                            WHEN %(id_number)s LIKE %(sep)s THEN SPLIT_PART(%(id_number)s, '-', 2)
                            ELSE RIGHT(%(id_number)s, 1)
                        END) AS vd''',
                    dian_code=dian_code,
                    nit_code=CO_NIT_DIAN_CODE,
                    id_number=id_number,
                    sep='%-%',
                ),
            ]
        category_ids = self.env['l10n_co.exogenous.category'].search([('report_type', '=', report_type)], order='sequence ASC')
        category_select_sql = []
        for category in category_ids:
            # Sum the AMLs based on the category and its value to report
            # Round the sum to the nearest integer as required by the DIAN pre-validator
            # Take the positive value of balance if the account is a liability as required by the DIAN pre-validator
            category_select_sql.append(
                SQL(
                    '''ROUND(SUM(
                        CASE
                            WHEN %(exog_categ_t)s = %(categ)s THEN (
                                CASE
                                    WHEN %(value_to_report)s = 'credit' THEN %(credit)s
                                    WHEN %(value_to_report)s = 'debit' THEN %(debit)s
                                    WHEN %(value_to_report)s = 'balance' THEN (
                                        CASE
                                            WHEN %(account_type)s LIKE %(pattern)s THEN -%(balance)s
                                            ELSE %(balance)s
                                        END)
                                END)
                            ELSE 0
                        END), 0) AS categ_%(categ_id)s''',
                    exog_categ_t=exogenous_category_t.id,
                    categ=category.id,
                    value_to_report=exogenous_config_t.value_to_report,
                    credit=aml_t.credit,
                    debit=aml_t.debit,
                    account_type=account_t.account_type,
                    pattern="liability_%",
                    balance=aml_t.balance,
                    categ_id=category.id,
                ),
            )
        location_select_sql = []
        if report_type not in ['1007', '1005', '1006']:
            location_select_sql.extend([
                SQL("(CASE WHEN %s = 'CO' THEN %s ELSE NULL END) AS address", partner_t.country_id.code, partner_t.street),
                SQL("TO_CHAR(%s, 'FM00') AS state_code", partner_t.state_id.l10n_co_edi_code),
                SQL("RIGHT(CAST(%s AS VARCHAR(10)), 3) AS city_code", partner_t.city_id.l10n_co_edi_code)
            ])
        if report_type not in ['1003', '1005', '1006']:
            location_select_sql.append(SQL("%s AS country_code", partner_t.country_code))

        # Select query to execute
        query_sql = query.select(
            *concept_select_sql,
            SQL(
                "(CASE WHEN %s != 'CO' THEN %s ELSE %s END) AS identification_type",
                partner_t.country_id.code,
                CO_FOREIGN_ID_DIAN_CODE,
                dian_code,
            ),
            # Derived from _get_vat_without_verification_code for VAT
            SQL(
                '''(CASE
                        WHEN %(dian_code)s != %(nit_code)s OR %(id_number)s = %(final_consumer_vat)s THEN %(id_number)s
                        WHEN %(id_number)s LIKE %(sep)s THEN SPLIT_PART(%(id_number)s, '-', 1)
                        ELSE LEFT(%(id_number)s, LENGTH(%(id_number)s)-1)
                    END) AS vat''',
                dian_code=dian_code,
                nit_code=CO_NIT_DIAN_CODE,
                id_number=id_number,
                final_consumer_vat=FINAL_CONSUMER_VAT,
                sep='%-%'
            ),
            *vd_select_sql,
            SQL("split_name.parts[3] AS partner_first_last_name"),
            SQL("split_name.parts[4] AS partner_second_last_name"),
            SQL("split_name.parts[1] AS partner_first_name"),
            SQL("split_name.parts[2] AS partner_other_name"),
            SQL("(CASE WHEN %s IN %s THEN %s END) AS business_name", dian_code, business_name_codes, partner_t.name),
            *location_select_sql,
            *category_select_sql,
        )
        self.env.cr.execute(query_sql)

        return self.env.cr.dictfetchall()

    def _is_category_key(self, key):
        '''
        Returns whether the key is a category or not

        :param key: a string representing a key/header
        :rtype: bool
        '''
        return key.startswith('categ_')

    def _l10n_co_reports_get_minor_amount_row(self, company, report_keys):
        '''
        Return the minor amount row generic data

        :param  company: the current company generating the report
        :param  report_keys: the keys from the exogenous report data
        :rtype: dict
        '''
        row = {k: 0 if self._is_category_key(k) else '' for k in report_keys}
        row.update({
            'identification_type': '43',
            'vat': MINOR_AMOUNT_VAT,
            'business_name': 'CUANTIAS MENORES',
        })
        if 'address' in report_keys:
            row['address'] = company.street
        if 'state_code' in report_keys:
            row['state_code'] = f"{company.state_id.l10n_co_edi_code!s:>02}"
        if 'city_code' in report_keys:
            row['city_code'] = str(company.partner_id.city_id.l10n_co_edi_code)[-3:]
        if 'country_code' in report_keys:
            row['country_code'] = company.country_code
        return row

    def _l10n_co_reports_get_concept_minor_amount_rows(self, minor_amount_report_lines, minor_amount_concepts, company, report_keys):
        '''
        Return the minor amount rows per concept

        :param  minor_amount_report_lines: the minor amount lines to be aggregated
        :param  minor_amount_concepts: a set of unique concepts to categorize the minor amounts
        :param  company: the current company generating the report
        :param  report_keys: the keys that should be in the minor amount row
        :rtype: list[dict]
        '''
        # Create the minor amount rows
        category_keys = [k for k in report_keys if self._is_category_key(k)]
        minor_amount_data = {}
        for concept in minor_amount_concepts:
            row = self._l10n_co_reports_get_minor_amount_row(company, report_keys)
            row['concept'] = concept
            minor_amount_data[concept] = row

        # Aggregate the report lines into the minor amount rows
        for line in minor_amount_report_lines:
            for categ in category_keys:
                minor_amount_data[line['concept']][categ] += line[categ]

        return list(minor_amount_data.values())

    def _l10n_co_reports_add_minor_amount_lt_uvt_sum_row(self, company, report_keys, exogenous_report_data, category, max_uvt_amount):
        '''
        Return the exogenous report data with the minor amount rows which is
        the sum of the lines with the given category whose sum is less than the maximum UVT amount,
        grouped by concepts.
        This minor amount rule is used in reports with concepts.

        :param  exogenous_report_data:  the data of the exogenous report to be modified
        :param  category:               the exogenous category the minor amount rule is based on
        :param  max_uvt_amount:         the integer that denotes the threshold for the minor amount rule
        :rtype: list[dict]
        '''
        # Convert the max UVT amount into the company's currency for minor amount comparison
        to_currency = company.currency_id
        from_currency = self.env.ref('l10n_co_reports.uvt')
        max_uvt_to_currency = from_currency._convert(max_uvt_amount, to_currency, company)

        # Determine which lines and concepts are minor amounts
        category_key = f"categ_{category.id}"
        minor_amount_concepts = set()
        for line in exogenous_report_data:
            categ_sum = line[category_key]
            if 0 < categ_sum < max_uvt_to_currency or line['vat'] == FINAL_CONSUMER_VAT:
                minor_amount_concepts.add(line['concept'])
                line['is_minor_amount'] = True

        # Update the exogenous report data by removing the minor amount lines and creating/adding the minor amount rows
        if minor_amount_report_lines := [line for line in exogenous_report_data if line.get('is_minor_amount')]:
            exogenous_report_data = [line for line in exogenous_report_data if not line.get('is_minor_amount')]
            minor_amount_rows = self._l10n_co_reports_get_concept_minor_amount_rows(minor_amount_report_lines, minor_amount_concepts, company, report_keys)
            exogenous_report_data.extend(minor_amount_rows)

        return exogenous_report_data

    def _l10n_co_reports_add_minor_amount_no_partner_sum_row(self, company, report_keys, exogenous_report_data, categories, is_concept=False):
        '''
        Return the exogenous report data with the minor amount row which is
        the sum of the lines with the given category and no partners or the partner is a final consumer,
        grouped by concept if required by report type (e.g Report 1007 uses concepts)

        :param  exogenous_report_data:  the data of the exogenous report to be modified
        :param  categories:             a list of exogenous categories the minor amount rule is based on
        :param  is_concept:             a boolean that denotes whether a report uses concepts or not (Optional)
        :rtype: list[dict]
        '''
        # Gather the minor amount rows information and flag minor amount lines in the data
        category_keys = [f"categ_{category.id}" for category in categories]
        all_category_keys = [k for k in report_keys if self._is_category_key(k)]
        minor_amount_concepts = set()
        for line in exogenous_report_data:
            for key in category_keys:
                if line[key] and (line['vat'] == FINAL_CONSUMER_VAT or (not line['business_name'] and not line['partner_first_name'])):
                    line['is_minor_amount'] = True
                    # Only add concept if it's a minor amount line and the report uses concept
                    if is_concept:
                        minor_amount_concepts.add(line['concept'])
        # Update the exogenous report data by removing the minor amount lines and creating/adding the minor amount rows
        if minor_amount_report_lines := [line for line in exogenous_report_data if line.get('is_minor_amount')]:
            exogenous_report_data = [line for line in exogenous_report_data if not line.get('is_minor_amount')]
            if is_concept:
                minor_amount_rows = self._l10n_co_reports_get_concept_minor_amount_rows(minor_amount_report_lines, minor_amount_concepts, company, report_keys)
                exogenous_report_data.extend(minor_amount_rows)
            else:
                # Aggregate the minor amount lines into one minor amount row for non-concept reports
                row = self._l10n_co_reports_get_minor_amount_row(company, report_keys)
                for line in minor_amount_report_lines:
                    for categ in all_category_keys:
                        row[categ] += line[categ]
                exogenous_report_data.append(row)

        return exogenous_report_data

    def _l10n_co_reports_add_minor_amount_rows(self, options, exogenous_report_data):
        ''' Return the exogenous report data with the minor amount row based on the report type'''
        report_type = options['exogenous_report_type']
        # Company is used for address info in minor amount rows
        # Use the root company if the current company is a branch
        company = self.env['res.company'].browse(options['companies'][0]['id']).root_id
        report_keys = list(exogenous_report_data[0].keys())
        if report_type == '1001':
            exogenous_report_data = self._l10n_co_reports_add_minor_amount_lt_uvt_sum_row(
                company,
                report_keys,
                exogenous_report_data,
                self.env.ref('l10n_co_reports.exogenous_categ_1001_01'),
                3
            )
        elif report_type == '1003':
            exogenous_report_data = self._l10n_co_reports_add_minor_amount_lt_uvt_sum_row(
                company,
                report_keys,
                exogenous_report_data,
                self.env.ref('l10n_co_reports.exogenous_categ_1003_01'),
                3
            )
        elif report_type == '1005':
            exogenous_report_data = self._l10n_co_reports_add_minor_amount_no_partner_sum_row(
                company,
                report_keys,
                exogenous_report_data,
                [
                    self.env.ref('l10n_co_reports.exogenous_categ_1005_01'),
                    self.env.ref('l10n_co_reports.exogenous_categ_1005_02'),
                ],
            )
        elif report_type == '1006':
            exogenous_report_data = self._l10n_co_reports_add_minor_amount_no_partner_sum_row(
                company,
                report_keys,
                exogenous_report_data,
                [self.env.ref('l10n_co_reports.exogenous_categ_1006_02')],
            )
        elif report_type == '1007':
            exogenous_report_data = self._l10n_co_reports_add_minor_amount_no_partner_sum_row(
                company,
                report_keys,
                exogenous_report_data,
                [self.env.ref('l10n_co_reports.exogenous_categ_1007_01')],
                True
            )
        elif report_type == '1008':
            exogenous_report_data = self._l10n_co_reports_add_minor_amount_lt_uvt_sum_row(
                company,
                report_keys,
                exogenous_report_data,
                self.env.ref('l10n_co_reports.exogenous_categ_1008_01'),
                12
            )
        elif report_type == '1009':
            exogenous_report_data = self._l10n_co_reports_add_minor_amount_lt_uvt_sum_row(
                company,
                report_keys,
                exogenous_report_data,
                self.env.ref('l10n_co_reports.exogenous_categ_1009_01'),
                12
            )

        return exogenous_report_data

    def _l10n_co_reports_get_processed_exogenous_report_data(self, options):
        '''
        Process and modify the data that could not be done in SQL and
        return the exogenous report data

        :rtype: list[dict]
        '''
        # Get data from SQL
        if exogenous_report_data := self._l10n_co_reports_get_unprocessed_exogenous_report_data(options):
            # Add minor amount rows
            exogenous_report_data = self._l10n_co_reports_add_minor_amount_rows(options, exogenous_report_data)
            # Process and modify the report data
            for line in exogenous_report_data:
                if country_code := line.get('country_code', ''):
                    line['country_code'] = EXOGENOUS_COUNTRY_CODES.get(country_code, '')
                # if the partner's name has 3 names, partner_second_last_name must be set instead
                if not line['partner_second_last_name'] and not line['business_name']:
                    line['partner_second_last_name'] = line['partner_other_name']
                    line['partner_other_name'] = ''

        return exogenous_report_data

    def l10n_co_reports_exogenous_report_csv_file_generator(self, options):
        ''' Generate the CSV file for the exogenous report type'''
        output = io.StringIO()
        exogenous_report_data = self._l10n_co_reports_get_processed_exogenous_report_data(options)
        if not exogenous_report_data:
            raise ValidationError(_("No journal items match the criteria for this report. Please verify your Chart of Accounts configuration, report filters, and journal entries."))

        header = exogenous_report_data[0].keys()
        custom_header = {k: self.env['l10n_co.exogenous.category'].browse(int(k.split('_')[1])).name.upper() if self._is_category_key(k) else HEADER_ES419[k] for k in header}
        writer = csv.DictWriter(output, fieldnames=header)
        writer.writerow(custom_header)
        writer.writerows(exogenous_report_data)

        return {
            'file_name': f"{options['exogenous_report_type']} - {fields.Date.context_today(self)}.csv",
            'file_content': output.getvalue(),
            'file_type': 'csv',
        }

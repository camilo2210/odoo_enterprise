# Part of Odoo. See LICENSE file for full copyright and licensing details.
from json import dumps, loads

from odoo import api, fields, models
from odoo.tools import SQL
from odoo.fields import Domain


class AccountEcSalesReportHandlerCommon(models.AbstractModel):
    """
        EC Sales Report defining common functions for both the generic (taxes) and
        localization specific (tax tags) custom handlers
        Localizations-specific EC sales reports should not inherit this model,
        but rather the one below: account.ec.sales.with.tags.report.handler
    """
    _name = 'account.ec.sales.report.handler.common'
    _inherit = ['account.report.custom.handler']
    _description = 'Common EC Sales Report Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        options['enable_export_buttons_for_common_vat_in_branches'] = True
        options['custom_display_config'] = {
            'components': {
                'AccountReportFilters': 'SalesReportFilters',
            },
        }

    @api.model
    def _get_ec_country_codes(self, options):
        """
        Return the list of country codes for the EC countries.
        :param dict options: Report options
        :return set: List of country codes for a given date (UK case)
        """
        rslt = {'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR', 'DE', 'GR', 'HU',
                'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL', 'PL', 'PT', 'RO', 'SK', 'SI', 'ES', 'SE', 'XI'}

        # GB left the EU on January 1st 2021. But before this date, it's still to be considered as a EC country
        if fields.Date.from_string(options['date']['date_from']) < fields.Date.from_string('2021-01-01'):
            rslt.add('GB')
        # Monaco is treated as part of France for VAT purposes (but should not be displayed within FR context)
        if self.env.company.account_fiscal_country_id.code != 'FR':
            rslt.add('MC')

        return rslt

    def _get_partner_details_query(self, current_groupby):
        if current_groupby in ('partner_id', 'partner_id_and_sale_type'):
            return SQL("""
                MIN(partner.id) AS partner_id,
                MIN(partner.name) AS partner_name,
                MIN(CASE
                    WHEN LEFT(partner.vat, 2) SIMILAR TO '[A-Za-z]{2}' THEN UPPER(LEFT(partner.vat, 2))
                    ELSE UPPER(COALESCE(country.code, ''))
                END) AS country_code,
                MIN(partner.vat) AS vat_number,
            """)
        return SQL("""
            '' AS partner_id,
            '' AS partner_name,
            '' AS country_code,
            '' AS vat_number,
        """)

    def _format_vat_number(self, full_vat_number):
        """Format VAT number by removing country code if present."""
        if not full_vat_number:
            return ''

        has_country_prefix = len(full_vat_number) >= 2 and full_vat_number[:2].isalpha()
        return full_vat_number[2:] if has_country_prefix else full_vat_number

    def _get_duplicate_vat_partners(self, duplicate_partners_vat):
        view_ref = self.env.ref('account_reports.duplicate_vat_partner_tree_view', raise_if_not_found=False)
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Partners with duplicate VAT numbers'),
            'context': {'group_by': 'vat', 'expand': 1, 'duplicate_partners_vat': duplicate_partners_vat},
            'views': [(view_ref and view_ref.id or False, 'list'), (False, 'form')],
            'res_model': 'res.partner',
            'domain': [('vat', 'in', duplicate_partners_vat)],
        }

    @api.model
    def _get_ec_sales_tax_tags(self):
        """ To override in localizations
            Should contain the sales types as keys, with a list of account tags as values
        """
        return {}


class AccountEcSalesWithTaxesReportHandler(models.AbstractModel):
    """ Generic EC Sales Report handler
        Localization-specific EC sales reports should not inherit this handler,
        but rather the one below: AccountEcSalesReportHandlerUsingTags
    """

    _name = 'account.ec.sales.with.taxes.report.handler'
    _inherit = ['account.ec.sales.report.handler.common']
    _description = 'EC Sales Report (with taxes) Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        country_ids = self.env['res.country'].search([
            ('code', 'in', tuple(self._get_ec_country_codes(options)))
        ]).ids
        other_country_ids = tuple(set(country_ids) - {self.env.company.account_fiscal_country_id.id})

        options.setdefault('forced_domain', []).extend([
            '|',
            ('move_id.partner_shipping_id.country_id', 'in', other_country_ids),
            '&',
            ('move_id.partner_shipping_id', '=', False),
            ('partner_id.country_id', 'in', other_country_ids),
        ])

        eu_countries = self.env.ref('base.europe').country_ids
        ec_sales_taxes_to_include = self.env['account.tax'].search([
            *self.env['account.tax']._check_company_domain(report.get_report_company_ids(options)),
            ('amount', '=', 0.0),
            ('amount_type', '=', 'percent'),
            ('type_tax_use', '=', 'sale'),
            ('country_id', 'in', eu_countries.ids),
        ]).ids
        options['ec_sales_taxes_to_include'] = ec_sales_taxes_to_include

    def _report_engine_ec_sales_report(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        """ Custom engine for EC Sales Report """
        report = self.env['account.report'].browse(options['report_id'])
        report_query = report._get_report_query(options, 'strict_range')
        if current_groupby:
            report._check_groupby_fields([current_groupby])
        groupby_sql = SQL('') if not current_groupby else self.env['account.move.line']._field_to_sql("account_move_line", current_groupby, report_query)

        ec_sales_taxes_to_include = tuple(options['ec_sales_taxes_to_include']) or (None,)
        if not ec_sales_taxes_to_include and warnings is not None:
            warnings['account_reports.sales_report_warning_no_taxes_to_include'] = {'alert_type': 'warning'}

        query = SQL(
            """
            SELECT
                %(grouping_key)s
                %(partner_details)s
                COALESCE(-SUM(%(balance)s), 0.0) AS balance
            FROM
                %(from_clause)s
                LEFT JOIN res_partner partner ON partner.id = account_move_line.partner_id
                JOIN res_country country ON partner.country_id = country.id
            WHERE
                %(where_clause)s
                AND EXISTS (
                    SELECT 1
                    FROM account_move_line_account_tax_rel aml_tax_rel
                    WHERE aml_tax_rel.account_move_line_id = account_move_line.id
                      AND aml_tax_rel.account_tax_id IN %(ec_sales_taxes_to_include)s
                    LIMIT 1
                )
            %(group_by_sql)s
            %(order_by_sql)s
            """,
            ec_sales_taxes_to_include=ec_sales_taxes_to_include,
            grouping_key=SQL('%s AS grouping_key,', groupby_sql) if groupby_sql else SQL(),
            partner_details=self._get_partner_details_query(current_groupby),
            balance=report_query.table.consolidation_balance,
            from_clause=report_query.from_clause,
            where_clause=report_query.where_clause,
            group_by_sql=SQL('GROUP BY %s', groupby_sql) if groupby_sql else SQL(),
            order_by_sql=SQL('ORDER BY %s', groupby_sql) if groupby_sql else SQL(),
        )

        self.env.cr.execute(query)
        query_res_lines = self.env.cr.dictfetchall()

        # Post-process values
        for res in query_res_lines:
            if res['vat_number']:
                res['vat_number'] = self._format_vat_number(res['vat_number'])

        if not current_groupby:
            return {next(iter(formulas_dict.values())): {
                'country_code': '',
                'vat_number': '',
                'balance': query_res_lines[0]['balance'],
                'has_sublines': True,
            }}

        else:
            return {next(iter(formulas_dict.values())): [
                (res['grouping_key'],
                 {
                     'country_code': res['country_code'],
                     'vat_number': res['vat_number'],
                     'balance': res['balance'],
                     'has_sublines': True,
                 })
                for res in query_res_lines
            ]}


class AccountEcSalesWithTagsReportHandler(models.AbstractModel):
    _name = 'account.ec.sales.with.tags.report.handler'
    _inherit = ['account.ec.sales.report.handler.common']
    _description = 'EC Sales Report (with tags) Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)

        options['sales_report_operation_types'] = options.get('sales_report_operation_types') or previous_options.get('sales_report_operation_types', {})

        # Add filter for sale type (only for reports using the custom groupby)
        if report.line_ids.filtered(lambda l: l._get_groupby(options) == 'partner_id_and_sale_type'):

            # Filter on Tax Code
            filter_sale_type_selection = [
                {
                    'id': sale_type_key,
                    'name': sale_type_val['name'],
                    'selected': True,
                }
                for sale_type_key, sale_type_val in options['sales_report_operation_types'].items()
            ]

            options['filter_sale_type_selection'] = previous_options.get('filter_sale_type_selection') or filter_sale_type_selection

            # If none are selected, select them all
            if all(not item['selected'] for item in options['filter_sale_type_selection']):
                for item in options['filter_sale_type_selection']:
                    item['selected'] = True

    def _report_engine_ec_sales_report(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        """ Custom engine for EC Sales Report """
        report = self.env['account.report'].browse(options['report_id'])
        if current_groupby:
            report._check_groupby_fields([current_groupby])
        report_query = report._get_report_query(options, 'strict_range')

        groupby_sql = (
            SQL() if not current_groupby
            else SQL('partner.id, sale_type') if current_groupby == 'partner_id_and_sale_type'
            else self.env['account.move.line']._field_to_sql('account_move_line', current_groupby, report_query)
        )

        sum_by_sale_type = SQL(' ').join([
            SQL(
                """
                COALESCE(SUM(
                    CASE WHEN aml_id_sale_type.sale_type = %(sale_type)s
                    THEN -%(balance)s ELSE 0 END
                ), 0) AS %(sale_type_alias)s,
                """,
                sale_type=sale_type,
                sale_type_alias=SQL.identifier(sale_type),
                balance=report_query.table.consolidation_balance,
            )
            for sale_type in options['sales_report_operation_types']
        ])

        ec_sales_warnings = SQL("""
            BOOL_OR(partner.vat IS NULL) AS warning_missing_vat,
            BOOL_OR(
                (
                    delivery_country.code IS NULL
                    AND UPPER(COALESCE(country.code, '')) NOT IN %(ec_country_codes)s
                )
                OR (
                    delivery_country.code IS NOT NULL
                    AND UPPER(delivery_country.code) NOT IN %(ec_country_codes)s
                )
            ) AS warning_non_ec_country,
            BOOL_OR(
                (
                    delivery_address.country_id IS NULL
                    AND partner.country_id = comp_partner.country_id
                )
                OR (
                    delivery_address.country_id IS NOT NULL
                    AND delivery_address.country_id = comp_partner.country_id
                )
            ) AS warning_same_country,
            """,
            ec_country_codes=tuple(self._get_ec_country_codes(options)) + ('',)
        ) if warnings is not None else SQL()

        query = SQL(
            """
            WITH aml_id_sale_type AS (
                SELECT DISTINCT
                    account_account_tag_account_move_line_rel.account_move_line_id,
                    CASE %(sale_type_statements)s ELSE '' END AS sale_type
                FROM account_account_tag_account_move_line_rel
                JOIN account_account_tag ON account_account_tag_account_move_line_rel.account_account_tag_id = account_account_tag.id
                WHERE CASE %(sale_type_statements)s ELSE NULL END IS NOT NULL
            )
            SELECT
                %(grouping_key)s
                %(partner_details)s
                %(sum_by_sale_type)s
                %(sale_type)s
                %(warnings)s
                COALESCE(-SUM(%(balance)s), 0.0) AS balance
            FROM
                %(from_clause)s
                LEFT JOIN res_partner partner ON partner.id = account_move_line.partner_id
                JOIN aml_id_sale_type ON aml_id_sale_type.account_move_line_id = account_move_line.id
                JOIN res_country country ON partner.country_id = country.id
                JOIN res_company ON res_company.id = account_move_line.company_id
                JOIN res_partner comp_partner ON comp_partner.id = res_company.partner_id
                JOIN account_move ON account_move.id = account_move_line.move_id
                LEFT JOIN res_partner delivery_address ON account_move.partner_shipping_id = delivery_address.id
                LEFT JOIN res_country delivery_country ON delivery_address.country_id = delivery_country.id
            WHERE %(where_clause)s
            %(groupby_clause)s
            %(orderby_clause)s
            """,
            sale_type_statements=self._build_sale_type_statements(options),
            grouping_key=SQL('%s AS grouping_key,', groupby_sql or ''),
            partner_details=self._get_partner_details_query(current_groupby),
            sum_by_sale_type=sum_by_sale_type,
            sale_type=SQL("%s AS sale_type,", SQL("MIN(aml_id_sale_type.sale_type)") if current_groupby == 'partner_id_and_sale_type' else ''),
            warnings=ec_sales_warnings,
            balance=report_query.table.consolidation_balance,
            from_clause=report_query.from_clause,
            where_clause=report_query.where_clause,
            groupby_clause=SQL('GROUP BY %s', groupby_sql) if groupby_sql else SQL(),
            orderby_clause=SQL('ORDER BY %s', groupby_sql) if groupby_sql else SQL(),
        )

        self.env.cr.execute(query)
        query_res_lines = self.env.cr.dictfetchall()

        if not current_groupby:

            if warnings is not None:
                for key, value in query_res_lines[0].items():
                    if key.startswith('warning') and value:
                        warning_key = f'account_reports.sales_report_{key}'
                        warnings[warning_key] = {'alert_type': 'warning'}

            return {next(iter(formulas_dict.values())): {
                'country_code': '',
                'vat_number': '',
                'sale_type': '',
                'sale_type_name': '',
                'sale_type_shortcut': '',
                'balance': query_res_lines[0]['balance'],
                'has_sublines': True,
                **{
                    sale_type: query_res_lines[0].get(sale_type, '') if query_res_lines else ''
                    for sale_type in options['sales_report_operation_types']
                }
            }}

        results = []
        for res in query_res_lines:

            # Define grouping key
            if current_groupby == 'partner_id_and_sale_type':
                grouping_keys = ('partner_id', 'sale_type')
                grouping_key = {key: res[key] for key in grouping_keys}
                grouping_key['tax_tag_ids'] = options['sales_report_operation_types'][res['sale_type']]['tax_tag_ids']
                grouping_key = dumps(grouping_key)
            else:
                grouping_key = res['grouping_key']

            # Post-process values
            if res['vat_number']:
                res['vat_number'] = self._format_vat_number(res['vat_number'])

            sale_type = res['sale_type']
            if sale_type and options['sales_report_operation_types'][sale_type].get('name'):
                res['sale_type_name'] = options['sales_report_operation_types'][sale_type]['name']
            if sale_type and options['sales_report_operation_types'][sale_type].get('shortcut'):
                res['sale_type_shortcut'] = options['sales_report_operation_types'][sale_type]['shortcut']

            results.append(
                (grouping_key,
                 {
                     'country_code': res['country_code'],
                     'vat_number': res['vat_number'],
                     'sale_type': res['sale_type'],
                     'sale_type_name': res.get('sale_type_name', ''),
                     'sale_type_shortcut': res.get('sale_type_shortcut', ''),
                     'balance': res['balance'],
                     'has_sublines': True,
                     **{
                         sale_type: res.get(sale_type, '')
                         for sale_type in options['sales_report_operation_types']
                     }
                 })
            )

        return {next(iter(formulas_dict.values())): results}

    def _build_sale_type_statements(self, options):
        """Build CASE statements for sale types."""
        not_selected_filters = {item['id'] for item in options.get('filter_sale_type_selection', []) if not item['selected']}

        return SQL(' ').join([
            SQL(
                "WHEN account_account_tag.id = ANY(%(tax_tag_ids)s) THEN %(sale_type)s",
                tax_tag_ids=list(data['tax_tag_ids']),
                sale_type=sale_type,
            )
            for sale_type, data in options['sales_report_operation_types'].items() if sale_type not in not_selected_filters
        ])

    def action_audit_cell(self, options, params):
        report_line = self.env['account.report.line'].browse(params['report_line_id'])
        action = report_line.report_id.action_audit_cell(options, params)
        tax_tag_ids = list({
            tag
            for sale_type in options['sales_report_operation_types'].values()
            for tag in sale_type['tax_tag_ids']
        })
        action['domain'] &= Domain('tax_tag_ids', 'in', tax_tag_ids)
        return action

    def _get_custom_groupby_map(self):

        def ec_sales_report_domain_builder(grouping_key):
            grouping_key_dict = loads(grouping_key)
            tax_tag_ids = grouping_key_dict['tax_tag_ids']
            return Domain([
                ('partner_id', '=', grouping_key_dict['partner_id']),
                ('tax_tag_ids', 'in', tax_tag_ids),
            ])

        def ec_sales_report_label_builder(grouping_keys):
            parsed_keys = [loads(k) for k in grouping_keys]
            partner_ids = [k['partner_id'] for k in parsed_keys]

            partners = self.env['res.partner'].browse(partner_ids)
            partner_names = {p.id: p.display_name for p in partners}

            return {
                grouping_key: partner_names[parsed['partner_id']]
                for grouping_key, parsed in zip(grouping_keys, parsed_keys)
            }

        return {
            "partner_id_and_sale_type": {
                'model': None,
                'domain_builder': ec_sales_report_domain_builder,
                'label_builder': ec_sales_report_label_builder,
            },
        }

    def _caret_options_initializer(self):
        """
        Add custom caret option for the report to link to the partner.
        """
        return {
            'partner_id_and_sale_type': [
                {'name': self.env._("View Partner"), 'action': 'caret_options_open_partner_record_form'},
            ],
        }

    def caret_options_open_partner_record_form(self, options, params):
        report = self.env['account.report'].browse(options['report_id'])
        partner_id = loads(report._parse_line_id(params['line_id'])[-1][2])['partner_id']

        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'res_model': 'res.partner',
            'res_id': partner_id,
        }

    def _custom_groupby_line_completer(self, report, options, line_data, current_groupby):
        if current_groupby == 'partner_id_and_sale_type':
            line_data.caret_options = 'partner_id_and_sale_type'

    def get_warning_act_window(self, options, params):
        act_window = {'type': 'ir.actions.act_window', 'context': {}}

        type_mapping = {
            'no_vat': {
                'aml_domain': [
                    ('partner_id.vat', '=', None),
                    ('partner_id.country_id.code', 'in', tuple(self._get_ec_country_codes(options))),
                ],
                'name': self.env._("Entries with partners with no VAT"),
                'context': {'search_default_group_by_partner': 1, 'expand': 1}
            },
            'non_ec_country': {
                'aml_domain': [
                    '|',
                    '&',
                    ('move_id.partner_shipping_id', '!=', False),
                    ('move_id.partner_shipping_id.country_id.code', 'not in', tuple(self._get_ec_country_codes(options))),
                    '&',
                    ('move_id.partner_shipping_id', '=', False),
                    ('partner_id.country_id.code', 'not in', tuple(self._get_ec_country_codes(options)))
                ],
                'name': self.env._("EC tax on non EC countries")
            },
            'same_country': {
                'aml_domain': [
                    '|',
                    '&',
                    ('move_id.partner_shipping_id', '!=', False),
                    ('move_id.partner_shipping_id.country_id', '=', self.env.company.account_fiscal_country_id.id),
                    '&',
                    ('move_id.partner_shipping_id', '=', False),
                    ('partner_id.country_id', '=', self.env.company.account_fiscal_country_id.id)
                ],
                'name': self.env._("EC tax on same country")
            }
        }

        type_info = type_mapping.get(params['type'], {})
        aml_domain = type_info.get('aml_domain', [])
        act_window['name'] = type_info.get('name', '')
        act_window['context'].update(type_info.get('context', {}))

        not_allowed_sale_types = {sale_type['id'] for sale_type in options.get('filter_sale_type_selection', []) if not sale_type.get('selected', True)}

        ec_sales_tag_ids = {
            tag
            for sale_type in options['sales_report_operation_types']
            if sale_type not in not_allowed_sale_types
            for tag in options['sales_report_operation_types'][sale_type]['tax_tag_ids']
        }

        amls = self.env['account.move.line'].search([
            *aml_domain,
            ('parent_state', '=', 'posted'),
            *self.env['account.report']._get_options_date_domain(options, 'strict_range'),
            ('tax_tag_ids', 'in', tuple(ec_sales_tag_ids))
        ])

        if params['model'] == 'move':
            act_window.update({
                'views': [[self.env.ref('account.view_move_tree').id, 'list'], (False, 'form')],
                'res_model': 'account.move',
                'domain': [('id', 'in', amls.move_id.ids)],
            })
        else:
            act_window.update({
                'views': [(False, 'list'), (False, 'form')],
                'res_model': 'res.partner',
                'domain': [('id', 'in', amls.move_id.partner_id.ids)],
            })

        return act_window

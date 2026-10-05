from odoo import models
from odoo.addons.account_reports.utils.report_data_objects import AccountReportColumnFormatParamsData
from odoo.tools import SQL

import json


GROUPED_ACCOUNT_TYPES = {
    'receivable': {'types': ('asset_receivable',), 'counterpart': 'payable'},
    'payable': {'types': ('liability_payable',), 'counterpart': 'receivable'},
    'current_assets': {'types': ('asset_current', 'asset_prepayments'), 'counterpart': 'current_liabilities'},
    'current_liabilities': {'types': ('liability_current', 'liability_credit_card'), 'counterpart': 'current_assets'},
    'income': {'types': ('income', 'income_other'), 'counterpart': 'expense'},
    'expense': {'types': ('expense', 'expense_other', 'expense_depreciation', 'expense_direct_cost'), 'counterpart': 'income'},
    'non_current_assets': {'types': ('asset_fixed', 'asset_non_current'), 'counterpart': 'equity_and_non_cur_liabilities'},
    'equity_and_non_cur_liabilities': {'types': ('equity', 'equity_unaffected', 'liability_non_current'), 'counterpart': 'non_current_assets'},
    'liquidity': {'types': ('asset_cash',), 'counterpart': 'liquidity'},
    'off_balance': {'types': ('off_balance',), 'counterpart': 'off_balance'},
}


class IntercoComparisonReportHandler(models.AbstractModel):
    _name = 'account.interco.comparison.report.handler'
    _inherit = ['account.report.custom.handler']
    _description = "Interco Comparison Report Custom Handler"

    def _custom_options_initializer(self, report, options, previous_options):
        main_company_col_opt = next((col_opt for col_opt in options['columns'] if col_opt['expression_label'] == 'main_company'), {})
        main_company_col_opt['name'] = self.env.company.name

        options['ignore_totals_below_sections'] = True

        companies = self.env['res.company'].browse(report.get_report_company_ids(options))
        counterpart_companies = companies - self.env.company
        options['forced_domain'] = [
            *options.get('forced_domain', []),
            ('move_id.exchange_diff_partial_ids', '=', False),
            '|',
                '&', ('partner_id', 'in', counterpart_companies.partner_id.ids), ('company_id', '=', self.env.company.id),
                '&', ('partner_id', '=', self.env.company.partner_id.id), ('company_id', 'in', counterpart_companies.ids),
        ]

        options['hide_tax_lines'] = (previous_options or {}).get('hide_tax_lines', True)

        if options['hide_tax_lines']:
            options['forced_domain'].append(('tax_line_id', '=', False))

        options['custom_display_config'] = {
            'components': {
                'AccountReportFilters': 'IntercoComparisonReportFilters',
            },
        }

    def _customize_warnings(self, report, options, all_column_groups_expression_totals, warnings):
        if len(options['companies']) == 1:
            warnings['account_reports.interco_comparison_single_company_warning'] = {'alert_type': 'warning'}

    def _report_engine_interco_comparison(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        report = self.env['account.report'].browse(options['report_id'])

        if current_groupby:
            report._check_groupby_fields([current_groupby])
        else:
            return {next(iter(formulas_dict.values())): {'has_sublines': True, 'main_company': None, 'counterpart': None, 'difference': None}}

        query = report._get_report_query(options, date_scope)

        aml_table = query.table._sudo()

        if current_groupby == 'interco_company':
            aml_company_table = aml_table._join('company_id')
            query.groupby = SQL(
                """
                    CASE WHEN %(company_id_field)s = %(main_company_id)s THEN %(partner_id_field)s
                    ELSE %(company_partner_field)s
                    END
                """,
                company_id_field=aml_table.company_id,
                main_company_id=self.env.company.id,
                partner_id_field=aml_table.partner_id,
                company_partner_field=aml_company_table.partner_id,
            )
        elif current_groupby == 'interco_account_type':
            groupby_sql_parts = []
            for grouping_key, grouping_rule in GROUPED_ACCOUNT_TYPES.items():
                groupby_sql_parts.append(SQL(
                    "WHEN %(company_id_field)s = %(main_company_id)s AND %(account_type_field)s IN %(account_types)s THEN %(grouping_key)s",
                    company_id_field=aml_table.company_id,
                    main_company_id=self.env.company.id,
                    account_type_field=aml_table.account_type,
                    account_types=grouping_rule['types'],
                    grouping_key=grouping_key,
                ))

                groupby_sql_parts.append(SQL(
                    "WHEN %(company_id_field)s != %(main_company_id)s AND %(account_type_field)s IN %(account_types)s THEN %(grouping_key)s",
                    company_id_field=aml_table.company_id,
                    main_company_id=self.env.company.id,
                    account_type_field=aml_table.account_type,
                    account_types=GROUPED_ACCOUNT_TYPES[grouping_rule['counterpart']]['types'],
                    grouping_key=grouping_key,
                ))

            query.groupby = SQL(
                """
                    CASE
                    %(groupby_parts)s
                    ELSE 'unknown'
                    END
                """,
                groupby_parts=SQL('\n').join(groupby_sql_parts),
            )
        elif current_groupby == 'interco_account':
            aml_account_table = aml_table._join('account_id')
            query.groupby = SQL(
                """
                    JSON_BUILD_OBJECT(
                        'account_id', %(account_id_field)s,
                        'code', COALESCE(%(account_table)s.code_store->>%(company_id_field)s::VARCHAR),
                        'name', %(account_name_field)s,
                        'company_id', %(company_id_field)s
                    )::VARCHAR
                """,
                account_id_field=aml_table.account_id,
                account_table=aml_account_table,
                account_name_field=aml_account_table.name,
                company_id_field=aml_table.company_id,
            )
        else:
            query.groupby = aml_table[current_groupby]

        sql = query.select(SQL(
            """
                %(grouping_key)s AS grouping_key,
                SUM(CASE WHEN %(company_field)s = %(main_company_id)s THEN %(amount_currency_field)s ELSE 0 END) AS main_company_amount,
                SUM(CASE WHEN %(company_field)s != %(main_company_id)s THEN %(amount_currency_field)s ELSE 0 END) AS counterpart_amount
            """,
            grouping_key=query.groupby,
            company_field=aml_table.company_id,
            main_company_id=self.env.company.id,
            amount_currency_field=aml_table.amount_currency,
        ))

        rslt = []
        for query_res in self.env.execute_query_dict(sql):
            main_company_amount = query_res['main_company_amount']
            counterpart_amount = query_res['counterpart_amount']
            rslt.append((
                query_res['grouping_key'],
                {'has_sublines': True, 'main_company': main_company_amount, 'counterpart': counterpart_amount, 'difference': main_company_amount + counterpart_amount},
            ))

        return {next(iter(formulas_dict.values())): rslt}

    def _custom_groupby_line_completer(self, report, options, line_data, current_groupby):
        if current_groupby in ('currency_id', 'interco_company'):
            line_data.unfolded = True

    def _custom_line_postprocessor(self, report, options, lines):
        for line in lines:
            related_currency_id = report._get_res_id_from_line_id(line.id, 'res.currency')
            related_currency = self.env['res.currency'].browse(related_currency_id)

            for col_data in line.columns:
                col_data.format_params = AccountReportColumnFormatParamsData(digits=related_currency.decimal_places)

                if not col_data.is_zero:
                    col_data.css_class = ' '  # Makes sure negative amounts aren't displayed in red (no style is applied when the css_class key is set)

        return lines

    def _get_custom_groupby_map(self):
        def interco_company_domain_builder(grouping_key):
            return [
                '|',
                '&', ('company_id', '=', self.env.company.id), ('partner_id', '=', grouping_key),
                '&', ('company_id', '!=', self.env.company.id), ('company_id.partner_id', '=', grouping_key),
            ]

        def interco_account_type_domain_builder(grouping_key):
            grouped_acc_type = GROUPED_ACCOUNT_TYPES[grouping_key]
            counterpart_acc_type = GROUPED_ACCOUNT_TYPES[grouped_acc_type['counterpart']]
            return [
                '|',
                '&', ('company_id', '=', self.env.company.id), ('account_type', 'in', grouped_acc_type['types']),
                '&', ('company_id', '!=', self.env.company.id), ('account_type', 'in', counterpart_acc_type['types']),
            ]

        def interco_account_type_label_builder(grouping_keys):
            key_labels = {
                'receivable': self.env._("Receivable"),
                'payable': self.env._("Payable"),
                'current_assets': self.env._("Current Assets"),
                'current_liabilities': self.env._("Current Liabilities"),
                'income': self.env._("Income"),
                'expense': self.env._("Expense"),
                'non_current_assets': self.env._("Non-current Assets"),
                'equity_and_non_cur_liabilities': self.env._("Equity & Non-current Liabilities"),
                'liquidity': self.env._("Liquidity"),
                'off_balance': self.env._("Off-balance"),
                'unknown': self.env._("Unknown"),
            }
            keys_with_label = [(key, key_labels[key]) for key in grouping_keys]
            return dict(sorted(keys_with_label, key=lambda x: x[1]))

        def interco_account_label_builder(grouping_keys):
            company_names = {company.id: company.name for company in self.env.companies}
            keys_and_labels = []
            for key in grouping_keys:
                parsed_key = json.loads(key)
                label = f"{parsed_key['code'] or ''} {parsed_key['name']} ({company_names[parsed_key['company_id']]})".strip()
                keys_and_labels.append((key, label))

            return dict(sorted(keys_and_labels, key=lambda x: x[1]))

        def interco_account_domain_builder(grouping_key):
            parsed_key = json.loads(grouping_key)
            return [('company_id', '=', parsed_key['company_id']), ('account_id', '=', parsed_key['account_id'])]

        return {
            'interco_company': {
                'model': 'res.partner',
                'domain_builder': interco_company_domain_builder,
            },

            'interco_account_type': {
                'model': None,
                'domain_builder': interco_account_type_domain_builder,
                'label_builder': interco_account_type_label_builder,
            },

            'interco_account': {
                'model': None,
                'label_builder': interco_account_label_builder,
                'domain_builder': interco_account_domain_builder,
            },
        }

    def action_audit_cell(self, options, params):
        expression_label = params.get('expression_label')
        if expression_label == 'main_company':
            options.setdefault('forced_domain', []).append(('company_id', '=', self.env.company.id))
        elif expression_label == 'counterpart':
            options.setdefault('forced_domain', []).append(('company_id', '!=', self.env.company.id))

        report = self.env['account.report'].browse(options['report_id'])
        return report.action_audit_cell(options, params)

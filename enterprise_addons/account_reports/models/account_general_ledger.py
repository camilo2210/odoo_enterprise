import csv
import io
import json

from collections import defaultdict
from textwrap import shorten

from odoo import api, models, fields
from odoo.tools import float_repr, SQL
from odoo.exceptions import UserError

from odoo.addons.account_reports.utils.report_data_objects import AccountReportLineData, AccountReportLineChatterData
from odoo.addons.account_reports.models.account_report_snapshot import snapshotable_engine


def _keep_known_value(values):
    """ Aggregator for the descriptive keys of an engine result row (account code, currency, dates, names, ...).
        They describe the row's grouping key, so every partition containing that key reports the same value;
        the most recent one is kept, falling back on the previous one when the row carries no value for it.
    """
    return values[-1] if values[-1] is not None else values[0]


GL_RESULT_AGGREGATORS = {
    'init_debit': sum,
    'init_credit': sum,
    'init_balance': sum,
    'init_amount_currency': lambda v: sum(single_value for single_value in v if single_value is not None) if v is not None else 0.0,
    'has_sublines': max,
    # Descriptive keys added to the rows by _get_gl_engine_data, depending on the groupby
    **dict.fromkeys(
        (
            'account_id', 'account_code', 'account_name', 'currency_id',
            'date', 'invoice_date', 'line_name', 'move_name', 'partner_name',
        ),
        _keep_known_value,
    ),
}


class AccountGeneralLedgerReportHandler(models.AbstractModel):
    _name = 'account.general.ledger.report.handler'
    _inherit = ['account.report.custom.handler']
    _description = 'General Ledger Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        options['buttons'].append({
            'name': self.env._("CSV"),
            'sequence': 50,
            'action': 'export_file',
            'action_param': 'generate_csv_export',
            'file_export_type': self.env._('CSV'),
        })

        super()._custom_options_initializer(report, options, previous_options=previous_options)
        # Remove multi-currency columns if needed
        if self.env.user.has_group('base.group_multi_currency'):
            options['multi_currency'] = True
        else:
            options['columns'] = [
                column for column in options['columns']
                if column['expression_label'] != 'amount_currency'
            ]

        # Automatically unfold the report when printing it, unless some specific lines have been unfolded
        options['unfold_all'] = (options['export_mode'] == 'print' and not options.get('unfolded_lines')) or options['unfold_all']

        if options.get('force_not_unfold_all'):
            options['unfold_all'] = False

        options['custom_display_config'] = {
            'templates': {
                'AccountReportLineName': 'account_reports.GeneralLedgerLineName',
            },
        }

    def _caret_options_initializer(self):
        default_caret = self.env['account.report']._caret_options_initializer_default()

        return {
            **default_caret,
            'id_with_accumulated_balance_caret': [
                {'name': self.env._("View Journal Entry"), 'action': 'caret_option_open_record_form_custom_id_groupby', 'action_param': 'move_id'},
            ],
            'undistributed_profits_losses': [
                {'name': self.env._("Journal Items"), 'action': 'open_unallocated_items_journal_items'},
            ],
        }

    def open_unallocated_items_journal_items(self, options, params):
        report = self.env['account.report'].browse(options['report_id'])
        return report.open_unallocated_items_journal_items(options, params)

    @api.model
    def open_journal_items(self, options, params):
        params['view_ref'] = 'account_reports.view_move_line_account'
        params['group_by_account'] = False
        report = self.env['account.report'].browse(options['report_id'])
        action = report.open_journal_items(options=options, params=params)
        return action

    def caret_option_open_record_form_custom_id_groupby(self, options, params):
        report = self.env['account.report'].browse(options['report_id'])
        _model, aml_key = report._get_model_info_from_id(params['line_id'])
        record_id = json.loads(aml_key)[1]

        record = self.env['account.move.line'].browse(record_id)
        target_record = record[params['action_param']] if 'action_param' in params else record

        view_id = report._resolve_caret_option_view(target_record)

        action = {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'views': [(view_id, 'form')],  # view_id will be False in case the default view is needed
            'res_model': target_record._name,
            'res_id': target_record.id,
            'context': self.env.context,
        }

        if view_id is not None:
            action['view_id'] = view_id

        return action

    def _get_custom_groupby_map(self):
        def custom_label_builder(grouping_keys):
            """
            Batch label builder used to rename balance lines. The keys keep the order they are received in;
            the engine already returned them in the order the report must display them.
            """
            keys_names_in_sequence = {}
            aml_id_by_key = {}

            for key in grouping_keys:
                if isinstance(key, str) and 'balance_line' in key:
                    keys_names_in_sequence[key] = self.env._("Initial Balance")
                else:
                    keys_names_in_sequence[key] = key
                    aml_id_by_key[key] = json.loads(key)[1]

            if aml_id_by_key:
                display_name_by_aml_id = {
                    aml_vals['id']: aml_vals['display_name']
                    for aml_vals in self.env['account.move.line'].browse(aml_id_by_key.values()).read(['display_name'])
                }
                for key, aml_id in aml_id_by_key.items():
                    keys_names_in_sequence[key] = shorten(display_name_by_aml_id.get(aml_id) or '', width=200)

                self.env['account.move'].invalidate_model()

            return keys_names_in_sequence

        def domain_builder(grouping_key):
            if isinstance(grouping_key, str) and 'balance_line' in grouping_key:
                return []
            grouping_key_array = json.loads(grouping_key)
            return [('id', '=', grouping_key_array[1]), ('date', '=', grouping_key_array[0])]

        def pre_load_more_key_sort(x):
            key = x[0]
            return 0 if isinstance(key, str) and 'balance_line' in key else 1

        return {
            'id_with_accumulated_balance': {
                'model': None,
                'domain_builder': domain_builder,
                'caret_builder': lambda grouping_key: None if isinstance(grouping_key, str) and 'balance_line' in grouping_key else 'id_with_accumulated_balance_caret',
                'label_builder': custom_label_builder,
                'pre_load_more_key_sort': pre_load_more_key_sort,
            },
        }

    @snapshotable_engine(result_aggregators=GL_RESULT_AGGREGATORS, sub_engine_of='_report_engine_gl_initial_balance')
    def _report_engine_gl_init_bal_sub(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        domain = [('account_id.include_initial_balance', '=', True)]
        result = self._get_gl_engine_data(options, date_scope, formulas_dict, current_groupby, additional_domain=domain, warnings=warnings)
        return result

    def _report_engine_gl_initial_balance(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        init_balance = self._report_engine_gl_init_bal_sub(options, date_scope, formulas_dict, current_groupby, warnings=warnings)

        date_from = fields.Date.from_string(options['date']['date_from'])
        current_fiscalyear_date_from = self.env.company.compute_fiscalyear_dates(date_from)['date_from']

        if current_fiscalyear_date_from <= date_from:
            pl_domain = [
                ('account_id.include_initial_balance', '=', False),
                ('date', '>=', fields.Date.to_string(current_fiscalyear_date_from)),
            ]
            pl_init_balance = self._get_gl_engine_data(options, date_scope, formulas_dict, current_groupby, additional_domain=pl_domain, warnings=warnings)
        else:
            pl_init_balance = None

        if not pl_init_balance:
            return init_balance

        exprs = next(iter(formulas_dict.values()))
        if not current_groupby:
            res_dict = dict(init_balance[exprs])
            for k, v in pl_init_balance[exprs].items():
                res_dict[k] = GL_RESULT_AGGREGATORS.get(k, _keep_known_value)((res_dict.get(k), v))
            return {exprs: res_dict}

        merged_dict = {}
        for partition in [init_balance, pl_init_balance]:
            if not partition:
                continue
            for key, row_dict in partition[exprs]:
                if key not in merged_dict:
                    merged_dict[key] = dict(row_dict)
                else:
                    for k, v in row_dict.items():
                        merged_dict[key][k] = GL_RESULT_AGGREGATORS.get(k, _keep_known_value)((merged_dict[key].get(k), v))

        return {exprs: list(merged_dict.items())}

    def _report_engine_general_ledger(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        return self._get_gl_engine_data(options, date_scope, formulas_dict, current_groupby, warnings=warnings)

    def _get_gl_engine_data(self, options, date_scope, formulas_dict, current_groupby, additional_domain=None, warnings=None):
        def get_grouping_key(row, groupby):
            if groupby == 'id_with_accumulated_balance':
                if not row['id']:
                    return f"balance_line_{row['account_id']}"
                else:
                    return json.dumps([fields.Date.to_string(row['date']), row['id']])
            return row[groupby] if groupby else None

        query = self._get_query(options, date_scope, current_groupby, additional_domain=additional_domain)

        currency_id = self.env.company.currency_id.id

        subformulas = set()
        for exprs in formulas_dict.values():
            for expr in exprs:
                if expr.subformula:
                    subformulas.add(expr.subformula)

        line_dict_template = {
            'has_sublines': False,
        }

        for sub in subformulas:
            if sub.endswith(('debit', 'credit', 'balance')):
                line_dict_template[sub] = 0.0
            else:
                line_dict_template[sub] = None

        rows_by_key = {}

        for row in self.env.execute_query_dict(query):
            aml_key = get_grouping_key(row, current_groupby)
            is_balance_line = isinstance(aml_key, str) and 'balance_line' in aml_key

            if aml_key not in rows_by_key:
                line_dict = line_dict_template.copy()
                line_dict['has_sublines'] = True

                if current_groupby == 'id_with_accumulated_balance':
                    line_dict['account_id'] = row.get('account_id')  # Needed for batching

                    if not is_balance_line:
                        line_dict['date'] = row.get('date')
                        line_dict['partner_name'] = row.get('partner_name')
                        line_dict['line_name'] = row.get('line_name')
                        line_dict['account_code'] = row.get('account_code')
                        line_dict['account_name'] = row.get('account_name')
                        line_dict['move_name'] = row.get('move_name')
                        if any(column['expression_label'] == 'invoice_date' for column in options['columns']):
                            line_dict['invoice_date'] = row.get('invoice_date')

                    if row.get('currency_id') and row['currency_id'] != currency_id:
                        line_dict['currency_id'] = row['currency_id']

                elif current_groupby == 'account_id':
                    line_dict['account_code'] = row.get('account_code')
                    if row.get('currency_id'):
                        line_dict['currency_id'] = row['currency_id']

                rows_by_key[aml_key] = line_dict
            else:
                line_dict = rows_by_key[aml_key]

            for sub in subformulas:
                if is_balance_line and sub.startswith('period_'):
                    continue

                if sub.endswith('debit'):
                    line_dict[sub] = (line_dict.get(sub) or 0.0) + (row.get('debit', 0.0) or 0.0)
                elif sub.endswith('credit'):
                    line_dict[sub] = (line_dict.get(sub) or 0.0) + (row.get('credit', 0.0) or 0.0)
                elif sub.endswith('balance'):
                    line_dict[sub] = (line_dict.get(sub) or 0.0) + (row.get('balance', 0.0) or 0.0)
                elif sub.endswith('amount_currency'):
                    line_curr = row.get('currency_id')
                    if line_curr and line_curr != currency_id and row.get('amount_currency') is not None:
                        current_val = line_dict.get(sub)
                        if current_val is None:
                            current_val = 0.0
                        line_dict[sub] = current_val + row['amount_currency']
                else:
                    if sub not in line_dict or line_dict[sub] is None:
                        line_dict[sub] = row.get(sub)

        if not current_groupby:
            return {next(iter(formulas_dict.values())): rows_by_key.get(None, line_dict_template)}  # None is the key for total line as there is no groupby

        return {next(iter(formulas_dict.values())): list(rows_by_key.items())}

    def _get_query(self, options, date_scope, current_groupby, order_by_account=False, additional_domain=None):
        report = self.env['account.report'].browse(options['report_id'])
        options_date_from = fields.Date.from_string(options['date']['date_from'])
        current_fiscalyear_date_from = self.env.company.compute_fiscalyear_dates(options_date_from)['date_from']

        # We want to exclude move lines from expense and income accounts before the fiscal year for every groupby under account_id
        if additional_domain is None:
            additional_domain = [
                '|',
                ('account_id.include_initial_balance', '=', True),
                ('date', '>=', current_fiscalyear_date_from),
            ]

        report_query = report._get_report_query(options, date_scope, additional_domain)

        if options.get('export_mode') == 'print' and options.get('filter_search_bar') and current_groupby not in ('id_with_accumulated_balance', 'id'):
            search_bar_sql = SQL(
                """
                AND account_move_line.account_id = ANY(%(search_bar_account_query)s)
                """,
                search_bar_account_query=self.env['account.account']._search([
                    '|',
                    ('display_name', 'ilike', options.get('filter_search_bar')),
                    ('code', 'like', options.get('filter_search_bar')),
                    *self.env['account.account']._check_company_domain(self.env['account.report'].get_report_company_ids(options)),
                ]).subselect()
            )
        else:
            search_bar_sql = SQL()

        additional_select = SQL("")
        joins = SQL("")
        groupby = []
        if current_groupby == 'id_with_accumulated_balance':
            account_code_select = self.env['account.account']._field_to_sql('account_move_line__account_id', 'code', report_query)
            account_name_select = self.env['account.account']._field_to_sql('account_move_line__account_id', 'name')
            invoice_date_select = SQL(
                """
                    MIN(
                        CASE
                            WHEN account_move_line.date >= %(date)s THEN account_move_line.invoice_date
                            ELSE NULL
                        END
                    ) AS invoice_date,
                """,
                date=options_date_from,
            ) if any(column['expression_label'] == 'invoice_date' for column in options['columns']) else SQL("")
            additional_select = SQL("""
                CASE
                    WHEN account_move_line.date >= %(date)s THEN account_move_line.id
                    ELSE NULL
                END AS id,
                CASE
                    WHEN account_move_line.date >= %(date)s THEN account_move_line.date
                    ELSE NULL
                END AS date,
                %(invoice_date_select)s
                MIN(move.name) AS move_name,

                CASE
                    WHEN MIN(account_move_line.currency_id) = MAX(account_move_line.currency_id)
                    THEN SUM(account_move_line.amount_currency)
                    ELSE NULL
                END AS amount_currency,
                MIN(partner.name) AS partner_name,
                CASE
                    WHEN MIN(account_move_line.currency_id) = MAX(account_move_line.currency_id)
                    THEN MIN(account_move_line.currency_id)
                    ELSE NULL
                END AS currency_id,
                MIN(account_move_line__account_id.id) AS account_id,

                MIN(account_move_line.name) AS line_name,
                MIN(%(account_name_select)s) AS account_name,
                MIN(%(account_code_select)s) AS account_code,
                """,
                date=options_date_from,
                invoice_date_select=invoice_date_select,
                account_name_select=account_name_select,
                account_code_select=account_code_select,
            )
            joins = SQL("""
                LEFT JOIN res_partner partner ON partner.id = account_move_line.partner_id
                JOIN account_move move ON move.id = account_move_line.move_id
            """)
            groupby = [SQL("1"), SQL("2"), SQL("account_move_line.account_id")]
        elif current_groupby == 'account_id':
            additional_select = SQL("""
                account_move_line__account_id.id AS account_id,
                account_move_line__account_id.account_type AS account_type,
                SUM(account_move_line.amount_currency) AS amount_currency,
                account_move_line__account_id.currency_id AS currency_id,
            """)
            groupby = [SQL("account_move_line__account_id.id"), SQL("account_move_line__account_id.currency_id")]

        elif current_groupby:
            groupby_field_sql = self.env['account.move.line']._field_to_sql('account_move_line', current_groupby, report_query)
            additional_select = SQL("%s AS %s,", groupby_field_sql, SQL.identifier(current_groupby))
            groupby = [groupby_field_sql]

        account_table = report_query.table._join('account_id')
        if current_groupby == 'account_id' or order_by_account:
            order_clause = [self.env['account.account']._order_to_sql(account_table, False)]
            groupby = order_clause + groupby
        else:
            order_clause = []
        if current_groupby == 'id_with_accumulated_balance':
            order_clause.append(SQL("2 NULLS FIRST, move_name, 1 NULLS FIRST"))

        return SQL(
            """
            SELECT
                %(additional_select)s
                COALESCE(SUM(%(select_debit)s), 0.0) AS debit,
                COALESCE(SUM(%(select_credit)s), 0.0) AS credit,
                COALESCE(SUM(%(select_balance)s), 0.0) AS balance
            FROM %(from_clause)s

            %(joins)s

            WHERE %(where_clause)s
            %(search_bar_sql)s

            %(additional_groupby)s
            %(orderby_clause)s
            """,
            additional_select=additional_select,
            select_balance=report_query.table.consolidation_balance,
            select_debit=report_query.table.consolidation_debit,
            select_credit=report_query.table.consolidation_credit,
            from_clause=report_query.from_clause,
            joins=joins,
            where_clause=report_query.where_clause,
            search_bar_sql=search_bar_sql,
            additional_groupby=SQL("GROUP BY %s", SQL(",").join(groupby)) if groupby else SQL(),
            orderby_clause=SQL("ORDER BY %s", SQL(",").join(order_clause)) if order_clause else SQL(),
        )

    def _report_expand_unfoldable_line_with_groupby(self, line_dict_id, groupby, options, unfold_all_batch_data=None, limit_to_load=None):
        """
        Shadows the function from account_report, in order to compute accumulated balances.
        """
        if limit_to_load and groupby.replace(' ', '').split(',')[0] == 'account_id':
            # Done for usability. We don't apply any load more limit for that grouping, assuming the number of accounts will always be small enough
            limit_to_load = None

        report = self.env['account.report'].browse(options['report_id'])
        expansion_result_lines = report._report_expand_unfoldable_line_with_groupby(line_dict_id, groupby, options, unfold_all_batch_data=unfold_all_batch_data, limit_to_load=limit_to_load)
        if groupby != 'id_with_accumulated_balance':
            return expansion_result_lines

        colname_to_idx = defaultdict(dict)
        for idx, col in enumerate(options.get('columns', [])):
            colname_to_idx[col['column_group_index']][col['expression_label']] = idx

        initial_balance_line_ids = set()
        for line in expansion_result_lines:
            _markup, _model, grouping_key = report._parse_line_id(line.id)[-1]
            if isinstance(grouping_key, str) and grouping_key.startswith('balance_line_'):
                initial_balance_line_ids.add(line.id)

        col_group_indexes = range(len(options['column_groups']))
        accumulated_balance_by_colgroup = {
            col_group_index: 0.0
            for col_group_index in col_group_indexes
        }
        for col_group_index in col_group_indexes:
            if 'balance' not in colname_to_idx[col_group_index]:
                continue
            for line in expansion_result_lines:
                line_balance = line.columns[colname_to_idx[col_group_index]['balance']].no_format or 0
                accumulated_balance_by_colgroup[col_group_index] += line_balance
                if line.id not in initial_balance_line_ids:
                    new_col_data = report._build_column_data(accumulated_balance_by_colgroup[col_group_index], options['columns'][colname_to_idx[col_group_index]['balance']], options)
                    line.columns[colname_to_idx[col_group_index]['balance']] = new_col_data

        return expansion_result_lines

    def _get_fiscalyear_start_date(self, options):
        options_date_from = fields.Date.to_date(options['date']['date_from'])
        return self.env.company.compute_fiscalyear_dates(options_date_from)['date_from']

    def _adjust_total_with_additional_lines(self, total_line_columns, additional_lines_values):
        for line_values in additional_lines_values:
            for col in total_line_columns:
                if col and col.expression_label in line_values:
                    if col.no_format is not None:
                        col.no_format += line_values[col.expression_label]
                    else:
                        col.no_format = line_values[col.expression_label]
                    col.is_zero = not bool(col.no_format)
        return total_line_columns

    def _fix_init_balance_amount_currency_column(self, report, options, lines):
        """ Fix the currency on the amount_currency column to align with the account currency
        """
        amount_currency_indexes = [
            index for index, column in enumerate(options['columns'])
            if column['expression_label'] == 'amount_currency'
        ]

        if not amount_currency_indexes:
            return

        def parse_groupby_line(line):
            markup, model, value = report._parse_line_id(line.id)[-1]
            return (markup['groupby'] if isinstance(markup, dict) else None), model, value

        account_ids = {
            value
            for groupby, model, value in map(parse_groupby_line, lines)
            if groupby == 'account_id' and model == 'account.account'
        }
        currency_by_account_id = {
            account.id: account.currency_id
            for account in self.env['account.account'].browse(account_ids)
            if account.currency_id
        }

        for line in lines:
            current_account_id = report._get_res_id_from_line_id(line.id, 'account.account')
            current_currency = currency_by_account_id.get(current_account_id)
            if current_currency:
                for index in amount_currency_indexes:
                    column = line.columns[index]
                    line.columns[index] = report._build_column_data(
                        column.no_format,
                        options['columns'][index],
                        options,
                        currency=current_currency,
                    )

    def _custom_line_postprocessor(self, report, options, lines):
        general_ledger_custom_engine_line = self.env.ref('account_reports.general_ledger_custom_engine_line')
        processed_lines = []
        main_line_dict = None
        account_move_lines = []
        unaffected_earning_values = defaultdict(float)
        cta_values = defaultdict(float)

        if report._parse_line_id(lines[0].id)[-1] == ('', 'account.report.line', report.line_ids[0].id):
            unaffected_earning_lines = report._get_unallocated_earnings_lines(options, 'from_beginning')
        else:
            unaffected_earning_lines = []

        if report.currency_translation == 'cta' and report._parse_line_id(lines[0].id)[-1] == ('', 'account.report.line', report.line_ids[0].id):
            cta_line = report._compute_cumulative_translation_adjustment_lines(options, 'from_beginning')
            cumulative_translation_adjustment_lines = [cta_line] if cta_line else []
        else:
            cumulative_translation_adjustment_lines = []

        self._fix_init_balance_amount_currency_column(report, options, lines)

        for line in lines + unaffected_earning_lines + cumulative_translation_adjustment_lines:
            for column in line.columns:
                if column.expression_label == 'amount_currency' and column.is_zero:
                    column.no_format = None

            markup, model, res_id = report._parse_line_id(line.id)[-1]
            if model == 'account.report.line' and res_id == general_ledger_custom_engine_line.id:
                main_line_dict = line
            elif markup in ('undistributed_profits_losses', 'unallocated_earnings'):
                for column in line.columns:
                    if column.figure_type == 'monetary':
                        unaffected_earning_values[column.expression_label] += column.no_format or 0.0
            elif markup == 'cumulative_translation_adjustment':
                for column in line.columns:
                    if column.figure_type == 'monetary':
                        cta_values[column.expression_label] += column.no_format or 0.0
            else:
                processed_lines.append(line)

            if (
                model is None and markup == {'groupby': 'id_with_accumulated_balance'}
                and not (isinstance(res_id, str) and res_id.startswith('balance_line_')) and options.get('export_mode') != 'file'
            ):
                line.chatter = AccountReportLineChatterData(id=json.loads(res_id)[1])
                account_move_lines.append(line)

        if account_move_lines:
            line_ids = (l.chatter.id for l in account_move_lines)
            account_moves = {
                line['id']: line['move_id']
                for line in self.env['account.move.line'].browse(line_ids).read(['id', 'move_id'], load=False)
            }
            for line in account_move_lines:
                line.chatter.id = account_moves.get(line.chatter.id)
                line.chatter.model = 'account.move'

        if self.env.company.totals_below_sections and not options.get('ignore_totals_below_sections'):
            if unaffected_earning_lines:
                total_line = processed_lines.pop(-1)
                total_line.columns = self._adjust_total_with_additional_lines(total_line.columns, [unaffected_earning_values])
                processed_lines.extend(unaffected_earning_lines)
                processed_lines.append(total_line)
            if cumulative_translation_adjustment_lines and not all(col.is_zero for col in cumulative_translation_adjustment_lines[0].columns):
                total_line = processed_lines.pop(-1)
                total_line.columns = self._adjust_total_with_additional_lines(total_line.columns, [cta_values])
                processed_lines.extend(cumulative_translation_adjustment_lines)
                processed_lines.append(total_line)
        else:
            processed_lines.extend(unaffected_earning_lines)
            if cumulative_translation_adjustment_lines and not all(col.is_zero for col in cumulative_translation_adjustment_lines[0].columns):
                processed_lines.extend(cumulative_translation_adjustment_lines)
            if main_line_dict:
                processed_lines.append(
                    AccountReportLineData(
                        id=report._get_generic_line_id(None, None, 'total'),
                        name=self.env._("Total General Ledger"),
                        columns=self._adjust_total_with_additional_lines(main_line_dict.columns, [unaffected_earning_values, cta_values]),
                        level=1,
                    )
                )

        return processed_lines

    def _custom_unfold_all_batch_data_generator(self, report, options, lines_to_expand_by_function):
        """ Generate the custom engine's results for each full-sub-groupby-key that
            would be created when doing an unfold-all on the report.
        """
        def build_full_sub_groupby_key(report_line_id, full_sub_groupby_key_elements, current_groupby):
            return f"[{report_line_id}]{','.join(full_sub_groupby_key_elements)}=>{current_groupby}"

        results = {}
        column_groups_options = report._split_options_per_column_group(options)

        for line_to_expand in lines_to_expand_by_function.get('_report_expand_unfoldable_line_with_groupby', []):
            report_line_id = report._get_res_id_from_line_id(line_to_expand.id, 'account.report.line')
            report_line = self.env['account.report.line'].browse(report_line_id)
            groupby_list = [groupby.strip() for groupby in (report_line._get_groupby(options) or '').split(',')]
            if groupby_list != ['account_id', 'id_with_accumulated_balance']:
                continue

            grouped_formulas = report._group_expression_formulas(options, report_line.expression_ids)

            # The custom engines are computed first; the aggregations below are expressed in terms of their results.
            for engine_name in ('_report_engine_gl_initial_balance', '_report_engine_general_ledger'):
                for (date_scope, _formulas_groupby), formulas_dict in grouped_formulas.get(engine_name, {}).items():
                    for column_group_index, column_group_options in column_groups_options.items():
                        for current_groupby in groupby_list:
                            engine_res = report._get_custom_report_function(engine_name, 'engine')(column_group_options, date_scope, formulas_dict, current_groupby)

                            for expressions, formula_res in engine_res.items():
                                if current_groupby == 'account_id':
                                    rows_by_full_sub_groupby_key = {build_full_sub_groupby_key(report_line_id, [], current_groupby): formula_res}
                                else:  # id_with_accumulated_balance: the results are split per account, each account being expanded on its own
                                    rows_by_full_sub_groupby_key = defaultdict(list)
                                    for grouping_key, row_res in formula_res:
                                        full_sub_groupby_key = build_full_sub_groupby_key(report_line_id, [f"account_id:{row_res['account_id']}"], current_groupby)
                                        rows_by_full_sub_groupby_key[full_sub_groupby_key].append((grouping_key, row_res))

                                for full_sub_groupby_key, rows in rows_by_full_sub_groupby_key.items():
                                    groupby_expression_totals = results.setdefault(full_sub_groupby_key, {}).setdefault(column_group_index, {})
                                    for expression in expressions:
                                        groupby_expression_totals[expression] = {
                                            'value': [(grouping_key, row_res.get(expression.subformula)) for grouping_key, row_res in rows],
                                            'sublines_info': {grouping_key for grouping_key, row_res in rows if row_res.get('has_sublines')},
                                        }

            custom_expressions = report_line.expression_ids.filtered(lambda expr: expr.engine == 'custom')

            # Aggregations are computed last, once every expression they reference is available in results.
            for current_groupby in groupby_list:
                # The aggregations are evaluated for the groupby currently being expanded, not for the one grouped_formulas
                # was built with (it is always None here, since nothing is expanded yet when this generator runs).
                aggregations_with_date_scope = []
                for (date_scope, _formulas_groupby), formulas_dict in grouped_formulas.get('aggregation', {}).items():
                    for expressions in formulas_dict.values():
                        for expression in expressions:
                            aggregations_with_date_scope.append((date_scope, current_groupby, expression))

                if not aggregations_with_date_scope:
                    continue

                key_suffix = f'=>{current_groupby}'
                for full_sub_groupby_key, column_groups_results in results.items():
                    if not full_sub_groupby_key.startswith(f'[{report_line_id}]') or not full_sub_groupby_key.endswith(key_suffix):
                        continue

                    for column_group_index, column_group_options in column_groups_options.items():
                        groupby_expression_totals = column_groups_results.setdefault(column_group_index, {})

                        # Some groupby might not have results in both engines. So we manually have to provide default values to allow aggregations
                        for expression in custom_expressions:
                            groupby_expression_totals.setdefault(expression, {'value': [], 'sublines_info': set()})

                        aggregation_formula_result = report._compute_totals_no_batch_aggregation(column_group_options, aggregations_with_date_scope, groupby_expression_totals, {})

                        # Partially taken from inject_formula_results
                        for expressions, result in aggregation_formula_result.items():
                            expression_value = []
                            sublines_info = set()
                            for grouping_key, result_dict in result:
                                if result_dict['has_sublines']:
                                    sublines_info.add(grouping_key)
                                expression_value.append((grouping_key, result_dict['result']))

                            for expression in expressions:
                                groupby_expression_totals[expression] = {
                                    'value': expression_value,
                                    'sublines_info': sublines_info,
                                }

        return results

    def generate_csv_export(self, options):
        if len(options['column_groups']) > 1:
            raise UserError(self.env._("CSV export only works with one column group"))

        report = self.env['account.report'].browse(options['report_id'])
        return {
            'file_content': self._generate_csv_lazy_export(options),
            'file_type': 'csv',
            'file_name': report.get_default_report_filename(options, 'csv')
        }

    def _generate_csv_lazy_export(self, options):
        with self.pool.cursor() as new_cr:
            self.env.flush_all()
            handler = self.with_env(self.env(cr=new_cr))
            cur_data = {
                currency.id: {'name': currency.name, 'decimal_places': currency.decimal_places}
                for currency in handler.env['res.currency'].with_context(active_test=False).search([])
            }
            company_currency_id = handler.env.company.currency_id.id

            def csv_format_account_line(account_line, has_code=True):
                if has_code:
                    cells = list(handler.env['account.account']._split_code_name(account_line.name))
                else:
                    cells = ['/', account_line.name]

                for col in account_line.columns:
                    cell = col.name
                    currency_id = col.currency.id if col.currency else company_currency_id

                    # The aggregation engine may return an int (e.g. 0) for a monetary value, so bool aside, any number is formatted.
                    if col.figure_type == 'monetary' and isinstance(cell, (int, float)) and not isinstance(cell, bool):
                        cell = float_repr(float(cell), cur_data[currency_id]['decimal_places'])

                    if col.expression_label == 'amount_currency':
                        cells.append(cell)
                        cell = cur_data[currency_id]['name'] if currency_id != company_currency_id else ''
                    cells.append(cell)

                return csv_format(cells)

            def csv_format_aml_res(aml_res):
                cells = ['', aml_res.get('move_name', '')]
                for col in options['columns']:
                    cell = aml_res.get(col['expression_label'], '')
                    if col['figure_type'] == 'monetary':
                        if col['expression_label'] == 'amount_currency':
                            currency_id = aml_res['currency_id']
                            amount_cur_cell = float_repr(cell, cur_data[currency_id]['decimal_places']) if currency_id != company_currency_id else ''
                            cells.append(amount_cur_cell)
                            cell = cur_data[currency_id]['name'] if currency_id != company_currency_id else ''
                        else:
                            cell = float_repr(cell, cur_data[company_currency_id]['decimal_places'])
                    cells.append(cell)

                return csv_format(cells)

            def csv_format(cells):
                with io.StringIO() as buf:
                    writer = csv.writer(buf, delimiter=',', lineterminator='\n')
                    writer.writerow(cells)
                    return buf.getvalue().encode()

            col_names = [col['name'] for col in options['columns']]
            currency_idx = next((i for i, col in enumerate(options['columns']) if col.get('expression_label') == 'amount_currency'), None)
            header = [handler.env._("Code"), handler.env._("Name")]

            if currency_idx is not None:
                header += [
                    *col_names[:currency_idx],
                    handler.env._("Amount Currency"),
                    handler.env._("Currency"),
                    *col_names[currency_idx + 1:]
                ]
            else:
                header += col_names

            yield csv_format(header)

            report = handler.env['account.report'].browse(options['report_id'])
            agg_lines_options = report.get_options(previous_options={**options, 'unfolded_lines': [], 'force_not_unfold_all': True})
            agg_lines = report.with_context(no_format=True)._get_lines(agg_lines_options)

            # Exclude total lines
            account_lines = []
            accounts = []
            for agg_line in agg_lines:
                line_id = agg_line.id
                markup, model, res_id = report._parse_line_id(line_id)[-1]
                if markup != 'total':
                    if model == 'account.account':
                        accounts.append(res_id)
                    account_lines.append(agg_line)

            if not account_lines:
                return

            accounts_with_codes = {account.id for account in handler.env['account.account'].browse(accounts) if account.code}

            account_lines_iter = iter(account_lines)
            account_line = next(account_lines_iter)
            _model, account_id = report._get_model_info_from_id(account_line.id)
            yield csv_format_account_line(account_line, has_code=account_id in accounts_with_codes)

            aml_query = handler._get_query(options, 'from_beginning', 'id_with_accumulated_balance', order_by_account=True)
            handler.env.cr.execute(SQL("%s", aml_query))
            progress = 0
            while aml_line := handler.env.cr.dictfetchone():
                while account_id != aml_line['account_id']:
                    account_line = next(account_lines_iter)
                    _model, account_id = report._get_model_info_from_id(account_line.id)
                    yield csv_format_account_line(account_line, has_code=account_id in accounts_with_codes)
                    progress = 0

                if aml_line['id'] is None:
                    aml_line['move_name'] = handler.env._("Initial Balance")
                    aml_line['partner_name'] = ''

                progress = aml_line['balance'] = (progress + aml_line['balance'])
                yield csv_format_aml_res(aml_line)

            # These are the "Result Brought Forward" lines
            for account_line in account_lines_iter:
                yield csv_format_account_line(account_line, has_code=False)

            total_line = agg_lines[-1]
            yield csv_format_account_line(total_line)

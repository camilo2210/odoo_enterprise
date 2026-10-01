import re
from collections import defaultdict

from odoo import api, fields, models
from odoo.addons.account_reports.models.account_report_snapshot import snapshotable_engine
from odoo.tools import SQL

FIELDS_TAKEN_FROM_PARTIALS = ['id', 'partner_id', 'debit', 'credit', 'amount_currency', 'balance']
NAME_PATTERN = re.compile(r"^[^()]+\s*(?:\([^()]+\))?")


class AccountPartnerLedgerReportHandler(models.AbstractModel):
    _name = 'account.partner.ledger.report.handler'
    _inherit = ['account.report.custom.handler']
    _description = 'Partner Ledger Custom Handler'

    ####################################################
    # OVERRIDES
    ####################################################

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)

        domain = []

        company_ids = report.get_report_company_ids(options)
        exch_code = self.env['res.company'].browse(company_ids).mapped('currency_exchange_journal_id')
        if exch_code:
            domain += ['!', '&', '&', '&', ('credit', '=', 0.0), ('debit', '=', 0.0), ('amount_currency', '!=', 0.0), ('journal_id', 'in', exch_code.ids)]

        if options['export_mode'] == 'print' and options.get('filter_search_bar'):
            domain += [
                '|', ('matched_debit_ids.debit_move_id.partner_id.name', 'ilike', options['filter_search_bar']),
                '|', ('matched_credit_ids.credit_move_id.partner_id.name', 'ilike', options['filter_search_bar']),
                '|', ('partner_id.name', 'ilike', options['filter_search_bar']),
                ('partner_id', '=', False),
            ]

        options['forced_domain'] = options.get('forced_domain', []) + domain

        if self.env.user.has_group('base.group_multi_currency'):
            options['multi_currency'] = True
        else:
            options['columns'] = [col for col in options['columns'] if col['expression_label'] not in {'amount_currency'}]

        accounts = self.env['account.account']
        if not accounts.search_count([('code', '!=', False), *accounts._check_company_domain(self.env.company)], limit=1):
            options['columns'] = [col for col in options['columns'] if col['expression_label'] != 'account_code']

        options['custom_display_config'] = {
            'css_custom_class': 'partner_ledger',
            'templates': {
                'AccountReportLineName': 'account_reports.PartnerLedgerLineName',
            },
        }

    def _get_custom_groupby_map(self):
        def partner_line_label_builder(ids):
            valid_ids = [id for id in ids if id]
            partners = self.env['res.partner'].browse(valid_ids).sorted('name')
            partner_names = partners.mapped('name')
            res = dict(zip(partners.ids, partner_names))
            if None in ids:
                res[None] = self.env._("Unknown Partner")
            return res

        def move_line_label_builder(keys):
            if not keys:
                return {}
            # The fake lines have negative ids, that's why to take the absolute value
            lines = self.env['account.move.line'].browse(abs(key) for key in keys if key is not None)
            key_to_label_dict = dict(zip(
                [key for key in keys if key is not None],
                lines.mapped(lambda line: match.group(0).strip() if (match := NAME_PATTERN.match(line.display_name or '')) else line.display_name),
            ))
            if None in keys:
                # Initial balance always displayed first.
                return {
                    None: self.env._("Initial Balance"),
                    **key_to_label_dict,
                }
            return key_to_label_dict

        return {
            'partner_id': {
                'model': 'res.partner',
                'label_builder': partner_line_label_builder,
                'domain_builder': lambda grouping_key: []  # Handled in _report_expand_unfoldable_line_with_groupby
            },
            'id': {
                'model': None,
                'caret_builder': lambda grouping_key: bool(grouping_key) and 'id',
                'label_builder': move_line_label_builder,
                'is_column_cumulative': lambda expr_label: expr_label == 'balance',
                'pre_load_more_key_sort': lambda all_group_results: 1 if all_group_results[0] else -1,
            },
        }

    def _caret_options_initializer(self):
        default_caret = self.env['account.report']._caret_options_initializer_default()

        return {
            **default_caret,
            'id': [
                {'name': self.env._("View Journal Entry"), 'action': 'caret_option_open_record_form_custom_id_groupby', 'action_param': 'move_id'},
            ]
        }

    def _report_expand_unfoldable_line_with_groupby(self, line_dict_id, groupby, options, unfold_all_batch_data=None, limit_to_load=None):
        report = self.env['account.report'].browse(options['report_id'])
        res_ids_map = report._get_res_ids_from_line_id(line_dict_id, ['res.partner'])
        if 'res.partner' in res_ids_map:
            # Restrict the computation to the expanded partner group (model_id is None for 'Unknown Partner').
            options = options | {'partner_ledger_expand_partner': res_ids_map['res.partner']}

        return report._report_expand_unfoldable_line_with_groupby(
            line_dict_id,
            groupby,
            options,
            unfold_all_batch_data=unfold_all_batch_data,
            limit_to_load=limit_to_load,
        )

    def _custom_unfold_all_batch_data_generator(self, report, options, lines_to_expand_by_function):
        def build_full_sub_groupby_key(report_line_id, full_sub_groupby_key_elements, current_groupby):
            return f"[{report_line_id}]{','.join(full_sub_groupby_key_elements)}=>{current_groupby}"

        def add_line_dict_to_rslt_dict(rslt, line_dict, column_group_index, key, groupby, value_key_by_expression):
            for expression, value_key in value_key_by_expression.items():
                rslt[key][column_group_index][expression]['value'].append((line_dict[groupby], line_dict.get(value_key)))
                if groupby != 'id':
                    rslt[key][column_group_index][expression]['sublines_info'].add(line_dict[groupby])

        rslt = defaultdict(lambda: defaultdict(
            lambda: defaultdict(
                lambda: {
                    'value': [],
                    'sublines_info': set(),
                }
            )
        ))
        for expand_function_name, lines_to_expand in lines_to_expand_by_function.items():
            for line_to_expand in lines_to_expand:
                if expand_function_name == '_report_expand_unfoldable_line_with_groupby':
                    report_line_id = report._get_res_id_from_line_id(line_to_expand.id, 'account.report.line')
                    report_line = self.env['account.report.line'].browse(report_line_id)
                    # We need to get the expression to compute without the workaround for snapshot
                    # So the balance aggregation is computed directly without using the aggregation
                    # In that case, we need to remove from expressions the init_balance and period_balance expression
                    expressions = report_line.expression_ids.filtered(
                        lambda expr: expr.label not in ('period_balance', 'init_balance')
                    )
                    groupbys = report_line._get_groupby(options).split(',')

                    # Don't depend on aggregation for unfold_all but calculate the 'balance' directly with 'from_beginning'
                    subformulas_rules = self._get_subformulas_rules()
                    value_key_by_expression = {}
                    for expression in expressions:
                        if expression.engine == 'custom':
                            value_key_by_expression[expression] = expression.subformula
                        elif expression.engine == 'aggregation' and expression.label in subformulas_rules:
                            value_key_by_expression[expression] = expression.label

                    subformulas = list({value_key for value_key in value_key_by_expression.values() if value_key})
                    for column_group_index, column_group_options in report._split_options_per_column_group(options).items():
                        for i, groupby in enumerate(groupbys):
                            if groupby != 'id':
                                line_dicts = self._get_aggregated_lines(subformulas, column_group_options, groupbys[:i + 1], 'from_beginning')
                            else:
                                line_dicts = self._get_move_lines(subformulas, column_group_options, groupbys[:i + 1], 'from_beginning')
                            for line_dict in line_dicts:
                                key = build_full_sub_groupby_key(report_line_id, [f"{groupby_}:{line_dict[groupby_]}" for groupby_ in groupbys[:i]], groupby)
                                add_line_dict_to_rslt_dict(rslt, line_dict, column_group_index, key, groupby, value_key_by_expression)

        return rslt

    def _custom_line_postprocessor(self, report, options, lines):
        today = fields.Date.context_today(report)

        monetary_columns_indexes = [i for i, col in enumerate(options['columns']) if col.get('figure_type') == 'monetary']
        date_maturity_index_col = next((i for i, col in enumerate(options['columns']) if col.get('expression_label') == 'date_maturity'), None)
        colname_to_idx = {col['expression_label']: idx for idx, col in enumerate(options.get('columns', []))}
        init_balance = 0

        for line in lines:
            line_col = line.columns
            next_groupby = line.groupby.split(',')[0] if line.groupby else None
            markup = report._get_markup(line.id)
            grouping_key = report._get_model_info_from_id(line.id)[1]

            if next_groupby == 'id' and markup != 'load_more':
                init_balance = 0

            if isinstance(markup, dict) and markup.get('groupby', '') == 'id':
                if date_maturity_index_col:
                    date_maturity = line_col[date_maturity_index_col].no_format
                    if date_maturity and date_maturity < today:
                        line_col[date_maturity_index_col].css_class = 'text-danger'

                if not options.get('unfold_all') and 'balance' in colname_to_idx:
                    # The batch data generator use a different method by avoiding using the snapshots
                    # Instead of computing init_balance and period_balance separately, it does it together
                    # resulting with the correcty cumulative balance.
                    if grouping_key is None:
                        init_balance = line.columns[colname_to_idx['balance']].no_format
                    else:
                        current_balance_column = line.columns[colname_to_idx['balance']]
                        new_balance = init_balance + current_balance_column.no_format
                        line.columns[colname_to_idx['balance']] = report._build_column_data(
                            new_balance,
                            options['columns'][colname_to_idx['balance']],
                            options,
                        )

            elif markup == 'load_more' and 'balance' in colname_to_idx:
                current_balance_column = line.columns[colname_to_idx['balance']]
                new_balance = init_balance + current_balance_column.no_format
                line.columns[colname_to_idx['balance']] = report._build_column_data(
                    new_balance,
                    options['columns'][colname_to_idx['balance']],
                    options,
                )

            for col_index in monetary_columns_indexes:
                line_col_details = line_col[col_index]
                no_format_value = line_col_details.no_format
                if no_format_value and no_format_value < 0:
                    line_col_details.css_class = 'text-info'

        return lines

    ####################################################
    # CORE
    ####################################################
    @api.model
    def _get_subformulas_rules(self):
        return {
            'journal_code': {'to_sql': lambda query: query.table.journal_id.code},
            'invoice_date': {
                'to_sql': lambda _query: SQL('COALESCE(account_move_line.invoice_date, account_move_line.date)'),
            },
            '_currency_amount_currency': {'field': 'currency_id'},
            'init_balance': {
                'field': 'balance',
                'from_beginning': True,
            },
            'balance': {
                'from_beginning': True,
                'cumulative_sum': True,
            },
            'period_balance': {
                'field': 'balance',
                'cumulative_sum': True,
            },
        }

    @api.model
    def _report_engine_partner_ledger_report(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        expressions = self.env['account.report.expression']
        for formula_expressions in formulas_dict.values():
            expressions |= formula_expressions

        subformulas = expressions.mapped('subformula')

        if not current_groupby:
            totals = self._get_aggregated_lines(subformulas, options, [], date_scope=date_scope)
            engine_res = {**totals[0], 'has_sublines': True} if totals else {subformula: None for subformula in subformulas} | {'has_sublines': False}
            return {next(iter(formulas_dict.values())): engine_res}

        if current_groupby == 'id':
            groupbys = [groupby.strip() for groupby in expressions.report_line_id._get_groupby(options).split(',')]
            line_dicts = self._get_move_lines(subformulas, options, groupbys, date_scope)
        else:
            line_dicts = self._get_aggregated_lines(subformulas, options, [current_groupby], date_scope=date_scope)

        return {next(iter(formulas_dict.values())): [(line_dict[current_groupby], line_dict | {'has_sublines': current_groupby != 'id'}) for line_dict in line_dicts]}

    def _report_engine_partner_ledger_initial_balance(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        expressions_key = next(iter(formulas_dict.values()))
        subengine_result = self._report_engine_partner_ledger_initial_balance_subengine(options, date_scope, formulas_dict, current_groupby)

        currency = self.env.company.currency_id
        if not current_groupby:
            total_init_balance = subengine_result[expressions_key]['init_balance']
            return {expressions_key: {'init_balance': total_init_balance or 0.0, 'has_sublines': False}}

        merged_groups = dict(subengine_result[expressions_key])
        if current_groupby == 'partner_id' or 'partner_ledger_expand_partner' in options:
            for grouping_key, balance_delta in self._get_no_partner_reconciled_delta(options, date_scope, current_groupby).items():
                group_values = merged_groups.setdefault(grouping_key, {'init_balance': 0.0, 'has_sublines': True})
                group_values['init_balance'] += balance_delta

        return {
            expressions_key: [
                (grouping_key, group_values)
                for grouping_key, group_values in merged_groups.items()
                if not currency.is_zero(group_values['init_balance'])
            ],
        }

    @snapshotable_engine(result_aggregators={'init_balance': sum, 'has_sublines': max}, sub_engine_of='_report_engine_partner_ledger_initial_balance')
    def _report_engine_partner_ledger_initial_balance_subengine(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        """ Summable part of the partner ledger's initial balance: plain sums grouped on the move lines' own partner_id """
        report = self.env['account.report'].browse(options['report_id'])
        expressions_key = next(iter(formulas_dict.values()))
        query = report._get_report_query(options, date_scope)
        balance_expr = SQL('SUM(%s * %s)', query.table.balance, query.table.consolidation_rate)

        if not current_groupby:
            row = self.env.execute_query_dict(query.select(SQL('%s AS init_balance', balance_expr)))[0]
            return {expressions_key: {'init_balance': row['init_balance'] or 0.0, 'has_sublines': False}}

        if 'partner_ledger_expand_partner' in options:
            query.add_where(SQL('partner_id = %s', options['partner_ledger_expand_partner']))

        if current_groupby == 'id':
            groupby_expr = SQL('NULL')
        else:
            groupby_expr = query.table[current_groupby]
            query.groupby = groupby_expr

        rows = self.env.execute_query_dict(query.select(
            SQL('%s AS grouping_key', groupby_expr),
            SQL('%s AS init_balance', balance_expr),
        ))
        return {
            expressions_key: [
                (row['grouping_key'], {'init_balance': row['init_balance'] or 0.0, 'has_sublines': False})
                for row in rows
            ],
        }

    @api.model
    def _get_no_partner_reconciled_delta(self, options, date_scope, current_groupby):
        """
        Calculate the amounts to transfer from 'Unknown Partner' group to a partner for partner-less lines that have been reconciled.

        This correction is recalculated on the whole period at every call: it cannot
        be part of snapshots, since reconciling can alter it at any time, even for lines in locked periods.
        """
        report = self.env['account.report'].browse(options['report_id'])
        partner_ids = options.get('partner_ids')
        query = report._get_report_query({**options, 'partner_ids': []}, date_scope, domain=[('partner_id', '=', False)])
        self._add_partials_data_join(query)
        query.add_where(SQL('partials_data.id IS NOT NULL'))
        if current_groupby != 'id':
            groupby_expr = self._get_expr(current_groupby, query)
            query.groupby = groupby_expr
        else:
            groupby_expr = SQL('NULL')

        partner_expr = self._get_expr('partner_id', query)

        if partner_ids:
            query.add_where(SQL('%s IN %s', partner_expr, tuple(partner_ids)))

        if 'partner_ledger_expand_partner' in options:
            query.add_where(SQL('%s = %s', partner_expr, options['partner_ledger_expand_partner']))

        rows = self.env.execute_query_dict(query.select(
            SQL('%s AS grouping_key', groupby_expr),
            SQL('SUM(%s) AS balance_delta', self._get_expr('balance', query)),
        ))
        return {row['grouping_key']: row['balance_delta'] for row in rows if row['balance_delta']}

    @api.model
    def _get_expr(self, subformula, query):
        expr = SQL('NULL')

        rules = self._get_subformulas_rules().get(subformula, {})
        field_name = rules.get('field', subformula)
        field = self.env['account.move.line']._fields.get(field_name)
        if to_sql := rules.get('to_sql'):
            expr = to_sql(query)
        elif field:
            expr = query.table[field_name]
            if field_name in FIELDS_TAKEN_FROM_PARTIALS:
                expr = SQL('COALESCE(partials_data.%s, %s)', SQL.identifier(field_name), expr)
            if field.type == 'monetary' and field.get_currency_field(self.env['account.move.line']) == 'company_currency_id':
                expr = SQL("%s * %s", expr, query.table.consolidation_rate)

        return expr

    @api.model
    def _get_agg_expr(self, subformula, query, groupbys, date_from):
        if subformula.startswith('_currency_'):
            return SQL(
                "ARRAY_AGG(DISTINCT %s)",
                query.table.currency_id,
            )
        expr = self._get_expr(subformula, query)
        rules = self._get_subformulas_rules().get(subformula, {})
        field_name = rules.get('field', subformula)
        field = self.env['account.move.line']._fields.get(field_name)
        from_beginning = rules.get('from_beginning') or (rules.get('cumulative_sum') and groupbys and groupbys[-1] == 'id')
        if not from_beginning and date_from:
            expr = SQL("""
                    CASE
                        WHEN %(date_field)s >= %(date_from)s THEN %(expr)s
                        ELSE NULL
                    END
                """,
                date_field=self._get_expr('invoice_date', query),
                date_from=date_from,
                expr=expr,
            )
        if field and field.type in {'integer', 'float', 'monetary'}:
            if field.get_currency_field(self.env['account.move.line']) != 'company_currency_id':
                expr = SQL(
                    """
                        CASE
                            -- Small optimization to count distinct currencies on large datasets.
                            -- If both MIN() and MAX() are equal, it means there's only one 'currency_id'.
                            WHEN MIN(%(currency_expr)s) = MAX(%(currency_expr)s) AND MIN(%(currency_expr)s) != %(company_currency_id)s
                                 AND ABS(SUM(%(expr)s)) > 0.01
                            THEN SUM(%(expr)s)
                            ELSE NULL
                        END
                    """,
                    currency_expr=query.table.currency_id,
                    expr=expr,
                    company_currency_id=self.env.company.currency_id.id,
                )
            else:
                expr = SQL('SUM(%s)', expr)
            if from_beginning and date_from:
                query.having = SQL('%s OR %s', query.having, SQL('%s != 0', expr))
            if rules.get('cumulative_sum') and groupbys and groupbys[-1] == 'id':
                return SQL(
                    'SUM (%s) OVER (PARTITION BY %s ORDER BY %s)',
                    expr, SQL(', ').join(self._get_expr(groupby, query) for groupby in groupbys[:-1]), query.order,
                )
            return expr

        if not groupbys or groupbys[-1] != 'id':
            return SQL('NULL')
        if field and field.type == 'boolean':
            return SQL('BOOL_AND(%s)', expr)
        return SQL('MIN(%s)', expr)

    @api.model
    def _get_aggregated_lines(self, subformulas, options, groupbys, date_scope):
        report = self.env['account.report'].browse(options['report_id'])
        date_from, _date_to = report._get_date_bounds_info(options, None)
        if date_scope != 'from_beginning':
            # The query itself is bounded to the evaluated period; no need to emulate the period bounds in SQL.
            date_from = None

        query = self._get_partner_ledger_query(options, date_scope=date_scope)
        if date_from:
            query.having = SQL('MAX(account_move_line.date) >= %s', date_from)
        groupby_exprs = [self._get_expr(groupby, query) for groupby in groupbys]
        query.groupby = SQL(', ').join(groupby_exprs)

        return self.env.execute_query_dict(query.select(
            *[SQL('%s AS %s', groupby_expr, SQL.identifier(groupby)) for groupby_expr, groupby in zip(groupby_exprs, groupbys)],
            *[SQL('%s AS %s', self._get_agg_expr(subformula, query, groupbys, date_from), SQL.identifier(subformula)) for subformula in subformulas],
        ))

    @api.model
    def _get_move_lines(self, subformulas, options, groupbys, date_scope):
        report = self.env['account.report'].browse(options['report_id'])
        date_from, _date_to = report._get_date_bounds_info(options, None)

        query = self._get_partner_ledger_query(options, date_scope)
        if date_from:
            id_expr = SQL("""
                    CASE
                        WHEN %(date_field)s >= %(date_from)s THEN %(expr)s
                        ELSE NULL
                    END
                """,
                date_field=self._get_expr('invoice_date', query),
                date_from=date_from,
                expr=self._get_expr('id', query),
            )
        else:
            id_expr = self._get_expr('id', query)

        previous_groupbys_exprs = [self._get_expr(groupby, query) for groupby in groupbys[:-1]]
        query.groupby = SQL(', ').join([*previous_groupbys_exprs, id_expr])
        query.having = SQL('%s != 0', id_expr) if date_from else SQL()
        order_clause = [
            *previous_groupbys_exprs,
            *self._get_date_order_clause(query, groupbys, date_from),
            id_expr,
        ]
        query.order = SQL(', ').join(order_clause)

        return self.env.execute_query_dict(query.select(
            SQL('%s AS id', id_expr),
            *[SQL('%s AS %s', groupby_expr, SQL.identifier(groupby)) for groupby_expr, groupby in zip(previous_groupbys_exprs, groupbys[:-1])],
            *[SQL('%s AS %s', self._get_agg_expr(subformula, query, groupbys, date_from), SQL.identifier(subformula)) for subformula in subformulas],
        ))

    @api.model
    def _get_date_order_clause(self, query, groupbys, date_from):
        return [SQL('%s ASC NULLS FIRST', self._get_agg_expr('invoice_date', query, groupbys, date_from))]

    ####################################################
    # HELPERS
    ####################################################

    @api.model
    def _get_partner_ledger_query(self, options, date_scope, match_partner_on_partials=True):
        report = self.env['account.report'].browse(options['report_id'])

        if match_partner_on_partials and (partner_ids := options.get('partner_ids')):
            # This is necessary for the query to consider lines without partner that are reconciled with a line having a partner.
            # It is controlled through a parameter to give more control on this to variants not needing that behavior, since it's more
            # efficient index-wise to rely on the move lines' partner_id field directly, as _get_options_domain does by default.
            query = report._get_report_query({**options, 'partner_ids': []}, date_scope)
            if partner_ids:
                query.add_where(SQL('%s IN %s', self._get_expr('partner_id', query), tuple(partner_ids)))
        else:
            query = report._get_report_query(options, date_scope)

        if 'partner_ledger_expand_partner' in options:
            partner_expr = self._get_expr('partner_id', query)
            partner_id = options['partner_ledger_expand_partner']
            query.add_where(SQL('%s = %s', partner_expr, partner_id) if partner_id else SQL('%s IS NULL', partner_expr))

        self._add_partials_data_join(query)

        return query

    @api.model
    def _add_partials_data_join(self, query):
        """ Joins the partial reconciliations of the move lines without partner that are reconciled with a line having one"""
        query.add_join(
            kind='LEFT JOIN LATERAL',
            alias='partials_data',
            table=SQL("""(
                   SELECT NULL::INTEGER AS id,
                          NULL::INTEGER AS partner_id,
                          NULL::NUMERIC AS debit,
                          NULL::NUMERIC AS credit,
                          NULL::NUMERIC AS amount_currency,
                          NULL::NUMERIC AS balance
                UNION ALL
                   SELECT account_move_line.id AS id,
                          credit_line_with_partner.partner_id AS partner_id,
                          apr.amount AS debit,
                          0 AS credit,
                          apr.debit_amount_currency AS amount_currency,
                          apr.amount AS balance
                     FROM account_partial_reconcile apr
                     JOIN account_move_line credit_line_with_partner ON (apr.debit_move_id = account_move_line.id AND apr.credit_move_id = credit_line_with_partner.id)
                    WHERE account_move_line.partner_id IS NULL
                      AND credit_line_with_partner.partner_id IS NOT NULL
                UNION ALL
                   SELECT -account_move_line.id AS id,
                          NULL AS partner_id,
                          0 AS debit,
                          apr.amount AS credit,
                          -apr.debit_amount_currency AS amount_currency,
                          -apr.amount AS balance
                     FROM account_partial_reconcile apr
                     JOIN account_move_line credit_line_with_partner ON (apr.debit_move_id = account_move_line.id AND apr.credit_move_id = credit_line_with_partner.id)
                    WHERE account_move_line.partner_id IS NULL
                      AND credit_line_with_partner.partner_id IS NOT NULL
                UNION ALL
                   SELECT account_move_line.id AS id,
                          debit_line_with_partner.partner_id AS partner_id,
                          0 AS debit,
                          apr.amount AS credit,
                          -apr.credit_amount_currency AS amount_currency,
                          -apr.amount AS balance
                     FROM account_partial_reconcile apr
                     JOIN account_move_line debit_line_with_partner ON (apr.debit_move_id = debit_line_with_partner.id AND apr.credit_move_id = account_move_line.id)
                    WHERE account_move_line.partner_id IS NULL
                      AND debit_line_with_partner.partner_id IS NOT NULL
                UNION ALL
                   SELECT -account_move_line.id AS id,
                          NULL AS partner_id,
                          apr.amount AS debit,
                          0 AS credit,
                          apr.credit_amount_currency AS amount_currency,
                          apr.amount AS balance
                     FROM account_partial_reconcile apr
                     JOIN account_move_line debit_line_with_partner ON (apr.debit_move_id = debit_line_with_partner.id AND apr.credit_move_id = account_move_line.id)
                    WHERE account_move_line.partner_id IS NULL
                      AND debit_line_with_partner.partner_id IS NOT NULL
            )"""),
            condition=SQL('TRUE'),
        )

    ####################################################
    # MISC
    ####################################################

    @api.model
    def _get_report_send_recipients(self, options):
        partners = options.get('partner_ids', [])
        if not partners:
            rows = self._get_aggregated_lines([], options, ['partner_id'], 'from_beginning')
            partners = [row['partner_id'] for row in rows]
        return self.env['res.partner'].browse(partner for partner in partners if partner)

    ####################################################
    # ACTIONS
    ####################################################

    @api.model
    def action_open_partner(self, options, params):
        _model, record_id = self.env['account.report']._get_model_info_from_id(params['id'])
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'res_id': record_id,
            'views': [[False, 'form']],
            'view_mode': 'form',
            'target': 'current',
        }

    @api.model
    def open_journal_items(self, options, params):
        params['view_ref'] = 'account.view_move_line_tree_grouped_partner'
        report = self.env['account.report'].browse(options['report_id'])
        if report._get_option_recon_date(options):
            params['view_ref'] = 'account.view_move_line_tree_open_on'
        action = report.open_journal_items(options=options, params=params)
        action.get('context', {}).update({'search_default_group_by_account': 0})
        return action

    @api.model
    def caret_option_open_record_form_custom_id_groupby(self, options, params):
        """ Copy-pasted from general ledger
        """
        report = self.env['account.report'].browse(options['report_id'])
        _model, aml_key = report._get_model_info_from_id(params['line_id'])

        record = self.env['account.move.line'].browse(int(aml_key))
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

    @api.model
    def action_toggle_no_followup(self, line_id, all_line_ids):
        """Toggle the `no_followup` field on the journal item corresponding to the given `line_id`.

        Toggling this field may result in other journal items of the same report having their field toggled as well.
        This function will return all impacted lines, so the report can be updated dynamically.

        :param line_id: The report line ID.
        :param all_line_ids: A list containing all the report's line IDs.
        :return: A dict containing:
            - `updated_value`: the updated `no_followup` value (`True` or `False`)
            - `updated_line_ids`: a list of the impacted report lines
        """
        model, aml_id = self.env['account.report']._get_model_info_from_id(line_id)
        if model is not None or not aml_id:
            return None
        aml = self.env['account.move.line'].browse(int(aml_id))
        aml.no_followup = not aml.no_followup

        aml_id_to_line_id = {}
        for cur_line_id in all_line_ids:
            model, record_id = self.env['account.report']._get_model_info_from_id(cur_line_id)
            if model is None and record_id:
                aml_id_to_line_id[int(record_id)] = cur_line_id

        res = {'updated_value': aml.no_followup, 'updated_line_ids': [aml_id_to_line_id[aml.id]]}
        move = aml.move_id
        if move.is_invoice():
            # For invoices, the `no_followup` toggle will impact all its receivable/payable lines.
            res['updated_line_ids'] = move.line_ids.filtered(
                lambda line: line.account_type in ('asset_receivable', 'liability_payable') and line.id in aml_id_to_line_id,
            ).mapped(lambda line: aml_id_to_line_id[line.id])
        return res

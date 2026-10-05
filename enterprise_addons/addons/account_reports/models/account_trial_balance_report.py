# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json
import datetime
from collections import defaultdict

from odoo import api, models, _, fields
from odoo.tools import SQL, groupby, frozendict
from odoo.fields import Domain


class AccountTrialBalanceReportHandler(models.AbstractModel):
    _name = 'account.trial.balance.report.handler'
    _inherit = ['account.report.custom.handler']
    _description = 'Trial Balance Custom Handler'

    ############################
    #  OPTIONS INITIALIZATION  #
    ############################

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)

        if options.get('comparison'):
            options['comparison']['period_order'] = 'ascending'  # Make comparisons ascending (always)
            options['comparison']['hide_period_order_filter'] = True

        # Modify column headers and group structure
        column_headers, columns = self._get_column_values(report, options)

        options['column_headers'][0] = column_headers
        options['columns'] = columns

        # CTA
        for group_vals in options['column_groups']:
            if group_vals['forced_options']['trial_balance_column_type'] in ('initial_balance', 'end_balance'):
                group_vals['forced_options']['no_impact_on_currency_table'] = True

        options['custom_display_config'] = {
            'pdf_export': {
                'pdf_export_main': 'account_reports.audit_pdf_export_main',
                'pdf_export_main_table_header': 'account_reports.audit_pdf_export_main_table_header',
                'pdf_export_main_table_body': 'account_reports.audit_pdf_export_main_table_body',
            },
        }

    def _get_column_values(self, report, options):
        """
        Generate and process column values for the trial balance report.
        Returns modified column headers, column groups, and columns.
        """
        headers = []
        columns = []

        original_headers = options['column_headers'][0]
        original_columns = options['columns']

        initial_date_from = fields.Date.to_date(
            options['column_groups'][original_columns[0]['column_group_index']]['forced_options']['date']['date_from']
        )
        previous_fiscal_year = self.env.company.compute_fiscalyear_dates(initial_date_from)
        block_id = 0

        # Add initial balance column
        initial_date_to = initial_date_from - datetime.timedelta(days=1)
        block_end_date = fields.Date.to_date(options['column_groups'][0]['forced_options']['date']['date_to'])
        headers, columns = self._add_initial_column(
            report, options, headers, columns, initial_date_to, block_id, previous_fiscal_year['date_from'], block_end_date=block_end_date,
        )

        last_column = {}
        nb_columns_per_header = len(original_columns) / len(original_headers)
        col_number_in_block = 0
        fiscal_year = {}

        for column in original_columns:
            column_group_values = options['column_groups'][column['column_group_index']]
            fiscal_year = self.env.company.compute_fiscalyear_dates(
                fields.Date.to_date(column_group_values['forced_options']['date']['date_from'])
            )

            # Check for fiscal year change
            if fiscal_year != previous_fiscal_year:
                headers, columns = self._add_end_column(report, options, headers, columns, last_column, block_id, previous_fiscal_year)

                block_id += 1
                initial_date_to = fields.Date.to_date(column_group_values['forced_options']['date']['date_from']) - datetime.timedelta(days=1)
                block_end_date = fields.Date.to_date(column_group_values['forced_options']['date']['date_to'])
                headers, columns = self._add_initial_column(report, options, headers, columns, initial_date_to, block_id, fiscal_year['date_from'], block_end_date=block_end_date)
                previous_fiscal_year = fiscal_year

            # Update column group
            if column['column_group_index'] != last_column.get('column_group_index'):
                column_group_values['forced_options'].update({
                    'trial_balance_column_block_id': str(block_id),
                    'trial_balance_column_type': 'period',
                    'trial_balance_block_fiscalyear_start': fields.Date.to_string(fiscal_year['date_from']),
                    'trial_balance_block_end_date': fields.Date.to_string(block_end_date),
                })

            # Handle column headers
            col_number_in_block += 1
            if col_number_in_block % nb_columns_per_header == 0:
                headers.append(original_headers.pop(0))

            columns.append(column)
            last_column = column

        headers, columns = self._add_end_column(report, options, headers, columns, last_column, block_id, fiscal_year)

        return headers, columns

    def _add_initial_column(self, report, options, headers, columns, date_to, block_id, fiscal_year_start, block_end_date=None):
        initial_dates = report._build_date_dict(options, None, date_to, mode='single')
        header, col = self._create_column(report, options, _("Initial Balance"), initial_dates, block_id, fiscal_year_start, 'initial_balance', block_end_date)
        headers.append(header)
        columns.extend(col)
        return headers, columns

    def _add_end_column(self, report, options, headers, columns, last_column, block_id, fiscal_year):
        last_group = options['column_groups'][last_column['column_group_index']]
        end_date_from = fields.Date.to_date(last_group['forced_options']['date']['date_from'])
        end_date_to = fields.Date.to_date(last_group['forced_options']['date']['date_to'])
        end_dates = report._build_date_dict(options, end_date_from, end_date_to)
        header, col = self._create_column(report, options, _("End Balance"), end_dates, block_id, fiscal_year['date_from'], 'end_balance', block_end_date=end_date_to)
        headers.append(header)
        columns.extend(col)
        return headers, columns

    def _create_column(self, report, options, header_name, period_dates, block_id, fiscal_year_start, column_type, block_end_date=None):
        header, cols = self._generate_column_group(
            report, options,
            new_header_name=header_name,
            new_values={
                'forced_options': {
                    'date': period_dates,
                    'trial_balance_column_block_id': str(block_id),
                    'trial_balance_column_type': column_type,
                    'trial_balance_block_fiscalyear_start': fields.Date.to_string(fiscal_year_start),
                    'trial_balance_block_end_date': fields.Date.to_string(block_end_date) if block_end_date else options['date']['date_to'],
                },
            },
            create_single_column=self._display_single_column_for_initial_and_end_sections(options),
        )
        return header, cols

    @api.model
    def _display_single_column_for_initial_and_end_sections(self, options):
        # Decide whether we want our Initial Balance and End Balance column groups to have a single 'Balance' column.
        # If there is more than one header level, the front-end can't handle different number of columns depending
        # on the column header, so we need to use 'debit' and 'credit' columns rather than a 'balance' column.
        create_single_column = len(options['column_headers']) == 1
        return create_single_column

    def _generate_column_group(self, report, options, new_header_name, new_values, create_single_column=True):
        """ Generate column header, column group and columns values for a new column group.

            This is used to insert Initial Balance and End Balance columns before / after
            the period columns.

            If `create_single_column` is True, we will create a single 'Balance' column instead
            a column per report column.
        """
        default_group_vals = {'horizontal_groupby_element': {}, 'forced_options': {}, **new_values}

        new_column_header_element = {'name': new_header_name, 'forced_options': {}, **new_values}

        if create_single_column:
            new_column_header_element['colspan'] = 1

        column_headers = [
            [new_column_header_element],
            *options['column_headers'][1:],
        ]
        new_column_group_vals = report._generate_columns_group_vals_recursively(column_headers, default_group_vals)
        new_columns = report._build_columns_from_column_group_vals(options, new_column_group_vals)

        if create_single_column:
            # _build_columns_from_column_group_vals creates a column group with all the columns defined in the report.
            # But we'd like to have just one 'Balance' column, so we edit columns here.
            column_name = _("Balance")
            new_columns = [
                {
                    **new_column,
                    'name': column_name,
                    'expression_label': 'balance',
                }
                for new_column in new_columns
                if new_column['expression_label'] == 'debit'
            ]

        return new_column_header_element, new_columns

    def _caret_options_initializer(self):
        return {
            'account.account': [
                {'name': _("General Ledger"), 'action': 'caret_option_open_general_ledger'},
                {'name': _("Journal Items"), 'action': 'open_journal_items'},
            ],
            'undistributed_profits_losses': [
                {'name': _("General Ledger"), 'action': 'caret_option_open_general_ledger'},
                {'name': _("Journal Items"), 'action': 'open_unallocated_items_journal_items'},
            ],
        }

    def open_unallocated_items_journal_items(self, options, params):
        report = self.env['account.report'].browse(options['report_id'])
        return report.open_unallocated_items_journal_items(options, params)

    ###################
    #  REPORT ENGINE  #
    ###################

    def _report_engine_trial_balance(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        """ The custom engine for the Trial Balance.

            Return a list of lines with keys {'balance', 'debit', 'credit'} that are the aggregation
            of the journal items specified by the options' domain and dates.
        """
        report = self.env['account.report'].browse(options['report_id'])

        # This is because we want to pass a list of fields via the 'current_groupby' argument when calling this method
        # from the _custom_unfold_all_batch_data_generator.
        current_groupbys = [current_groupby] if current_groupby and not isinstance(current_groupby, list) else current_groupby or []
        report._check_groupby_fields(current_groupbys)

        # Never expand individual AMLs if we are in the Initial Balance.
        if 'id' in current_groupbys and options['trial_balance_column_type'] == 'initial_balance':
            return {next(iter(formulas_dict.values())): []}

        extra_domain = []
        # Don't consider income and expense AMLs from previous fiscal years.
        # (1) This is an optimization that speeds up the report but prevents expanding the Unaffected Earnings account.
        # (2) This also has the functional purpose of ensuring that income and expense accounts only take into account AMLs
        #     from the current fiscal year when coming from the `_expand_groupby`, because the `_expand_groupby` only adds
        #     a forced_domain on 'account_id' and doesn't do any restriction based on date.
        if fiscalyear_start := options.get('trial_balance_block_fiscalyear_start'):
            extra_domain = [
                '|',
                ('account_id.include_initial_balance', '=', True),
                ('date', '>=', fiscalyear_start),
            ]

        if options.get('export_mode') == 'print' and options.get('filter_search_bar'):
            extra_domain.append(('account_id', 'ilike', options['filter_search_bar']))

        block_end_date = None
        if options['trial_balance_column_type'] == 'initial_balance':
            date_scope = 'from_beginning'
            block_end_date = options.get('trial_balance_block_end_date')

        query = report._get_report_query(options, date_scope, domain=extra_domain, cta_date_to=block_end_date)

        if current_groupbys:
            select_groupby_key_components = SQL(',\n').join(
                SQL("%s AS %s", self.env['account.move.line']._field_to_sql("account_move_line", groupby_key, query), SQL.identifier(f'groupby_key_{groupby_key}'))
                for groupby_key in current_groupbys
            )
            query.groupby = SQL(',').join(SQL.identifier(f'groupby_key_{groupby_key}') for groupby_key in current_groupbys)

        query_results = self.env.execute_query_dict(query.select(SQL(', ').join(s for s in (
            SQL('%s', select_groupby_key_components) if current_groupbys else SQL(),
            SQL('COALESCE(SUM(%s), 0.0) AS balance', query.table.consolidation_balance),
            SQL('COALESCE(SUM(%s), 0.0) AS credit', query.table.consolidation_credit),
            SQL('COALESCE(SUM(%s), 0.0) AS debit', query.table.consolidation_debit),
        ) if s)))

        if not current_groupbys:
            if not query_results:
                return {next(iter(formulas_dict.values())): {
                    'balance': 0.0,
                    'debit': 0.0,
                    'credit': 0.0,
                    'has_sublines': False,
                }}

            query_result = query_results[0]
            query_result['has_sublines'] = True
            return {next(iter(formulas_dict.values())): query_result}

        return {next(iter(formulas_dict.values())): [
            (
                (
                    query_result[f'groupby_key_{current_groupbys[0]}']
                    if len(current_groupbys) == 1
                    else tuple(query_result[f'groupby_key_{groupby}'] for groupby in current_groupbys)
                ),
                {**query_result, 'has_sublines': True},
            )
            for query_result in query_results
        ]}

    def _custom_groupby_line_completer(self, report, options, line_dict, current_groupby):
        if line_dict.groupby != 'id':
            return

        # Don't expand individual AMLs in the Initial Balance
        unfoldable = False
        for column in line_dict.columns:
            column_options = options['column_groups'][column.column_group_index]['forced_options']
            if column_options['trial_balance_column_type'] == 'initial_balance':
                column.has_sublines = False
            unfoldable = unfoldable or column.has_sublines

        line_dict.unfoldable = unfoldable

    def _custom_line_postprocessor(self, report, options, lines):
        """ Compute the end balance for each column block and each horizontal group,
            based on the initial balance and the period debits and credits in the same
            column block and horizontal group.
            Any value that was already in the end_balance column is ignored.
        """
        def get_block_and_group_key(column):
            col_group_index = column.column_group_index
            if col_group_index is None:
                return None, frozendict(), ()

            column_group = options['column_groups'][col_group_index]
            block_id = column_group['forced_options'].get('trial_balance_column_block_id')
            horizontal_group = frozendict(column_group.get('horizontal_groupby_element', {}))
            analytic_group = tuple(column_group['forced_options'].get('analytic_accounts_list', []))

            return block_id, horizontal_group, analytic_group

        # Unaffected Earnings lines
        if report._parse_line_id(lines[0].id)[-1] == ('', 'account.report.line', report.line_ids[0].id):
            unaffected_earning_lines = report._get_unallocated_earnings_lines(options, 'strict_range', auditable=True)
        else:
            unaffected_earning_lines = []

        if report.currency_translation == 'cta':
            cta_line = report._compute_cumulative_translation_adjustment_lines(options, 'strict_range')
            cumulative_translation_adjustment_lines = [cta_line] if cta_line else []
        else:
            cumulative_translation_adjustment_lines = []

        if self.env.company.totals_below_sections:
            total_line_id = lines[-1].id
        else:
            total_line_id = lines[0].id

        unaffected_earning_values = defaultdict(
            lambda: {
                'initial_balance': {'debit': 0, 'credit': 0, 'balance': 0},
                'period': {'debit': 0, 'credit': 0, 'balance': 0},
            }
        )

        cumulative_translation_adjustment_values = defaultdict(
            lambda: {
                'initial_balance': {'debit': 0, 'credit': 0, 'balance': 0},
                'period': {'debit': 0, 'credit': 0, 'balance': 0},
            }
        )

        for line in unaffected_earning_lines + cumulative_translation_adjustment_lines + lines:
            unaffected_earning_line = report._get_markup(line.id) == 'undistributed_profits_losses'
            cumulative_translation_adjustment_line = report._get_markup(line.id) == 'cumulative_translation_adjustment'
            # Group by column block ID and horizontal groupby element to sum up end balance
            grouped_by_block = groupby(line.columns, key=get_block_and_group_key)

            for _grouping_key, columns_in_block in grouped_by_block:
                columns_grouped_by_type = dict(groupby(
                    columns_in_block,
                    lambda column: (
                        options['column_groups'][column.column_group_index]['forced_options'].get('trial_balance_column_type')
                        if column.column_group_index is not None else None
                    )
                ))

                # We do a separate sum for debits and credits since we need to handle both the case where
                # there is a single Balance column (if there is no horizontal groupby) or separate Debit and
                # Credit columns in the initial balance and end balance (if there is a horizontal groupby)
                sum_debit = sum_credit = 0.0
                for col_type, cols in columns_grouped_by_type.items():
                    if col_type in ('initial_balance', 'period'):
                        for col in cols:
                            if line.id == total_line_id:
                                col.no_format += unaffected_earning_values[_grouping_key][col_type][col.expression_label]
                                col.no_format += cumulative_translation_adjustment_values[_grouping_key][col_type][col.expression_label]
                                col.is_zero = not bool(col.no_format)
                            if not col.is_zero:
                                if col.expression_label == 'debit' or (col.expression_label == 'balance' and col in columns_grouped_by_type['initial_balance']):
                                    sum_debit += col.no_format
                                elif col.expression_label == 'credit':
                                    sum_credit += col.no_format
                                if unaffected_earning_line:
                                    unaffected_earning_values[_grouping_key][col_type][col.expression_label] += col.no_format
                                if cumulative_translation_adjustment_line:
                                    cumulative_translation_adjustment_values[_grouping_key][col_type][col.expression_label] += col.no_format

                for end_balance_col in columns_grouped_by_type.get('end_balance', []):
                    match end_balance_col.expression_label:
                        case 'debit':
                            end_balance_col.no_format = sum_debit
                            end_balance_col.is_zero = not bool(sum_debit)
                        case 'credit':
                            end_balance_col.no_format = sum_credit
                            end_balance_col.is_zero = not bool(sum_credit)
                        case 'balance':
                            balance = sum_debit - sum_credit
                            end_balance_col.no_format = balance
                            end_balance_col.is_zero = not bool(balance)

        # Total line
        if lines and not lines[0].parent_id:  # should not affect when unfolding lines
            # The same behavior is expected with or without totals_below_sections activated
            # Only the total line should be displayed at the bottom, in bold
            if self.env.company.totals_below_sections:  # total line already exists
                lines.pop(0)
                if unaffected_earning_lines:
                    total_line = lines.pop(-1)
                    lines.extend(unaffected_earning_lines)
                    lines.append(total_line)
                if cumulative_translation_adjustment_lines and not all(col.is_zero for col in cumulative_translation_adjustment_lines[0].columns):
                    total_line = lines.pop(-1)
                    lines.extend(cumulative_translation_adjustment_lines)
                    lines.append(total_line)
            else:
                lines.extend(unaffected_earning_lines)
                if cumulative_translation_adjustment_lines and not all(col.is_zero for col in cumulative_translation_adjustment_lines[0].columns):
                    lines.extend(cumulative_translation_adjustment_lines)
                lines.append(lines.pop(0))
                # To make the style as if totals_below_sections was activated
                lines[-1].id = report._build_subline_id(lines[-1].id, report._build_line_id([('total', None, None)]))
            # To make totals line not blank
            for col in lines[-1].columns:
                col.blank_if_zero = False
            lines[-1].name = self.env._("Total")

        return lines

    def _report_expand_unfoldable_line_with_groupby(self, line_dict_id, groupby, options, unfold_all_batch_data=None, limit_to_load=None):
        """ Shallow the 'account.report' function to prevent displaying move lines that do not belong to the period that is selected """
        if limit_to_load and groupby.replace(' ', '').split(',')[0] == 'account_id':
            # Done for usability. We don't apply any load more limit for that grouping, assuming the number of accounts will always be small enough
            limit_to_load = None

        report = self.env['account.report'].browse(options['report_id'])
        if groupby != 'id':
            return report._report_expand_unfoldable_line_with_groupby(line_dict_id, groupby, options, unfold_all_batch_data=unfold_all_batch_data, limit_to_load=limit_to_load)

        for _col_group_index, col_group_vals in enumerate(options['column_groups']):
            if col_group_vals['forced_options']['trial_balance_column_type'] == 'initial_balance':
                col_group_vals['forced_domain'].append(('id', '=', False))

        return report._report_expand_unfoldable_line_with_groupby(line_dict_id, groupby, options, unfold_all_batch_data=unfold_all_batch_data, limit_to_load=limit_to_load)

    def _get_account_ids_type_map(self, report, options):
        company_ids = report.get_report_company_ids(options)
        accounts = self.env['account.account'].search_fetch([('company_ids', 'in', company_ids)], ['account_type'])
        account_dict = {account.id: account.account_type for account in accounts}
        return account_dict

    def _get_fiscalyear_start_date(self, options):
        return options.get('trial_balance_block_fiscalyear_start')

    def _custom_unfold_all_batch_data_generator(self, report, options, lines_to_expand_by_function):
        """ Generate the custom engine's results for each full-sub-groupby-key that
            would be created when doing an unfold-all on the report.
        """
        def get_sub_groupby_key(report_line_id, groupbys, grouping_key):
            previous_groupbys, current_groupby = groupbys[:-1], groupbys[-1]

            sub_groupby_key = f'[{report_line_id}]'
            sub_groupby_key += ','.join(
                f'{field_name}:{value or None}'
                for (field_name, value) in zip(previous_groupbys, grouping_key)
            )
            sub_groupby_key += f'=>{current_groupby}'
            return sub_groupby_key

        results = {}  # In the form {full_sub_groupby_key: all_column_group_expression_totals for this groupby computation}

        for line_to_expand in lines_to_expand_by_function.get('_report_expand_unfoldable_line_with_groupby', []):
            report_line_id = report._get_res_id_from_line_id(line_to_expand.id, 'account.report.line')
            report_line = self.env['account.report.line'].browse(report_line_id)

            expressions = report_line.expression_ids.filtered(
                lambda x: x.engine == 'custom' and x.formula == '_report_engine_trial_balance'
            )
            if len(expressions) != len(report_line.expression_ids):
                continue

            formulas_dict = {expressions[0].formula: expressions}

            groupby_str = report_line._get_groupby(options)
            groupbys = groupby_str.replace(' ', '').split(',')

            # Execute the query once for each groupby level. While we could optimize this further
            # (execute the query once at the deepest groupby level, and then aggregate the results in Python),
            # this ensures that the results match exactly what we would get by expanding each line.
            # But we could change that if there is a performance need.
            while groupbys:
                for column_group_index, column_group_options in report._split_options_per_column_group(options).items():
                    for date_scope, expressions_by_date_scope in groupby(expressions, lambda e: e.date_scope):
                        # Get the custom engine results for the given groupby level.
                        engine_res = self._report_engine_trial_balance(column_group_options, date_scope, formulas_dict, current_groupby=groupbys)

                        # Transform the groupby key of each line into a list
                        engine_lines = [
                            (grouping_key if isinstance(grouping_key, tuple) else (grouping_key,), line_values)
                            for formula_res in engine_res.values()
                            for grouping_key, line_values in formula_res
                        ]
                        for parent_line_grouping_key, engine_lines_grouped_by_parent_line in groupby(
                            engine_lines,
                            lambda l: tuple(l[0][:-1])
                        ):
                            full_sub_groupby_key = get_sub_groupby_key(report_line_id, groupbys, parent_line_grouping_key)
                            results.setdefault(full_sub_groupby_key, {})
                            results[full_sub_groupby_key][column_group_index] = {
                                expression: {
                                    'value': [
                                        (grouping_key[-1], line_values[expression.subformula])
                                        for grouping_key, line_values in engine_lines_grouped_by_parent_line
                                    ],
                                    'sublines_info': {
                                        grouping_key[-1]
                                        for grouping_key, line_values in engine_lines_grouped_by_parent_line
                                        if line_values['has_sublines']
                                    },
                                }
                                for expression in expressions_by_date_scope
                            }
                groupbys.pop()
        return results

    def action_audit_cell(self, options, params):
        report = self.env['account.report'].browse(options['report_id'])
        column_group_forced_options = options['column_groups'][params['column_group_index']]['forced_options']

        # When generating the end balance column, we didn't specify a date in the forced_options,
        # to avoid a separate call to the custom engine (instead, the end balance is computed in
        # the custom lines postprocessor.)
        # But when auditing an end balance line, we need to retrieve moves from the beginning of time,
        # so we modify the options here just for the call to report.action_audit_cell.
        if column_group_forced_options['trial_balance_column_type'] == 'end_balance':
            column_group_forced_options['date'].update({
                'mode': 'single',
                'date_from': None,
            })

        action = report.action_audit_cell(options, params)

        account_id = report._get_res_id_from_line_id(params['calling_line_dict_id'], 'account.account')
        account = self.env['account.account'].browse(account_id)

        modified_domain = []
        if not account:
            action['domain'] += report._get_unallocated_earnings_lines_domain(
                column_group_forced_options['trial_balance_block_fiscalyear_start'],
                report._get_res_id_from_line_id(params['calling_line_dict_id'], 'res.company')
            )

        elif (
                column_group_forced_options['trial_balance_column_type'] in ('initial_balance', 'end_balance')
                and (account.internal_group in ('income', 'expense') or account.account_type == 'equity_unaffected')
        ):
            for condition in action['domain']:
                match condition:
                    case ['account_id', '=', account_id]:
                        modified_domain.extend([
                            ('account_id', '=', account_id),
                            ('date', '>=', column_group_forced_options['trial_balance_block_fiscalyear_start']),
                        ])
                    case _:
                        modified_domain.append(condition)

            action['domain'] = modified_domain

        date_from, date_to = report._get_date_bounds_info(options, 'strict_range')
        if report._get_markup(params['calling_line_dict_id']) == 'undistributed_profits_losses':
            date_from = column_group_forced_options['date']['date_from']
            date_to = column_group_forced_options['date']['date_to']

        action['context'].update({
            'currency_translation': report.currency_translation,
            'date_from': date_from,
            'date_to': date_to,
        })

        if options.get('multi_currency'):
            action['views'] = [(self.env.ref('account_reports.view_multi_currency_report_audit').id, 'list')]

        if report._get_markup(params['calling_line_dict_id']) == 'cumulative_translation_adjustment':
            column_group_options = report._get_column_group_options(options, params.get('column_group_index'))
            action['views'] = [(self.env.ref('account_reports.view_cumulative_translation_adjustment_audit_tree').id, 'list')]
            action['domain'] = Domain.AND([
                report._get_options_domain(column_group_options, 'strict_range'),
                Domain('account_type', 'in', ['equity', 'equity_unaffected', 'income', 'income_other', 'expense_direct_cost', 'expense', 'expense_depreciation', 'expense_other'])])

        return action

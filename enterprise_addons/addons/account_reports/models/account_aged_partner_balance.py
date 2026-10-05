# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime

from dateutil.relativedelta import relativedelta
from odoo import _, fields, models
from odoo.tools import SQL


class AccountAgedPartnerBalanceReportHandler(models.AbstractModel):
    _name = 'account.aged.partner.balance.report.handler'
    _inherit = ['account.report.custom.handler']
    _description = 'Aged Partner Balance Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        hidden_columns = set()

        options['multi_currency'] = report.env.user.has_group('base.group_multi_currency')
        options['show_currency'] = options['multi_currency'] and (previous_options or {}).get('show_currency', False)
        options['no_xlsx_currency_code_columns'] = True
        if not options['show_currency']:
            hidden_columns.update(['amount_currency', 'currency'])

        options['show_account'] = (previous_options or {}).get('show_account', False)
        if not options['show_account']:
            hidden_columns.add('account_name')

        options['columns'] = [
            column for column in options['columns']
            if column['expression_label'] not in hidden_columns
        ]

        default_order_column = {
            'expression_label': 'invoice_date',
            'direction': 'ASC',
        }

        options['order_column'] = previous_options.get('order_column') or default_order_column
        options['aging_based_on'] = previous_options.get('aging_based_on') or 'base_on_maturity_date'
        options['aging_interval'] = previous_options.get('aging_interval') or 30

        # Set aging column names
        interval = options['aging_interval']
        for column in options['columns']:
            if column['expression_label'].startswith('period'):
                period_number = int(column['expression_label'].replace('period', '')) - 1
                if 0 <= period_number < 4:
                    column['name'] = f'{interval * period_number + 1}-{interval * (period_number + 1)}'

        options['custom_display_config'] = {
            'css_custom_class': 'aged_partner_balance',
            'templates': {
                'AccountReportLineName': 'account_reports.AgedPartnerBalanceLineName',
            },
            'components': {
                'AccountReportFilters': 'AgedPartnerBalanceFilters',
            },
        }

    def _custom_line_postprocessor(self, report, options, lines):
        partner_lines_map = {}

        # Sort line dicts by partner
        for line in lines:
            model, model_id = report._get_model_info_from_id(line.id)
            if model == 'res.partner' and model_id:
                partner_lines_map[model_id] = line

        if partner_lines_map:
            for partner, line_data in zip(
                    self.env['res.partner'].browse(partner_lines_map),
                    partner_lines_map.values()
            ):
                line_data.get_custom()['trust'] = partner.with_company(partner.company_id or self.env.company).trust

        return lines

    def _report_engine_aged_receivable(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        return self._aged_partner_report_custom_engine_common(options, 'asset_receivable', current_groupby, formulas_dict)

    def _report_engine_aged_payable(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        return self._aged_partner_report_custom_engine_common(options, 'liability_payable', current_groupby, formulas_dict)

    def _aged_partner_report_custom_engine_common(self, options, internal_type, current_groupby, formulas_dict):
        report = self.env['account.report'].browse(options['report_id'])
        if current_groupby:
            report._check_groupby_fields([current_groupby])

        def minus_days(date_obj, days):
            return fields.Date.to_string(date_obj - relativedelta(days=days))

        aging_date_field = SQL.identifier('invoice_date') if options['aging_based_on'] == 'base_on_invoice_date' else SQL.identifier('date_maturity')
        date_to = fields.Date.from_string(options['date']['date_to'])
        interval = options['aging_interval']
        periods = [(False, fields.Date.to_string(date_to))]
        # Since we added the first period in the list we have to do one less iteration
        nb_column_groups = len(options['column_groups'])
        nb_periods = len([column for column in options['columns'] if column['expression_label'].startswith('period')]) // nb_column_groups - 1
        for i in range(nb_periods):
            start_date = minus_days(date_to, (interval * i) + 1)
            # The last element of the list will have False for the end date
            end_date = minus_days(date_to, interval * (i + 1)) if i < nb_periods - 1 else False
            periods.append((start_date, end_date))

        def build_result_dict(report, query_res_lines):
            rslt = {f'period{i}': 0 for i in range(len(periods))}

            for query_res in query_res_lines:
                for i in range(len(periods)):
                    period_key = f'period{i}'
                    rslt[period_key] += query_res[period_key]

            if current_groupby == 'id':
                query_res = query_res_lines[0] # We're grouping by id, so there is only 1 element in query_res_lines anyway
                currency = self.env['res.currency'].browse(query_res['currency_id'][0]) if len(query_res['currency_id']) == 1 else None
                rslt.update({
                    'invoice_date': query_res['invoice_date'][0] if len(query_res['invoice_date']) == 1 else None,
                    'due_date': query_res['due_date'][0] if len(query_res['due_date']) == 1 else None,
                    'amount_currency': query_res['amount_currency'],
                    'currency_id': query_res['currency_id'][0] if len(query_res['currency_id']) == 1 else None,
                    'currency': currency.display_name if currency else None,
                    'account_name': query_res['account_name'][0] if len(query_res['account_name']) == 1 else None,
                    'total': None,
                    'has_sublines': True,

                    # Needed by the custom_unfold_all_batch_data_generator, to speed-up unfold_all
                    'partner_id': query_res['partner_id'][0] if query_res['partner_id'] else None,
                })
            else:
                rslt.update({
                    'invoice_date': None,
                    'due_date': None,
                    'amount_currency': None,
                    'currency_id': None,
                    'currency': None,
                    'account_name': None,
                    'total': sum(rslt[f'period{i}'] for i in range(len(periods))),
                    'has_sublines': True,
                })

            return rslt

        # Build period table
        period_table = SQL('(VALUES %s)', SQL(',').join(
            SQL("(%s, %s, %s)", from_ or None, to or None, i)
            for i, (from_, to) in enumerate(periods))
        )

        # Build query
        if not report._get_option_recon_date(options):
            # Ensure the residual is computed at the report date_to
            options['recon_date'] = {
                'date_to': options['date']['date_to'],
            }
        query = report._get_report_query(options, 'strict_range', domain=[('account_id.account_type', '=', internal_type)])
        account_code = query.table._sudo().account_id.code

        always_present_groupby = SQL("period_table.period_index")
        if current_groupby:
            groupby_field_sql = query.table[current_groupby]
            select_from_groupby = SQL("%s AS grouping_key,", groupby_field_sql)
            groupby_clause = SQL("%s, %s", groupby_field_sql, always_present_groupby)
        else:
            select_from_groupby = SQL()
            groupby_clause = always_present_groupby
        multiplicator = -1 if internal_type == 'liability_payable' else 1
        select_period_query = SQL(',').join(
            SQL("""
                CASE WHEN period_table.period_index = %(period_index)s
                THEN %(multiplicator)s * SUM(%(balance_select)s)
                ELSE 0 END AS %(column_name)s
                """,
                period_index=i,
                multiplicator=multiplicator,
                column_name=SQL.identifier(f"period{i}"),
                balance_select=SQL("%s * %s", query.table.residual_at_date, query.table.consolidation_rate),
            )
            for i in range(len(periods))
        )

        query = SQL(
            """
            WITH period_table(date_start, date_stop, period_index) AS (%(period_table)s)

            SELECT
                %(select_from_groupby)s
                %(multiplicator)s * SUM(%(residual_currency_at_date)s) AS amount_currency,
                ARRAY_AGG(DISTINCT account_move_line.partner_id) AS partner_id,
                ARRAY_AGG(account_move_line.payment_id) AS payment_id,
                ARRAY_AGG(DISTINCT COALESCE(account_move_line.invoice_date, account_move_line.date)) AS invoice_date,
                ARRAY_AGG(DISTINCT COALESCE(account_move_line.%(aging_date_field)s, account_move_line.date)) AS report_date,
                ARRAY_AGG(DISTINCT %(account_code)s) AS account_name,
                ARRAY_AGG(DISTINCT COALESCE(account_move_line.%(aging_date_field)s, account_move_line.date)) AS due_date,
                ARRAY_AGG(DISTINCT account_move_line.currency_id) AS currency_id,
                COUNT(account_move_line.id) AS aml_count,
                ARRAY_AGG(%(account_code)s) AS account_code,
                %(select_period_query)s

            FROM %(table_references)s

            JOIN account_journal journal ON journal.id = account_move_line.journal_id
            JOIN period_table ON
                (
                    period_table.date_start IS NULL
                    OR COALESCE(account_move_line.%(aging_date_field)s, account_move_line.date) <= DATE(period_table.date_start)
                )
                AND
                (
                    period_table.date_stop IS NULL
                    OR COALESCE(account_move_line.%(aging_date_field)s, account_move_line.date) >= DATE(period_table.date_stop)
                )

            WHERE %(search_condition)s

            GROUP BY %(groupby_clause)s

            HAVING
                ROUND(SUM(%(residual_at_date)s), %(currency_precision)s) != 0

            ORDER BY %(groupby_clause)s
            """,
            account_code=account_code,
            period_table=period_table,
            select_from_groupby=select_from_groupby,
            residual_at_date=query.table.residual_at_date,
            residual_currency_at_date=query.table.residual_currency_at_date,
            select_period_query=select_period_query,
            multiplicator=multiplicator,
            aging_date_field=aging_date_field,
            table_references=query.from_clause,
            search_condition=query.where_clause,
            groupby_clause=groupby_clause,
            currency_precision=self.env.company.currency_id.decimal_places,
        )

        query_res_lines = self.env.execute_query_dict(query)

        if not current_groupby:
            return {next(iter(formulas_dict.values())): build_result_dict(report, query_res_lines)}
        else:
            rslt = []

            all_res_per_grouping_key = {}
            for query_res in query_res_lines:
                grouping_key = query_res['grouping_key']
                all_res_per_grouping_key.setdefault(grouping_key, []).append(query_res)

            for grouping_key, query_res_lines in all_res_per_grouping_key.items():
                rslt.append((grouping_key, build_result_dict(report, query_res_lines)))

            return {next(iter(formulas_dict.values())): rslt}

    def open_journal_items(self, options, params):
        params['view_ref'] = 'account.view_move_line_tree_grouped_partner'
        options_for_audit = {**options, 'date': {**options['date'], 'date_from': None}}
        report = self.env['account.report'].browse(options['report_id'])
        action = report.open_journal_items(options=options_for_audit, params=params)
        action.get('context', {}).update({'search_default_group_by_account': 0, 'search_default_group_by_partner': 1})
        return action

    def _common_custom_unfold_all_batch_data_generator(self, internal_type, report, options, lines_to_expand_by_function):
        rslt = {} # In the form {full_sub_groupby_key: all_column_group_expression_totals for this groupby computation}
        report_periods = 6 # The report has 6 periods

        for expand_function_name, lines_to_expand in lines_to_expand_by_function.items():
            for line_to_expand in lines_to_expand: # In standard, this loop will execute only once
                if expand_function_name == '_report_expand_unfoldable_line_with_groupby':
                    report_line_id = report._get_res_id_from_line_id(line_to_expand.id, 'account.report.line')
                    expressions_to_evaluate = report.line_ids.expression_ids.filtered(lambda x: x.report_line_id.id == report_line_id and x.engine == 'custom')

                    if not expressions_to_evaluate:
                        continue

                    formulas_dict = {expressions_to_evaluate[0].formula: expressions_to_evaluate}  # We assume they all share the same custom engine
                    for column_group_index, column_group_options in report._split_options_per_column_group(options).items():
                        # Get all aml results by partner
                        aml_data_by_partner = {}
                        for formula_result in self._aged_partner_report_custom_engine_common(column_group_options, internal_type, 'id', formulas_dict).values():
                            for aml_id, aml_result in formula_result:
                                aml_result['aml_id'] = aml_id
                                aml_data_by_partner.setdefault(aml_result['partner_id'], []).append(aml_result)

                        # Iterate on results by partner to generate the content of the column group
                        partner_expression_totals = rslt.setdefault(f"[{report_line_id}]=>partner_id", {})\
                                                        .setdefault(column_group_index, {expression: {'value': [], 'sublines_info': set()} for expression in expressions_to_evaluate})
                        for partner_id, aml_data_list in aml_data_by_partner.items():
                            partner_values = self._prepare_partner_values()
                            for i in range(report_periods):
                                partner_values[f'period{i}'] = 0

                            # Build expression totals under the right key
                            partner_aml_expression_totals = rslt.setdefault(f"[{report_line_id}]partner_id:{partner_id}=>id", {})\
                                                                .setdefault(column_group_index, {expression: {'value': [], 'sublines_info': set()} for expression in expressions_to_evaluate})
                            for aml_data in aml_data_list:
                                for i in range(report_periods):
                                    period_value = aml_data[f'period{i}']
                                    partner_values[f'period{i}'] += period_value
                                    partner_values['total'] += period_value

                                for expression in expressions_to_evaluate:
                                    partner_aml_expression_totals[expression]['value'].append(
                                        (aml_data['aml_id'], aml_data[expression.subformula])
                                    )

                            for expression in expressions_to_evaluate:
                                partner_expression_totals[expression]['value'].append(
                                    (partner_id, partner_values[expression.subformula])
                                )
                                partner_expression_totals[expression]['sublines_info'].add(partner_id)

        return rslt

    def _prepare_partner_values(self):
        return {
            'invoice_date': None,
            'due_date': None,
            'amount_currency': None,
            'currency_id': None,
            'currency': None,
            'account_name': None,
            'total': 0,
        }

    def aged_partner_balance_audit(self, options, params, journal_type):
        """ Open a list of invoices/bills and/or deferral entries for the clicked cell

        :param dict options: the report's `options`
        :param dict params:  a dict containing:

             * ``calling_line_dict_id``: line id containing the optional account of the cell
             * ``expression_label``: the expression label of the cell
        """
        report = self.env['account.report'].browse(options['report_id'])
        action = self.env['ir.actions.actions']._for_xml_id('account.action_amounts_to_settle')
        journal_type_to_exclude = {'purchase': 'sale', 'sale': 'purchase'}
        if options:
            domain = [
                ('account_id.reconcile', '=', True),
                ('residual_at_date', '!=', 0),
                ('journal_id.type', '!=', journal_type_to_exclude.get(journal_type)),
                *self._build_domain_from_period(options, params['expression_label']),
                *report._get_options_domain(options, 'from_beginning'),
                *report._get_audit_line_groupby_domain(params['calling_line_dict_id']),
            ]
            action['domain'] = domain
            action['context'] = {
                'recon_limit': options['date']['date_to'],
            }
            if recon_date := report._get_option_recon_date(options):
                action['context']['search_default_open_on'] = recon_date.strftime('%Y-%m-%d')
        return action

    def _build_domain_from_period(self, options, period):
        if period != "total" and period[-1].isdigit():
            period_number = int(period[-1])
            if period_number == 0:
                domain = [
                    '|',
                    ('date_maturity', '>=', options['date']['date_to']),
                    '&', ('date_maturity', '=', False), ('date', '>=', options['date']['date_to']),
                ]
            else:
                options_date_to = datetime.datetime.strptime(options['date']['date_to'], '%Y-%m-%d')
                period_end = options_date_to - datetime.timedelta(30*(period_number-1)+1)
                period_start = options_date_to - datetime.timedelta(30*(period_number))
                domain = [
                        '|',
                        '&', ('date_maturity', '>=', period_start), ('date_maturity', '<=', period_end),
                        '&', '&', ('date_maturity', '=', False), ('date', '>=', period_start), ('date', '<=', period_end),
                    ]
                if period_number == 5:
                    domain = [
                        '|',
                        ('date_maturity', '<=', period_end),
                        '&', ('date_maturity', '=', False), ('date', '<=', period_end),
                    ]
        else:
            domain = []
        return domain

    def open_followup_report(self, options, params):
        partner_id = self.env['account.report']._get_res_id_from_line_id(params['line_id'], 'res.partner')
        followup_report = self.env.ref('account_reports.followup_report')
        followup_options = followup_report.get_options(options)

        followup_options['unfold_all'] = True
        if partner_id:
            followup_options['partner_ids'] = [partner_id]

        action_vals = self.env['ir.actions.actions']._for_xml_id('account_reports.action_account_report_followup')
        action_vals['params'] = {
            'options': followup_options,
            'ignore_session': True,
        }

        return action_vals


class AccountAgedPayableReportHandler(models.AbstractModel):
    _name = 'account.aged.payable.report.handler'
    _inherit = ['account.aged.partner.balance.report.handler']
    _description = 'Aged Payable Custom Handler'

    def open_journal_items(self, options, params):
        payable_account_type = {'id': 'trade_payable', 'name': _("Payable"), 'selected': True}

        if 'account_type' in options:
            options['account_type'].append(payable_account_type)
        else:
            options['account_type'] = [payable_account_type]

        return super().open_journal_items(options, params)

    def _custom_unfold_all_batch_data_generator(self, report, options, lines_to_expand_by_function):
        # We only optimize the unfold all if the groupby value of the report has not been customized. Else, we'll just run the full computation
        aged_payable_line = self.env.ref('account_reports.aged_payable_line')
        if aged_payable_line._get_groupby(options).replace(' ', '') == (aged_payable_line.groupby or report.groupby).replace(' ', ''):
            return self._common_custom_unfold_all_batch_data_generator('liability_payable', report, options, lines_to_expand_by_function)
        return {}

    def action_audit_cell(self, options, params):
        return self.aged_partner_balance_audit(options, params, 'purchase')


class AccountAgedReceivableReportHandler(models.AbstractModel):
    _name = 'account.aged.receivable.report.handler'
    _inherit = ['account.aged.partner.balance.report.handler']
    _description = 'Aged Receivable Custom Handler'

    def open_journal_items(self, options, params):
        receivable_account_type = {'id': 'trade_receivable', 'name': _("Receivable"), 'selected': True}

        if 'account_type' in options:
            options['account_type'].append(receivable_account_type)
        else:
            options['account_type'] = [receivable_account_type]

        return super().open_journal_items(options, params)

    def _custom_unfold_all_batch_data_generator(self, report, options, lines_to_expand_by_function):
        # We only optimize the unfold all if the groupby value of the report has not been customized. Else, we'll just run the full computation
        aged_receivable_line = self.env.ref('account_reports.aged_receivable_line')
        if aged_receivable_line._get_groupby(options).replace(' ', '') == (aged_receivable_line.groupby or report.groupby).replace(' ', ''):
            return self._common_custom_unfold_all_batch_data_generator('asset_receivable', report, options, lines_to_expand_by_function)
        return {}

    def action_audit_cell(self, options, params):
        return self.aged_partner_balance_audit(options, params, 'sale')

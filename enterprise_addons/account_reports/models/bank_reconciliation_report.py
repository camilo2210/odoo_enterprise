import ast
from datetime import date
from dateutil.relativedelta import relativedelta

from odoo import fields, models
from odoo.fields import Domain
from odoo.tools import SQL


class AccountBankReconciliationReportHandler(models.AbstractModel):
    _name = 'account.bank.reconciliation.report.handler'
    _inherit = ['account.report.custom.handler']
    _description = 'Bank Reconciliation Report Custom Handler'

    ######################
    # Options
    ######################
    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)

        # Options is needed otherwise some elements added in the post processor go on the total line
        if 'active_id' in self.env.context and self.env.context.get('active_model') == 'account.journal':
            options['bank_reconciliation_report_journal_id'] = self.env.context['active_id']
        elif 'bank_reconciliation_report_journal_id' in previous_options:
            options['bank_reconciliation_report_journal_id'] = previous_options['bank_reconciliation_report_journal_id']
        else:
            # This should never happen except in some test cases
            options['bank_reconciliation_report_journal_id'] = self.env['account.journal'].search([('type', '=', 'bank')], limit=1).id

        # Remove multi-currency columns if needed
        is_multi_currency = self.env.user.has_group('base.group_multi_currency') and self.env.user.has_group('base.group_no_one')
        if not is_multi_currency:
            options['columns'] = [
                column for column in options['columns']
                if column['expression_label'] not in ('amount_currency', 'currency')
            ]

        # This template override adds warning with tooltip on report lines.
        options['custom_display_config'] = {
            'templates': {
                'AccountReportLineName': 'account_reports.BankReconciliationReportLineName',
            },
        }

        # This removes journal groups option from the report like Local Gaap, IFRS.
        # We don't need `journals` options as we get journal from `bank_reconciliation_report_journal_id`.
        options.pop('journals', None)

    ######################
    # Return function
    ######################
    def _build_bank_reco_engine_result(self, date=None, label=None, amount_currency=None, amount_currency_currency_id=None, amount=0, amount_currency_id=None, has_sublines=False):
        return {
            'date': date,
            'label': label,
            'amount_currency': amount_currency,
            'amount_currency_currency_id': amount_currency_currency_id,
            'amount': amount,
            'amount_currency_id': amount_currency_id,
            'has_sublines': has_sublines,
        }

    ######################
    # Engine
    ######################
    def _report_engine_forced_currency_amount(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        _journal, journal_currency, _company_currency = self._get_bank_journal_and_currencies(options)
        return {next(iter(formulas_dict.values())): self._build_bank_reco_engine_result(amount_currency_id=journal_currency.id)}

    def _report_engine_starting_balance(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        journal, journal_currency, _company_currency = self._get_bank_journal_and_currencies(options)
        bank_balance, _st_line_ids = self._get_bank_balance_and_last_statement_lines(options, journal, 'to_beginning_of_period')
        return {next(iter(formulas_dict.values())): self._build_bank_reco_engine_result(amount=bank_balance, amount_currency_id=journal_currency.id)}

    def _report_engine_reconciled_receipts(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        return self._bank_reconciliation_report_custom_engine_common(options, 'receipts', current_groupby, formulas_dict, False)

    def _report_engine_reconciled_payments(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        return self._bank_reconciliation_report_custom_engine_common(options, 'payments', current_groupby, formulas_dict, False)

    def _report_engine_unreconciled_receipts(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        return self._bank_reconciliation_report_custom_engine_common(options, 'receipts', current_groupby, formulas_dict, True)

    def _report_engine_unreconciled_payments(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        return self._bank_reconciliation_report_custom_engine_common(options, 'payments', current_groupby, formulas_dict, True)

    def _report_engine_outstanding_receipts(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        return self._bank_reconciliation_report_custom_engine_outstanding_common(options, 'receipts', current_groupby, formulas_dict)

    def _report_engine_outstanding_payments(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        return self._bank_reconciliation_report_custom_engine_outstanding_common(options, 'payments', current_groupby, formulas_dict)

    def _report_engine_misc_operations(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        report = self.env['account.report'].browse(options['report_id'])
        if current_groupby:
            report._check_groupby_fields([current_groupby])

        def build_result_dict(query_res_lines):
            if current_groupby == 'id':
                res = query_res_lines[0]
                currency = self.env['res.currency'].browse(res['currency_id'])
                convert = currency != journal_currency
                return self._build_bank_reco_engine_result(
                    date=res['date'],
                    label=res['ref'],
                    amount_currency=res['amount_currency'] if convert else None,
                    amount_currency_currency_id=currency.id if convert else None,
                    amount=company_currency._convert(res['balance'], journal_currency, journal.company_id, options['date']['date_to']) if convert else res['amount_currency'],
                    amount_currency_id=journal_currency.id,
                )
            else:
                amount = 0
                for res in query_res_lines:
                    convert = self.env['res.currency'].browse(res['currency_id']) != journal_currency
                    amount += company_currency._convert(res['balance'], journal_currency, journal.company_id, options['date']['date_to']) if convert else res['amount_currency']
                return self._build_bank_reco_engine_result(
                    amount=amount,
                    amount_currency_id=journal_currency.id,
                    has_sublines=bool(query_res_lines),
                )

        journal, journal_currency, company_currency = self._get_bank_journal_and_currencies(options)
        exchange_journal = journal.company_id.currency_exchange_journal_id

        bank_miscellaneous_domain = self._get_bank_miscellaneous_move_lines_domain(options, journal)
        bank_miscellaneous_domain = Domain.AND([
            bank_miscellaneous_domain,
            [('journal_id', '!=', exchange_journal.id)]
        ])

        base_query = report._get_report_query(options, 'strict_range', domain=bank_miscellaneous_domain or [])

        groupby_field_sql = self.env['account.move.line']._field_to_sql('account_move_line', current_groupby, base_query) if current_groupby else SQL('NULL')
        query_sql = SQL(
            """
            SELECT
                 %(select_from_groupby)s,
                 account_move_line.ref,
                 account_move_line.date,
                 account_move_line.balance,
                 account_move_line.amount_currency,
                 account_move_line.currency_id
            FROM %(table_references)s
           WHERE %(search_condition)s
        GROUP BY %(groupby)s,
                 account_move_line.ref,
                 account_move_line.date,
                 account_move_line.balance,
                 account_move_line.amount_currency,
                 account_move_line.currency_id
            """,
            select_from_groupby=SQL('%s AS grouping_key', groupby_field_sql),
            table_references=base_query.from_clause,
            search_condition=base_query.where_clause,
            groupby=groupby_field_sql if current_groupby else SQL('account_move_line.ref'),
        )

        self.env.cr.execute(query_sql)
        query_res_lines = self.env.cr.dictfetchall()

        return {next(iter(formulas_dict.values())): self._compute_result(query_res_lines, current_groupby, build_result_dict)}

    def _report_engine_gl_balance(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        report = self.env['account.report'].browse(options['report_id'])
        journal, journal_currency, _company_currency = self._get_bank_journal_and_currencies(options)
        gl_balance = self._get_gl_balance(options, report, journal, 'from_beginning')
        return {next(iter(formulas_dict.values())): self._build_bank_reco_engine_result(amount=gl_balance, amount_currency_id=journal_currency.id)}

    def _bank_reconciliation_report_custom_engine_common(self, options, internal_type, current_groupby, formulas_dict, unreconciled):
        """
            Retrieve entries for bank reconciliation based on specified parameters.
            Parameters:
            - options (dict): A dictionary containing options of the report.
            - internal_type (str): The internal type used for classification (e.g., receipt, payment, all). For the receipt
                                   we will query the entries with a positive amounts and for the payment
                                   the negative amounts.
                                   If the internal type is all it will get all the
                                   entries positive or negative.
            - current_groupby (str): The current grouping criteria.
            - formulas_dict (dict): A dictionary with custom engine method name as key and recordset of all expressions as value.
            - unreconciled (bool): If True, query the unreconciled entries only. If False, query the reconciled entries only.

        """
        journal, journal_currency, _company_currency = self._get_bank_journal_and_currencies(options)
        if not journal:
            return {next(iter(formulas_dict.values())): self._build_bank_reco_engine_result()}

        report = self.env['account.report'].browse(options['report_id'])
        if current_groupby:
            report._check_groupby_fields([current_groupby])

        def build_result_dict(query_res_lines):
            # The query should find exactly one account move line per bank statement line
            if current_groupby == 'id':
                res = query_res_lines[0]
                foreign_currency = self.env['res.currency'].browse(res['foreign_currency_id'])
                rate = 1  # journal_currency / foreign_currency
                if foreign_currency:
                    rate = (res['amount'] / res['amount_currency']) if res['amount_currency'] else 0

                if unreconciled:
                    amount = -res['amount_residual'] * rate if res['amount_residual'] else None
                    amount_currency = -res['amount_residual'] if res['foreign_currency_id'] else None
                elif res['is_reconciled']:
                    amount = res['amount'] if res['amount'] else None
                    amount_currency = res['amount_currency'] if res['foreign_currency_id'] else None
                else:
                    amount = res['amount'] + res['amount_residual'] * rate if res['amount'] else None
                    amount_currency = res['amount_currency'] + res['amount_residual'] if res['foreign_currency_id'] else None

                return self._build_bank_reco_engine_result(
                    date=res['date'] if res['date'] else None,
                    label=res['payment_ref'] or res['ref'] or '/',
                    amount_currency=amount_currency,
                    amount_currency_currency_id=foreign_currency.id if res['foreign_currency_id'] else None,
                    amount=amount,
                    amount_currency_id=journal_currency.id,
                    has_sublines=True,
                )
            else:
                amount = 0
                for res in query_res_lines:
                    rate = 1  # journal_currency / foreign_currency
                    if res['foreign_currency_id']:
                        rate = (res['amount'] / res['amount_currency']) if res['amount_currency'] else 0

                    if unreconciled:
                        amount += -res['amount_residual'] * rate
                    elif res['is_reconciled']:
                        amount += res['amount']
                    else:
                        amount += res['amount'] + res['amount_residual'] * rate

                return self._build_bank_reco_engine_result(
                    amount=amount,
                    amount_currency_id=journal_currency.id,
                    has_sublines=bool(len(query_res_lines)),
                )

        query = report._get_report_query(options, 'strict_range', domain=[
            ('journal_id', '=', journal.id),
            ('account_id', '=', journal.default_account_id.id),  # There should be only 1 line per move with that account
        ])

        if internal_type == 'receipts':
            st_line_amount_condition = SQL("AND st_line.amount > 0")
        elif internal_type == 'payments':
            st_line_amount_condition = SQL("AND st_line.amount < 0")
        else:
            st_line_amount_condition = SQL("")

        if unreconciled:
            # Fully unreconciled and partially reconciled transactions.
            reconciliation_condition = SQL("AND st_line.is_reconciled IS NOT TRUE")
        else:
            # Fully reconciled and partially reconciled transactions.
            reconciliation_condition = SQL("""
                AND (
                    st_line.is_reconciled IS TRUE
                    OR (st_line.foreign_currency_id IS NULL AND -st_line.amount_residual != st_line.amount)
                    OR (st_line.foreign_currency_id IS NOT NULL AND -st_line.amount_residual != st_line.amount_currency)
                )
            """)

        groupby_field_sql = self.env['account.move.line']._field_to_sql("account_move_line", current_groupby, query) if current_groupby else SQL('NULL')
        # Build query
        query = SQL(
            """
           SELECT %(select_from_groupby)s,
                  st_line.id,
                  move.name,
                  move.ref,
                  move.date,
                  st_line.payment_ref,
                  st_line.amount,
                  st_line.amount_residual,
                  st_line.amount_currency,
                  st_line.foreign_currency_id,
                  st_line.is_reconciled
             FROM %(table_references)s
             JOIN account_bank_statement_line st_line ON st_line.move_id = account_move_line.move_id
             JOIN account_move move ON move.id = st_line.move_id
            WHERE %(search_condition)s
                  %(reconciliation_condition)s
                  %(st_line_amount_condition)s
         GROUP BY %(group_by)s,
                  st_line.id,
                  move.id
            """,
            select_from_groupby=SQL("%s AS grouping_key", groupby_field_sql),
            table_references=query.from_clause,
            search_condition=query.where_clause,
            reconciliation_condition=reconciliation_condition,
            st_line_amount_condition=st_line_amount_condition,
            group_by=groupby_field_sql if current_groupby else SQL('st_line.id'),  # Same key in the groupby because we can't put a null key in a group by
        )

        self.env.cr.execute(query)
        query_res_lines = self.env.cr.dictfetchall()

        return {next(iter(formulas_dict.values())): self._compute_result(query_res_lines, current_groupby, build_result_dict)}

    def _bank_reconciliation_report_custom_engine_outstanding_common(self, options, internal_type, current_groupby, formulas_dict):
        """
            This engine retrieves the data of all recorded payments/receipts that have not been matched with a bank
            statement yet
        """
        journal, journal_currency, company_currency = self._get_bank_journal_and_currencies(options)
        if not journal:
            return {next(iter(formulas_dict.values())): self._build_bank_reco_engine_result()}

        report = self.env['account.report'].browse(options['report_id'])
        if current_groupby:
            report._check_groupby_fields([current_groupby])

        def build_result_dict(query_res_lines):
            if current_groupby == 'id':
                res = query_res_lines[0]
                convert = not (journal_currency and res['currency_id'] == journal_currency.id)
                amount_currency = res['amount_residual_currency']
                balance = res['amount_residual']
                foreign_currency = self.env['res.currency'].browse(res['currency_id'])

                return self._build_bank_reco_engine_result(
                    date=res['date'] if res['date'] else None,
                    label=res['ref'] if res['ref'] else None,
                    amount_currency=amount_currency if convert else None,
                    amount_currency_currency_id=foreign_currency.id if convert else None,
                    amount=company_currency._convert(balance, journal_currency, journal.company_id, options['date']['date_to']) if convert else amount_currency,
                    amount_currency_id=journal_currency.id,
                )
            else:
                amount = 0
                for res in query_res_lines:
                    convert = not (journal_currency and res['currency_id'] == journal_currency.id)
                    if convert:
                        balance = res['amount_residual']
                        amount += company_currency._convert(balance, journal_currency, journal.company_id, options['date']['date_to'])
                    else:
                        amount += res['amount_residual_currency']

                return self._build_bank_reco_engine_result(
                    amount=amount,
                    amount_currency_id=journal_currency.id,
                    has_sublines=bool(len(query_res_lines)),
                )

        accounts = journal._get_journal_inbound_outstanding_payment_accounts() + journal._get_journal_outbound_outstanding_payment_accounts()

        query = report._get_report_query(options, 'from_beginning', domain=[
            ('journal_id', '=', journal.id),
            ('account_id', 'in', accounts.ids),
            ('full_reconcile_id', '=', False),
            ('amount_residual_currency', '!=', 0.0)
        ])

        # Build query
        groupby_field_sql = self.env['account.move.line']._field_to_sql("account_move_line", current_groupby, query) if current_groupby else SQL('NULL')
        query = SQL(
            """
           SELECT %(select_from_groupby)s,
                  account_move_line.account_id,
                  account_move_line.payment_id,
                  account_move_line.move_id,
                  account_move_line.currency_id,
                  account_move_line.move_name AS name,
                  account_move_line.ref,
                  account_move_line.date,
                  SUM(account_move_line.amount_residual) AS amount_residual,
                  SUM(account_move_line.balance) AS balance,
                  SUM(account_move_line.amount_residual_currency) AS amount_residual_currency,
                  SUM(account_move_line.amount_currency) AS amount_currency
             FROM %(table_references)s
             JOIN account_account account ON account.id = account_move_line.account_id
            WHERE %(search_condition)s
              AND %(is_receipt)s
         GROUP BY %(group_by)s,
                  account_move_line.account_id,
                  account_move_line.payment_id,
                  account_move_line.move_id,
                  account_move_line.currency_id,
                  account_move_line.move_name,
                  account_move_line.ref,
                  account_move_line.date
           """,
            select_from_groupby=SQL("%s AS grouping_key", groupby_field_sql),
            table_references=query.from_clause,
            search_condition=query.where_clause,
            is_receipt=SQL("account_move_line.balance > 0") if internal_type == "receipts" else SQL("account_move_line.balance < 0"),
            group_by=groupby_field_sql if current_groupby else SQL('account_move_line.account_id'),  # Same key in the groupby because we can't put a null key in a group by
        )
        self.env.cr.execute(query)
        query_res_lines = self.env.cr.dictfetchall()

        return {next(iter(formulas_dict.values())): self._compute_result(query_res_lines, current_groupby, build_result_dict)}

    def _compute_result(self, query_res_lines, current_groupby, build_result_dict):
        if not current_groupby:
            return build_result_dict(query_res_lines)
        else:
            rslt = []

            all_res_per_grouping_key = {}
            for query_res in query_res_lines:
                grouping_key = query_res['grouping_key']
                all_res_per_grouping_key.setdefault(grouping_key, []).append(query_res)

            for grouping_key, query_res_lines in all_res_per_grouping_key.items():
                rslt.append((grouping_key, build_result_dict(query_res_lines)))

            return rslt

    def _custom_line_postprocessor(self, report, options, lines):
        lines = super()._custom_line_postprocessor(report, options, lines)
        journal, journal_currency, _company_currency = self._get_bank_journal_and_currencies(options)
        if not journal:
            return lines

        date_from = fields.Date.from_string(options['date']['date_from']).strftime('%B %d %Y')
        date_to = fields.Date.from_string(options['date']['date_to']).strftime('%B %d %Y')

        amount_col_index = None
        monetary_col_indexes = []
        for index, col in enumerate(options['columns']):
            if col['figure_type'] == 'monetary':
                monetary_col_indexes.append(index)

            if col['expression_label'] == 'amount':
                amount_col_index = index

        for line in lines:
            if line.code == 'bank_name':
                line.name = journal.default_account_id.display_name
            elif line.code == 'starting_balance':
                line.name = self.env._("Opening Bank Balance as of %(date_from)s", date_from=date_from)
                line.css_class = 'o_bold_tr'
                line.columns[amount_col_index].is_zero = False  # We want this line to be always visible even with filter 'Hide lines at 0'.
                amount_column = line.columns[amount_col_index]
                if starting_balance_warning := self._get_gl_mismatch_warning(options, journal, journal_currency, report, amount_column.no_format, amount_column.format_params, 'to_beginning_of_period'):
                    line.update_values(**starting_balance_warning)
            elif line.code == 'ending_balance':
                line.name = self.env._("Calculated Ending Bank Balance as of %(date_to)s", date_to=date_to)
                line.css_class = 'o_bold_tr'
                line.columns[amount_col_index].is_zero = False
                amount_column = line.columns[amount_col_index]
                if ending_balance_warning := self._get_gl_mismatch_warning(options, journal, journal_currency, report, amount_column.no_format, amount_column.format_params, 'from_beginning'):
                    line.update_values(**ending_balance_warning)
            elif line.code == 'gl_balance':
                line.name = self.env._("Ending General Ledger Balance as of %(date_to)s", date_to=date_to)
                line.css_class = 'line_level_0 text-info'
                line.columns[amount_col_index].is_zero = False
            elif line.code == 'misc_operations' and line.groupby and line.unfoldable and (misc_warning := self._get_misc_operations_warning(options, journal)):
                line.update_values(**misc_warning)
                line.columns[amount_col_index].is_zero = False

            # Check if it's a leaf node
            model, _model_id = report._get_model_info_from_id(line.id)
            if model == "account.move.line":
                line_name = line.name.split()
                line.name = line_name[0]  # This will give just the name without the ref or label

            for col_index in monetary_col_indexes:
                line.columns[col_index].css_class = ' '  # This prevents adding text-danger class for negative amounts.

        return lines

    def _customize_warnings(self, report, options, all_column_groups_expression_totals, warnings):
        journal, _journal_currency, _company_currency = self._get_bank_journal_and_currencies(options)
        inconsistent_statements_line_ids = self._get_inconsistent_statements(options, journal).line_ids.ids
        lines_without_statement_ids = self._get_st_lines_without_statement(options, journal).ids

        if warnings is not None:
            if inconsistent_statements_line_ids:
                warnings['account_reports.inconsistent_statement_warning'] = {
                    'alert_type': 'warning',
                    'st_line_ids': inconsistent_statements_line_ids,
                    'name': self.env._("Inconsistent Statements"),
                }

            if lines_without_statement_ids:
                warnings['account_reports.lines_without_statement_warning'] = {
                    'alert_type': 'info',
                    'st_line_ids': lines_without_statement_ids,
                    'name': self.env._("Transactions without Statement"),
                }

    ######################
    # Getter
    ######################
    def _get_bank_journal_and_currencies(self, options):
        """
            Retrieve the bank journal and its associated currencies.
            :param options: The report options.
            :return:        A tuple of (bank journal, journal currency, company currency).
        """
        journal = self.env['account.journal'].browse(options.get('bank_reconciliation_report_journal_id'))
        company_currency = journal.company_id.currency_id
        journal_currency = journal.currency_id or company_currency
        return journal, journal_currency, company_currency

    def _get_previous_period_date_options(self, options):
        """
            Get the date option for the previous period.
            :param options: The report options.
            :return:        A dictionary containing the date options for the previous period.
        """
        date_option = self.env['account.report']._get_shifted_dates_period(options, options['date'], -1)
        if options['date']['period_type'] == 'custom':
            date_to = fields.Date.from_string(options['date']['date_from']) - relativedelta(days=1)
            date_option = self.env['account.report']._build_date_dict(options, date_option['date_from'], date_to, 'custom')
        return date_option

    def _get_bank_balance_and_last_statement_lines(self, options, journal, date_scope='from_beginning'):
        """
            Compute the bank balance and retrieve last statement lines.
            :param options:    The report options.
            :param journal:    The account.journal from which this report has been opened.
            :param date_scope: The date scope to apply ('from_beginning' or 'to_beginning_of_period').
            :return:           A tuple of (bank balance, list of account.bank.statement.line ids).
        """
        date_options = self._get_previous_period_date_options(options) if date_scope == 'to_beginning_of_period' else options['date']
        report_date = fields.Date.from_string(date_options['date_to'])
        move_state_condition = SQL("move.state != 'cancel'") if options['all_entries'] else SQL("move.state = 'posted'")
        query = SQL(
            """
                WITH statement_lines AS (
                    SELECT stl.id,
                           stl.amount,
                           stl.statement_id,
                           move.date
                      FROM account_bank_statement_line stl
                      JOIN account_move move
                        ON move.id = stl.move_id
                     WHERE stl.journal_id = %(journal_id)s
                       AND move.date <= %(report_date)s
                       AND %(move_state_condition)s
                )
                SELECT statement.id AS last_statement_id,
                       COALESCE(statement.balance_start, 0.0) AS balance_start,
                       COALESCE(stl_before_date.amount, 0.0) AS before_date_amount,
                       COALESCE(stl_before_date.ids, ARRAY[]::INTEGER[]) AS before_date_stl_ids,
                       COALESCE(unlinked_stl.amount, 0.0) AS unlinked_amount,
                       COALESCE(unlinked_stl.ids, ARRAY[]::INTEGER[]) AS unlinked_stl_ids
                  FROM (SELECT 1) seed
                  LEFT JOIN (
                        SELECT statement_id
                          FROM statement_lines
                         WHERE statement_id IS NOT NULL
                      ORDER BY date DESC, id DESC
                         LIMIT 1
                       ) last_stl ON TRUE
                  LEFT JOIN account_bank_statement statement
                    ON statement.id = last_stl.statement_id
                  LEFT JOIN LATERAL (
                        SELECT SUM(amount) AS amount,
                               ARRAY_AGG(id) AS ids
                          FROM statement_lines
                         WHERE statement_id = statement.id
                       ) stl_before_date ON TRUE
                  LEFT JOIN (
                        SELECT SUM(amount) AS amount,
                               ARRAY_AGG(id) AS ids
                          FROM statement_lines
                         WHERE statement_id IS NULL
                       ) unlinked_stl ON TRUE
            """,
            journal_id=journal.id,
            report_date=report_date,
            move_state_condition=move_state_condition,
        )

        self.env.cr.execute(query)
        res = self.env.cr.dictfetchall()[0]

        if date_scope == 'to_beginning_of_period' and not (res['last_statement_id'] or res['unlinked_stl_ids']):
            # Searching for first statement line instead of directly searching first statement
            # because we might receive first statement after the selected period's end date
            # but that statement's first transaction's date may be within the selected period.
            first_statement = self.env['account.bank.statement.line'].search(
                [
                    *self._get_st_lines_domain(options, journal),
                    ('statement_id', '!=', False),
                ],
                order='date, id', limit=1,
            ).statement_id
            return first_statement.balance_start, first_statement.line_ids.ids

        bank_balance = res['balance_start'] + res['before_date_amount'] + res['unlinked_amount']
        st_line_ids = res['before_date_stl_ids'] + res['unlinked_stl_ids']

        return bank_balance, st_line_ids

    def _get_gl_balance(self, options, report, journal, date_scope):
        """
            Retrieve the General Ledger balance for the given journal's bank account.
            :param options:    The report options.
            :param report:     The account.report record.
            :param journal:    The account.journal from which this report has been opened.
            :param date_scope: The date scope to apply ('from_beginning' or 'to_beginning_of_period').
            :return:           The GL balance.
        """
        domain = report._get_options_domain(options, date_scope)
        gl_balance = journal._get_journal_bank_account_balance(domain=domain)[0]
        return gl_balance

    def _get_inconsistent_statements(self, options, journal):
        """
            Retrieve the account.bank.statements records on the range of the options date having different starting
            balance regarding its previous statement.
            :param options: The report options.
            :param journal: The account.journal from which this report has been opened.
            :return:        An account.bank.statements recordset.
        """
        return self.env['account.bank.statement'].search([
            ('journal_id', '=', journal.id),
            ('date', '<=', options['date']['date_to']),
            ('is_valid', '=', False),
        ])

    def _get_st_lines_without_statement(self, options, journal):
        """
            Retrieve the account.bank.statement.line records on the range of the options date
            which are not related to any bank statement.
            :param options: The report options.
            :param journal: The account.journal from which this report has been opened.
            :return:        An account.bank.statement.line recordset.
        """
        return self.env['account.bank.statement.line'].search([
            *self._get_st_lines_domain(options, journal),
            ('statement_id', '=', False),
        ])

    def _get_st_lines_domain(self, options, journal):
        """
            Get the domain to be used to retrieve statement lines upto selected period's end date.
            :param options: The report options.
            :param journal: The account.journal from which this report has been opened.
            :return:        A domain to search on the account.bank.statement.line model.
        """
        return [
            ('journal_id', '=', journal.id),
            ('date', '<=', options['date']['date_to']),
            ('move_id.state', '!=', 'cancel') if options['all_entries'] else ('move_id.state', '=', 'posted'),
        ]

    def _get_bank_miscellaneous_move_lines_domain(self, options, journal):
        """
            Get the domain to be used to retrieve the journal items affecting the bank accounts but not linked to
            a statement line. (Limited in a year)
            :param options: The report options.
            :param journal: The account.journal from which this report has been opened.
            :return:        A domain to search on the account.move.line model.

        """
        if not journal.default_account_id:
            return None

        report = self.env['account.report'].browse(options['report_id'])
        domain = [
            ('account_id', '=', journal.default_account_id.id),
            ('statement_line_id', '=', False),
            *report._get_options_domain(options, 'from_beginning'),
        ]

        fiscal_lock_date = journal.company_id._get_user_fiscal_lock_date(journal)
        if fiscal_lock_date != date.min:
            domain.append(('date', '>', fiscal_lock_date))

        if journal.company_id.account_opening_move_id:
            domain.append(('move_id', '!=', journal.company_id.account_opening_move_id.id))

        return domain

    def _get_gl_mismatch_warning(self, options, journal, journal_currency, report, bank_balance, format_params, date_scope):
        gl_balance = self._get_gl_balance(options, report, journal, date_scope)
        difference = bank_balance - gl_balance
        if not journal_currency.is_zero(difference):
            bank_balance = report._format_value(options, bank_balance, format_params=format_params, figure_type='monetary')
            gl_balance = report._format_value(options, gl_balance, format_params=format_params, figure_type='monetary')
            difference = report._format_value(options, difference, format_params=format_params, figure_type='monetary')
            if date_scope == 'to_beginning_of_period':
                warning_text = self.env._(
                    "The opening bank balance %(bank_balance)s does not match the General Ledger opening balance %(gl_balance)s for the selected report period, resulting in an unexplained difference of %(difference)s",
                    bank_balance=bank_balance,
                    gl_balance=gl_balance,
                    difference=difference,
                )
            else:
                warning_text = self.env._(
                    "The calculated ending bank balance %(bank_balance)s does not match the General Ledger ending balance %(gl_balance)s for the selected report period, resulting in an unexplained difference of %(difference)s",
                    bank_balance=bank_balance,
                    gl_balance=gl_balance,
                    difference=difference,
                )

            return {
                'warning_text': warning_text,
                'warning_action': 'action_redirect_to_general_ledger',
                'warning_params': {'date_scope': date_scope},
            }

    def _get_misc_operations_warning(self, options, journal):
        bank_miscellaneous_domain = self._get_bank_miscellaneous_move_lines_domain(options, journal)
        has_bank_miscellaneous_move_lines = bank_miscellaneous_domain and bool(self.env['account.move.line'].search_count(bank_miscellaneous_domain, limit=1))
        if has_bank_miscellaneous_move_lines:
            return {
                'warning_text': self.env._(
                    "'%(account_name)s' account balance is affected by journal items which don't originate from a bank statement or payment.",
                    account_name=journal.default_account_id.display_name,
                ),
                'warning_action': 'open_bank_miscellaneous_move_lines',
            }
        else:
            return None

    ################
    # Audit
    ################
    def action_audit_cell(self, options, params):
        report_line = self.env['account.report.line'].browse(params['report_line_id'])

        if report_line.code == 'starting_balance':
            journal = self.env['account.journal'].browse(options['bank_reconciliation_report_journal_id'])
            _bank_balance, st_line_ids = self._get_bank_balance_and_last_statement_lines(options, journal, 'to_beginning_of_period')
            return self.action_redirect_to_bank_statement_widget(options, {'st_line_ids': st_line_ids})
        elif report_line.code == 'gl_balance':
            return self.action_redirect_to_general_ledger(options, {'date_scope': 'from_beginning'})

        return report_line.report_id.action_audit_cell(options, params)

    ################
    # ACTIONS
    ################
    def action_redirect_to_general_ledger(self, options, params):
        """
            Action to redirect to the general ledger
            :param options:     The report options.
            :param params:      The action params containing 'date_scope'('from_beginning' or 'to_beginning_of_period').
            :return:            Actions to the report
        """
        general_ledger_action = self.env['ir.actions.actions']._for_xml_id('account_reports.action_account_report_general_ledger')
        if params.get('date_scope') == 'to_beginning_of_period':
            general_ledger_options = {
                **options,
                'date': self._get_previous_period_date_options(options),
            }
        else:
            general_ledger_options = options

        general_ledger_action['params'] = {
            'options': general_ledger_options,
            'ignore_session': True,
        }
        context = ast.literal_eval(general_ledger_action['context'])
        journal = self.env['account.journal'].browse(options.get('bank_reconciliation_report_journal_id'))
        context['default_filter_accounts'] = journal.default_account_id.code
        general_ledger_action['context'] = context

        return general_ledger_action

    def action_redirect_to_bank_statement_widget(self, options, params):
        """
            Redirect the user to the requested bank statement, if empty displays all bank transactions of the journal.
            :param options:     The report options.
            :param params:      The action params containing at least 'st_line_ids' and 'name'.
            :return:            A dictionary representing an ir.actions.act_window.
        """
        return self.env['account.bank.statement.line']._action_open_bank_reconciliation_widget(
            default_context={'create': False},
            extra_domain=[('id', 'in', params.get('st_line_ids'))],
            name=params.get('name'),
        )

    def open_bank_miscellaneous_move_lines(self, options):
        """
            An action opening the account.move.line list view affecting the bank account balance but not linked to
            a bank statement line.
            :param options: The report options.
            :return:        An action redirecting to the list view of journal items.
        """
        journal = self.env['account.journal'].browse(options['bank_reconciliation_report_journal_id'])

        return {
            'name': self.env._('Journal Items'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move.line',
            'views': [(self.env.ref('account.view_move_line_tree').id, 'list')],
            'domain': self._get_bank_miscellaneous_move_lines_domain(options, journal),
        }

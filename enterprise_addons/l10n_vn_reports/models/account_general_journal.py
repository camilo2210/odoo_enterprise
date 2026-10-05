import json
from collections import defaultdict
from textwrap import shorten

from odoo import models
from odoo.tools import SQL


class L10n_VnAccountGeneralJournalReportHandler(models.AbstractModel):
    _name = 'l10n_vn.account.general.journal.report.handler'
    _inherit = ['l10n_vn.account.report.counterpart.mixin', 'account.report.custom.handler']
    _description = 'VAS GENERAL JOURNAL Report S03a-DN Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        if self.env.user.has_group('base.group_multi_currency'):
            options['multi_currency'] = True
        else:
            options['columns'] = [
                column for column in options['columns']
                if column['expression_label'] != 'amount_currency'
            ]

        options['unfold_all'] = (options['export_mode'] == 'print' and not options.get('unfolded_lines')) or options['unfold_all']
        if options.get('force_not_unfold_all'):
            options['unfold_all'] = False

    def _caret_options_initializer(self):
        return {
            **self.env['account.report']._caret_options_initializer_default(),
            'id_with_accumulated_balance_caret': [
                {'name': self.env._("View Journal Entry"), 'action': 'caret_option_open_journal_entry'},
            ],
        }

    def caret_option_open_journal_entry(self, options, params):
        report = self.env['account.report'].browse(options['report_id'])
        _model, aml_key = report._get_model_info_from_id(params['line_id'])
        move = self.env['account.move.line'].browse(json.loads(aml_key)[1]).move_id

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': move.id,
            'view_mode': 'form',
            'views': [(report._resolve_caret_option_view(move), 'form')],
            'context': self.env.context,
        }

    def _get_custom_groupby_map(self):
        res = super()._get_custom_groupby_map()

        def move_label_builder(grouping_keys):
            names = {
                move['id']: move['display_name']
                for move in self.env['account.move'].browse(grouping_keys).read(['display_name'])
            }
            return {grouping_key: names.get(grouping_key, '') for grouping_key in grouping_keys}

        def aml_label_builder(grouping_keys):
            keys_names = {}
            for grouping_key in grouping_keys:
                *_, is_tax_closing, account_code, account_name, line_name = json.loads(grouping_key)
                name_parts = [account_code, account_name] if is_tax_closing else [account_code, account_name, line_name]
                keys_names[grouping_key] = shorten(' '.join(filter(None, name_parts)), width=200)
            return keys_names

        res['move_id'] = {
            'model': 'account.move',
            'domain_builder': lambda grouping_key: [('move_id', '=', grouping_key)],
            'label_builder': move_label_builder,
        }
        res['id_with_accumulated_balance'] = {
            'model': None,
            'domain_builder': lambda grouping_key: [('id', '=', json.loads(grouping_key)[1])],
            'caret_builder': lambda grouping_key: 'id_with_accumulated_balance_caret',
            'label_builder': aml_label_builder,
        }
        return res

    def _get_extra_grouping_key_values(self, row):
        return [row['account_code'], row['account_name'], row['line_name']]

    def _report_engine_s03a_dn(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        return self._report_engine_counterpart_lines(options, date_scope, formulas_dict, current_groupby, warnings=warnings)

    def _get_query(self, options, current_groupby):
        report = self.env['account.report'].browse(options['report_id'])
        # Unlike the general ledger, the general journal only lists what was actually
        # posted during the period: there is no balance to carry over, hence no
        # 'from_beginning' scope and no initial balance rows (rows with a NULL id).
        report_query = report._get_report_query(options, 'strict_range')

        if options.get('export_mode') == 'print' and options.get('filter_search_bar') and current_groupby == 'move_id':
            search_bar_sql = SQL(
                "AND move.name ILIKE %(search_bar_pattern)s",
                search_bar_pattern=f"%{options['filter_search_bar']}%",
            )
        else:
            search_bar_sql = SQL()

        additional_select = SQL("")
        groupby = []
        order_clause = []
        if current_groupby == 'move_id':
            additional_select = SQL("""
                account_move_line.move_id AS move_id,
                MIN(account_move_line.date) AS date,
                MIN(move.name) AS move_name,
                CASE WHEN COUNT(DISTINCT partner.id) = 1 THEN MIN(partner.name) END AS partner_name,

                -- An entry balances out, so summing its amounts in currency would always
                -- report 0: report the total of its debit side instead, the counterpart
                -- in currency of the Debit and Credit columns of the entry.
                CASE
                    WHEN MIN(account_move_line.currency_id) = MAX(account_move_line.currency_id)
                    THEN SUM(GREATEST(account_move_line.amount_currency, 0))
                    ELSE NULL
                END AS amount_currency,
                CASE
                    WHEN MIN(account_move_line.currency_id) = MAX(account_move_line.currency_id)
                    THEN MIN(account_move_line.currency_id)
                END AS currency_id,
                """)
            groupby = [SQL("account_move_line.move_id")]
            order_clause = [SQL("MIN(account_move_line.date), MIN(move.name)")]
        elif current_groupby == 'id_with_accumulated_balance':
            account_code_select = self.env['account.account']._field_to_sql('account_move_line__account_id', 'code', report_query)
            account_name_select = self.env['account.account']._field_to_sql('account_move_line__account_id', 'name')
            additional_select = SQL("""
                account_move_line.id AS id,
                account_move_line.date AS date,
                MIN(move.name) AS move_name,

                SUM(account_move_line.amount_currency) AS amount_currency,
                MIN(partner.name) AS partner_name,
                MIN(account_move_line.currency_id) AS currency_id,
                MIN(account_move_line__account_id.id) AS account_id,

                MIN(account_move_line.name) AS line_name,
                MIN(%(account_name_select)s) AS account_name,
                MIN(%(account_code_select)s) AS account_code,
                """,
                account_name_select=account_name_select,
                account_code_select=account_code_select,
            )
            groupby = [SQL("1"), SQL("2"), SQL("account_move_line.account_id")]
            order_clause = [SQL("2, move_name, 1")]
        elif current_groupby:
            groupby_field_sql = self.env['account.move.line']._field_to_sql('account_move_line', current_groupby, report_query)
            additional_select = SQL("%s AS %s,", groupby_field_sql, SQL.identifier(current_groupby))
            groupby = [groupby_field_sql]

        report_query.table._join('account_id')

        return SQL(
            """
            SELECT
                %(additional_select)s
                COALESCE(SUM(%(select_debit)s), 0.0) AS debit,
                COALESCE(SUM(%(select_credit)s), 0.0) AS credit,
                COALESCE(SUM(%(select_balance)s), 0.0) AS balance
            FROM %(from_clause)s

            LEFT JOIN res_partner partner ON partner.id = account_move_line.partner_id
            JOIN account_move move ON move.id = account_move_line.move_id

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
            where_clause=report_query.where_clause,
            search_bar_sql=search_bar_sql,
            additional_groupby=SQL("GROUP BY %s", SQL(",").join(groupby)) if groupby else SQL(),
            orderby_clause=SQL("ORDER BY %s", SQL(",").join(order_clause)) if order_clause else SQL(),
        )

    def _custom_line_postprocessor(self, report, options, lines):
        """
        Move the lines for which no counterpart could be determined under a dedicated
        section at the end of their journal entry.
        """
        lines = super()._custom_line_postprocessor(report, options, lines)
        if not lines:
            return lines

        cp_idx = next(
            (idx for idx, col in enumerate(options.get('columns', [])) if col.get('expression_label') == 'counterpart_account'),
            None,
        )
        if cp_idx is None:
            return lines

        uncategorized_by_move = defaultdict(list)
        for line in lines:
            if not line.parent_id or not self._is_uncategorized_line(report, line, cp_idx):
                continue
            parent_model, _parent_res_id = report._get_model_info_from_id(line.parent_id)
            if parent_model == 'account.move':
                uncategorized_by_move[line.parent_id].append(line)

        if not uncategorized_by_move:
            return lines

        uncategorized_line_ids = {line.id for group in uncategorized_by_move.values() for line in group}
        final_lines = []

        def flush(move_line_id):
            uncategorized_lines = uncategorized_by_move.pop(move_line_id, None)
            if not uncategorized_lines:
                return
            self._append_uncategorized_section(
                report, options, final_lines, move_line_id,
                uncategorized_lines, uncategorized_lines[0].level or 3,
            )

        pending_move_line_id = None
        for line in lines:
            markup = report._get_markup(line.id)
            # The section is injected at the end of the entry: either right before the
            # entry's own total line, or as soon as another entry starts.
            is_group_total = markup == 'total' and bool(line.parent_id)
            if pending_move_line_id and (is_group_total or line.parent_id != pending_move_line_id):
                flush(pending_move_line_id)
                pending_move_line_id = None

            if line.id in uncategorized_line_ids:
                pending_move_line_id = line.parent_id
                continue

            final_lines.append(line)

        # Trailing entry, when the report ends without a total line (e.g. load more).
        if pending_move_line_id:
            flush(pending_move_line_id)

        return final_lines

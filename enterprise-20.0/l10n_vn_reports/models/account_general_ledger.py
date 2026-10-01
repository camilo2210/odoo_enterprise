import json
from collections import defaultdict

from odoo import models

from odoo.addons.account_reports.utils.report_data_objects import AccountReportLineData


class L10n_VnAccountGeneralLedgerReportHandler(models.AbstractModel):
    _name = 'l10n_vn.account.general.ledger.report.handler'
    _inherit = ['l10n_vn.account.report.counterpart.mixin', 'account.general.ledger.report.handler']
    _description = 'VAS GENERAL LEDGER Report S03b-DN Handler'

    def _get_custom_groupby_map(self):
        res = super()._get_custom_groupby_map()
        original_label_builder = res['id_with_accumulated_balance']['label_builder']

        def custom_label_builder(grouping_keys):
            keys_names = original_label_builder(grouping_keys)

            # For Tax Closing journal lines, show only the move name without the line
            # label.  move_name and is_tax_closing are carried in the grouping key
            # (see account_report_counterpart_mixin.py _report_engine_counterpart_lines.get_grouping_key)
            # so no extra query is needed.
            for grouping_key in grouping_keys:
                if "balance_line" in grouping_key:
                    continue
                *_, move_name, is_tax_closing = json.loads(grouping_key)
                if is_tax_closing:
                    keys_names[grouping_key] = move_name or self.env._("Draft Entry")

            return keys_names

        res['id_with_accumulated_balance']['label_builder'] = custom_label_builder
        return res

    def _report_engine_s03b_dn(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        return self._report_engine_counterpart_lines(options, date_scope, formulas_dict, current_groupby, warnings=warnings)

    def _get_query(self, options, current_groupby):
        # The counterpart mixin builds the initial balance rows (the ones with a NULL id) and the period
        # rows from a single query, so it always needs the whole history, the way the general ledger
        # queried it before its initial balance was split into an engine of its own.
        return super()._get_query(options, 'from_beginning', current_groupby)

    def _custom_line_postprocessor(self, report, options, lines):
        lines = super()._custom_line_postprocessor(report, options, lines)
        if not lines:
            return lines

        # Identify the index of our target columns based on their expression_label
        cols_config = options.get('columns', [])
        col_indices = {
            col.get('expression_label'): i for i, col in enumerate(cols_config)
        }
        cp_idx = col_indices.get('counterpart_account')
        deb_idx = col_indices.get('debit')
        cre_idx = col_indices.get('credit')
        bal_deb_idx = col_indices.get('balance_debit')
        bal_cre_idx = col_indices.get('balance_credit')

        # State tracking variables
        uncategorized_by_parent = defaultdict(list)
        period_totals_by_parent = defaultdict(lambda: {'deb': 0, 'cre': 0})
        running_balances = {}
        processed_uncat_parents = set()
        period_totals_injected = set()

        # Helper to flush pending groups for a specific account
        def _flush_pending_for_parent(target_parent, lvl, target_list):
            if target_parent in uncategorized_by_parent and target_parent not in processed_uncat_parents:
                self._append_uncategorized_section(
                    report, options, target_list, target_parent,
                    uncategorized_by_parent[target_parent], lvl,
                )
                processed_uncat_parents.add(target_parent)

            if target_parent in period_totals_by_parent and target_parent not in period_totals_injected:
                p_deb = period_totals_by_parent[target_parent]['deb']
                p_cre = period_totals_by_parent[target_parent]['cre']
                pt_columns = []
                for i, col_opt in enumerate(cols_config):
                    if i == deb_idx:
                        pt_columns.append(report._build_column_data(p_deb, col_opt, options=options))
                    elif i == cre_idx:
                        pt_columns.append(report._build_column_data(p_cre, col_opt, options=options))
                    else:
                        pt_columns.append(report._build_column_data(None, col_opt, options=options))

                target_list.append(AccountReportLineData(
                    id=report._get_generic_line_id(None, None, markup='period_total', parent_line_id=target_parent),
                    name=self.env._("Total for Period"),
                    level=lvl,
                    parent_id=target_parent,
                    columns=pt_columns,
                    unfoldable=False,
                    unfolded=False,
                ))
                period_totals_injected.add(target_parent)

        for line in lines:
            parent_id = line.parent_id
            line_name = line.name or ''

            if not parent_id or not line.columns:
                continue

            markup, _model, value = report._get_model_info_from_id(line.id, include_markup=True) if line.id else (None, None, None)

            is_parent_account = report._get_model_info_from_id(parent_id)[0] == 'account.account'
            is_detail_line = isinstance(markup, dict) and markup.get('groupby') == 'id_with_accumulated_balance'
            is_balance_line = isinstance(value, str) and value.startswith('balance_line_')

            # Process Initial Balance Lines
            if is_parent_account and (markup == 'initial_balance' or 'Initial Balance' in line_name or is_balance_line):
                deb = (line.columns[deb_idx].no_format or 0) if deb_idx is not None else 0
                cre = (line.columns[cre_idx].no_format or 0) if cre_idx is not None else 0
                running_balances[parent_id] = deb - cre

                rb = running_balances[parent_id]
                if bal_deb_idx is not None:
                    line.columns[bal_deb_idx] = report._build_column_data(max(rb, 0), cols_config[bal_deb_idx], options=options)
                if bal_cre_idx is not None:
                    line.columns[bal_cre_idx] = report._build_column_data(abs(min(rb, 0)), cols_config[bal_cre_idx], options=options)

            # Process Standard Detail Lines
            elif is_parent_account and is_detail_line and not is_balance_line:
                if self._is_uncategorized_line(report, line, cp_idx):
                    uncategorized_by_parent[parent_id].append(line)

                deb = (line.columns[deb_idx].no_format or 0) if deb_idx is not None else 0
                cre = (line.columns[cre_idx].no_format or 0) if cre_idx is not None else 0
                period_totals_by_parent[parent_id]['deb'] += deb
                period_totals_by_parent[parent_id]['cre'] += cre

                running_balances.setdefault(parent_id, 0)
                running_balances[parent_id] += (deb - cre)
                rb = running_balances[parent_id]

                if bal_deb_idx is not None:
                    line.columns[bal_deb_idx] = report._build_column_data(max(rb, 0), cols_config[bal_deb_idx], options=options)
                if bal_cre_idx is not None:
                    line.columns[bal_cre_idx] = report._build_column_data(abs(min(rb, 0)), cols_config[bal_cre_idx], options=options)

        final_lines = []

        for line in lines:
            parent_id = line.parent_id
            line_name = line.name or ''

            markup = report._get_markup(line.id)

            # 1. Skip uncategorized lines here (they get injected under the new header)
            if self._is_uncategorized_line(report, line, cp_idx):
                continue

            # 2. Check if we hit the end of an account group
            is_account_total = (markup == 'total' and 'General Ledger' not in line_name and parent_id)

            # 3. Check if we hit the bottom-of-report totals appended by the parent class
            is_report_bottom = (markup == 'undistributed_profits_losses' or 'Total General Ledger' in line_name)

            # Flush injections before the account total line
            if is_account_total:
                _flush_pending_for_parent(parent_id, line.level or 3, final_lines)

            # If we hit the Grand Total/Unallocated lines, flush ANY remaining pending accounts
            if is_report_bottom:
                pending_parents = set(period_totals_by_parent.keys()) | set(uncategorized_by_parent.keys())
                for p_id in pending_parents:
                    last_child = next((ln for ln in reversed(final_lines) if ln.parent_id == p_id), None)
                    lvl = (last_child.level or 3) if last_child else 3
                    _flush_pending_for_parent(p_id, lvl, final_lines)

            final_lines.append(line)

        # Handle edge case: Trailing data without total lines at the very end of pagination
        pending_parents = set(period_totals_by_parent.keys()) | set(uncategorized_by_parent.keys())
        for p_id in pending_parents:
            last_child = next((ln for ln in reversed(final_lines) if ln.parent_id == p_id), None)
            lvl = (last_child.level or 3) if last_child else 3
            _flush_pending_for_parent(p_id, lvl, final_lines)

        return final_lines

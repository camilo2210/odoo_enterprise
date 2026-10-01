# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models
from odoo.addons.account_reports.models.account_report import NUMBER_FIGURE_TYPES
from odoo.tools import SQL
from odoo.addons.account_reports.utils.report_data_objects import AccountReportLineData


class L10nPhBoaGeneralJournalReportHandler(models.AbstractModel):
    _name = "l10n_ph.boa.general.journal.report.handler"
    _inherit = ["l10n_ph.boa.report.handler"]
    _description = """Grouping: root report line > account.move > account.move.line
    and a grand total line."""

    LEVEL_ROOT, LEVEL_MOVE, LEVEL_AML = 1, 3, 5

    def _build_custom_columns(self, report, options, vals):
        """Deduplicate columns values across colgroups."""
        columns = []
        last_cg_key = len(cg) - 1 if (cg := options.get("column_groups")) else None
        for c in options["columns"]:
            current_key = c.get("column_group_index")
            if (current_key) != last_cg_key and c.get("expression_label") not in ("debit", "credit"):
                columns.append(report._build_column_data("", c, options=options))
                continue
            columns.append(report._build_column_data(
                (vals.get(current_key) or {}).get(c["expression_label"]) or (0.0 if c.get("figure_type") in NUMBER_FIGURE_TYPES else ""),
                c,
                options=options,
                currency=self.env.company.currency_id
            ))
        return columns

    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals=None, warnings=None):
        queries = []
        for column_group_index, column_group_options in report._split_options_per_column_group(options).items():
            report_query = report._get_report_query(column_group_options, "strict_range")
            queries.append(SQL("""
                            SELECT %(column_group_index)s                  AS column_group_index,
                                   COALESCE(SUM(%(debit_select)s), 0.0)  AS debit,
                                   COALESCE(SUM(%(credit_select)s), 0.0) AS credit
                              FROM %(from_clause)s
                             WHERE %(where_clause)s
            """,
                column_group_index=column_group_index,
                debit_select=report_query.table.consolidation_debit,
                credit_select=report_query.table.consolidation_credit,
                from_clause=report_query.from_clause,
                where_clause=report_query.where_clause,
            ))

        if not queries:
            return []

        results = self.env.execute_query_dict(SQL(
            "SELECT * FROM (%s) AS total_summaries ORDER BY column_group_index",
            SQL(" UNION ALL ").join(queries)
        ))
        vals = {res["column_group_index"]: res for res in results}
        return [(0, AccountReportLineData(
            id=report._get_generic_line_id(None, None, markup="boa_root"),
            name="General Journal Report",
            level=self.LEVEL_ROOT,
            unfoldable=False,
            unfolded=True,
            columns=self._build_custom_columns(report, options, vals),
            expand_function="_report_expand_unfoldable_line_l10n_ph_gj_root",
        ))]

    def _report_expand_unfoldable_line_l10n_ph_gj_root(self, line_dict_id, groupby, options, unfold_all_batch_data=None, limit_to_load=None):
        def _get_report_line_move(report, options, move_id, line_values, parent_line_id):
            line_id = report._get_generic_line_id("account.move", move_id, parent_line_id=parent_line_id)
            is_unfolded = options.get("unfold_all") or line_id in options.get("unfolded_lines", [])
            return AccountReportLineData(
                id=line_id,
                parent_id=parent_line_id,
                name=line_values["move_name"],
                level=self.LEVEL_MOVE,
                caret_options="account.move",
                unfoldable=True,
                unfolded=is_unfolded,
                columns=self._build_custom_columns(report, options, line_values),
                expand_function="_report_expand_unfoldable_line_l10n_ph_gj_move",
            )

        report = self.env["account.report"].browse(options["report_id"])
        queries = []
        for column_group_index, column_group_options in report._split_options_per_column_group(options).items():
            report_query = report._get_report_query(column_group_options, "strict_range")
            queries.append(SQL("""
                            SELECT %(column_group_index)s      AS column_group_index,
                                   account_move_line.move_id AS move_id,
                                   move.name                 AS move_name,
                                   move.date                 AS date,
                                   SUM(%(debit_select)s)     AS debit,
                                   SUM(%(credit_select)s)    AS credit
                              FROM %(from_clause)s
                              JOIN account_move move ON move.id = account_move_line.move_id
                             WHERE %(where_clause)s
                          GROUP BY move.name,
                                   account_move_line.move_id,
                                   move.date
            """,
                column_group_index=column_group_index,
                debit_select=report_query.table.consolidation_debit,
                credit_select=report_query.table.consolidation_credit,
                from_clause=report_query.from_clause,
                where_clause=report_query.where_clause,
            ))

        full_query = SQL("""
                      SELECT * FROM (%(union_query)s) AS combined_moves
                    ORDER BY move_name,
                             move_id
        """,
            union_query=SQL(" UNION ALL ").join(queries),
        )

        results = self.env.execute_query_dict(full_query)
        lines_values = {}
        for res in results:
            move_id = res["move_id"]
            if move_id not in lines_values:
                lines_values[move_id] = {
                    "move_name": res["move_name"],
                    "move_date": res["date"],
                }
            lines_values[move_id][res["column_group_index"]] = res

        lines = []
        for move_id, line_vals in lines_values.items():
            if limit_to_load and len(lines) >= limit_to_load:
                break
            lines.append(_get_report_line_move(report, options, move_id, line_vals, parent_line_id=line_dict_id))

        load_more_count = max(len(lines_values) - limit_to_load, 0) if limit_to_load else 0
        if load_more_count:
            lines.append(report._create_load_more_line(
                self.env["account.report.line"],  # little hack since we don't have a real report line here
                line_dict_id,
                options,
                None,
                load_more_count,
                self.LEVEL_MOVE,
                groupby,
                "_report_expand_unfoldable_line_l10n_ph_gj_root",
                None
            ))

        return lines

    def _report_expand_unfoldable_line_l10n_ph_gj_move(self, line_dict_id, groupby, options, unfold_all_batch_data=None, limit_to_load=None):
        def _get_report_line_move_line(report, options, move_line_id, line_values, parent_line_id):
            line_id = report._get_generic_line_id("account.move.line", move_line_id, parent_line_id=parent_line_id)
            line = AccountReportLineData(
                id=line_id,
                parent_id=parent_line_id,
                name=line_values["line_name"] or "",
                level=self.LEVEL_AML,
                caret_options="account.move.line",
                columns=self._build_custom_columns(report, options, line_values),
            )
            line.update_values(
                csv_date=line_values["move_date"],
                csv_move_name=line_values["move_name"],
            )
            return line

        report = self.env["account.report"].browse(options["report_id"])
        move_id = report._get_res_id_from_line_id(line_dict_id, "account.move")
        queries = []
        for column_group_index, column_group_options in report._split_options_per_column_group(options).items():
            report_query = report._get_report_query(column_group_options, "strict_range")
            queries.append(SQL("""
                            SELECT %(column_group_index)s        AS column_group_index,
                                   move.id                     AS move_id,
                                   move.name                   AS move_name,
                                   move.date                   AS move_date,
                                   account_move_line.id        AS line_id,
                                   account_move_line.name      AS line_name,
                                   account_move_line.sequence  AS line_sequence,
                                   %(account_code_sql)s        AS account_code,
                                   %(account_name_sql)s        AS account_name,
                                   %(debit_select)s            AS debit,
                                   %(credit_select)s           AS credit
                              FROM %(from_clause)s
                              JOIN account_move move ON move.id = account_move_line.move_id
                         LEFT JOIN account_account account ON account.id = account_move_line.account_id
                             WHERE account_move_line.move_id = %(move_id)s
                               AND %(where_clause)s
            """,
                column_group_index=column_group_index,
                account_code_sql=self.env["account.account"]._field_to_sql("account", "code", report_query),
                account_name_sql=self.env["account.account"]._field_to_sql("account", "name", report_query),
                debit_select=report_query.table.consolidation_debit,
                credit_select=report_query.table.consolidation_credit,
                from_clause=report_query.from_clause,
                where_clause=report_query.where_clause,
                move_id=move_id
            ))

        full_query = SQL("""
            SELECT * FROM (
                %(union_query)s
            ) AS combined_lines
            ORDER BY line_sequence, line_id
        """,
            union_query=SQL(" UNION ALL ").join(queries),
        )

        results = self.env.execute_query_dict(full_query)
        lines_values = {}
        for res in results:
            lines_values.setdefault(res["line_id"], {
                "line_name": res["line_name"],
                "move_name": res["move_name"],
                "move_date": res["move_date"]
            })[res["column_group_index"]] = res

        return [_get_report_line_move_line(report, options, line_id, line_vals, parent_line_id=line_dict_id)
            for line_id, line_vals in lines_values.items()]

    # ================
    # .CSV file export
    # ================

    def _get_csv_row_from_line(self, line, options):
        """'csv_' prefixed fields are hidden and only passed for the export."""
        report = self.env["account.report"].browse(options["report_id"])
        _markup, model, _res_id = report._parse_line_id(line.id)[-1]
        if model != "account.move.line":
            return None

        cols = self._boa_map_cols(line, options)
        return [
            self._boa_clean(f'{line.get_custom()['csv_move_name'] or ""} {line.name or ""}'),
            line.get_custom().get('csv_date', ''),
            self._boa_get_str(cols, "account_code"),
            self._boa_get_str(cols, "account_name"),
            self._boa_get_amt(cols, "debit"),
            self._boa_get_amt(cols, "credit"),
        ]

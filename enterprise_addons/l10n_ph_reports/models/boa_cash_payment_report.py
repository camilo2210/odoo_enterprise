# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.addons.account_reports.models.account_report import NUMBER_FIGURE_TYPES
from odoo.addons.account_reports.utils.report_data_objects import AccountReportLineData
from odoo.fields import Domain
from odoo.tools import SQL


class L10nPhBoaCashReportHandler(models.AbstractModel):
    _name = "l10n_ph.boa.cash.report.handler"
    _inherit = ["l10n_ph.boa.report.handler"]
    _description = "Base Handler for Cash Receipts and Disbursements"

    LEVEL_ROOT, LEVEL_MOVE, LEVEL_AML = 1, 3, 5

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        report._init_options_journals(options, previous_options=previous_options, additional_journals_domain=[("type", "in", ("bank", "cash", "general"))])

    def _build_custom_columns(self, report, options, vals):
        """Deduplicate columns values across colgroups."""
        columns = []
        last_cg_key = len(cg) - 1 if (cg := options.get("column_groups")) else None
        for c in options["columns"]:
            current_key = c.get("column_group_index")
            if (current_key) != last_cg_key and c.get("expression_label") not in ["debit", "credit"]:
                columns.append(report._build_column_data("", c, options=options))
                continue
            columns.append(report._build_column_data(
                (vals.get(current_key) or {}).get(c["expression_label"]) or (0.0 if c.get("figure_type") in NUMBER_FIGURE_TYPES else ""),
                c,
                options=options,
                currency=self.env.company.currency_id
            ))
        return columns

    def _get_options_domain(self, options):
        # We evaluate the condition via 'move_id.line_ids' rather than filtering the lines directly
        # so that include the AR/AP counterpart lines that contain the Partner/TIN data.
        return Domain("move_id.line_ids", "any", Domain.AND([
            Domain("account_id.account_type", "in", ("asset_cash", "liability_credit_card")),
            Domain("debit" if options.get("ph_boa_book_type") == "cash_receipts" else "credit", ">", 0)
        ]))

    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals=None, warnings=None):
        queries = []
        for column_group_key, column_group_options in report._split_options_per_column_group(options).items():
            report_query = report._get_report_query(column_group_options, "strict_range", self._get_options_domain(options))
            queries.append(SQL("""
                SELECT %(column_group_key)s                  AS column_group_key,
                       COALESCE(SUM(%(debit_select)s), 0.0)  AS debit,
                       COALESCE(SUM(%(credit_select)s), 0.0) AS credit
                  FROM %(from_clause)s
                 WHERE %(where_clause)s
            """,
                column_group_key=column_group_key,
                debit_select=report_query.table.consolidation_debit,
                credit_select=report_query.table.consolidation_credit,
                from_clause=report_query.from_clause,
                where_clause=report_query.where_clause,
            ))

        results = self.env.execute_query_dict(SQL(" UNION ALL ").join(queries))
        vals = {res["column_group_key"]: res for res in results}
        return [(0, AccountReportLineData(
            id=report._get_generic_line_id(None, None, markup="boa_root"),
            name=report.name,
            level=self.LEVEL_ROOT,
            unfoldable=False,
            unfolded=True,
            columns=self._build_custom_columns(report, options, vals),
            expand_function="_report_expand_unfoldable_line_l10n_ph_boa_cash_root",
        ))]

    def _report_expand_unfoldable_line_l10n_ph_boa_cash_root(self, line_dict_id, groupby, options, unfold_all_batch_data=None, limit_to_load=None):
        def _get_move_line(report, options, move_id, line_values, parent_id):
            line_id = report._get_generic_line_id("account.move", move_id, parent_line_id=parent_id)
            is_unfolded = options.get("unfold_all") or line_id in options.get("unfolded_lines", [])
            return AccountReportLineData(
                id=line_id,
                parent_id=parent_id,
                name=line_values["move_name"],
                level=self.LEVEL_MOVE,
                caret_options="account.move",
                unfoldable=True,
                unfolded=is_unfolded,
                columns=self._build_custom_columns(report, options, line_values),
                expand_function="_report_expand_unfoldable_line_l10n_ph_boa_cash_move",
            )

        report = self.env["account.report"].browse(options["report_id"])
        queries = []
        for column_group_key, column_group_options in report._split_options_per_column_group(options).items():
            report_query = report._get_report_query(column_group_options, "strict_range", self._get_options_domain(options))
            queries.append(SQL("""
            SELECT %(column_group_key)s                          AS column_group_key,
                   move.id                                       AS move_id,
                   move.name                                     AS move_name,
                   move.date                                     AS date,
                   move.ref                                      AS reference,
                   partner.name                                  AS partner_name,
                   partner.vat                                   AS partner_vat,
                   CONCAT_WS(', ', partner.street, partner.city) AS partner_address,
                   SUM(%(debit_select)s)                         AS debit,
                   SUM(%(credit_select)s)                        AS credit
              FROM %(from_clause)s
              JOIN account_move move ON move.id = account_move_line.move_id
         LEFT JOIN res_partner partner ON partner.id = move.partner_id
             WHERE %(where_clause)s
          GROUP BY move.id, move.name, move.date, move.ref,
                   partner.name, partner.vat, partner.street, partner.city
          ORDER BY move.name
        """,
            column_group_key=column_group_key,
            debit_select=report_query.table.consolidation_debit,
            credit_select=report_query.table.consolidation_credit,
            from_clause=report_query.from_clause,
            where_clause=report_query.where_clause,
        ))

        results = self.env.execute_query_dict(SQL(" UNION ALL ").join(queries))
        lines_values = {}
        for res in results:
            move_id = res["move_id"]
            if move_id not in lines_values:
                lines_values[move_id] = res.copy()
            lines_values[move_id][res["column_group_key"]] = res

        lines = []
        for move_id, line_vals in lines_values.items():
            if limit_to_load and len(lines) >= limit_to_load:
                break
            lines.append(_get_move_line(report, options, move_id, line_vals, parent_id=line_dict_id))

        if limit_to_load and len(lines_values) > limit_to_load:
            lines.append(report._create_load_more_line(
                self.env["account.report.line"], line_dict_id, options, None,
                len(lines_values) - limit_to_load, self.LEVEL_MOVE, groupby,
                "_report_expand_unfoldable_line_l10n_ph_boa_cash_root", None
            ))
        return lines

    def _report_expand_unfoldable_line_l10n_ph_boa_cash_move(self, line_dict_id, groupby, options, unfold_all_batch_data=None, limit_to_load=None):
        def _get_aml_line(report, options, line_id, line_values, parent_id):
            report_line_id = report._get_generic_line_id("account.move.line", line_id, parent_line_id=parent_id)
            line_data = AccountReportLineData(
                id=report_line_id,
                parent_id=parent_id,
                name=line_values.get("line_name"),
                level=self.LEVEL_AML,
                caret_options="account.move.line",
                columns=self._build_custom_columns(report, options, line_values),
            )
            line_data.update_values(csv_data=line_values.get("csv_data"))
            return line_data

        report = self.env["account.report"].browse(options["report_id"])
        move_id = report._get_res_id_from_line_id(line_dict_id, "account.move")
        queries = []
        for column_group_key, column_group_options in report._split_options_per_column_group(options).items():
            report_query = report._get_report_query(column_group_options, "strict_range", self._get_options_domain(options))
            queries.append(SQL("""
                    SELECT %(column_group_key)s                          AS column_group_key,
                           account_move_line.id                          AS line_id,
                           account_move_line.name                        AS line_name,
                           account_move_line.date                        AS move_date,
                           move.name                                     AS move_name,
                           partner.name                                  AS partner_name,
                           partner.vat                                   AS partner_vat,
                           CONCAT_WS(', ', partner.street, partner.city) AS partner_address,
                           move.ref                                      AS reference,
                           %(account_code)s                              AS account_code,
                           %(account_name)s                              AS account_name,
                           %(debit_select)s                              AS debit,
                           %(credit_select)s                             AS credit
                      FROM %(from_clause)s
                      JOIN account_move move ON move.id = account_move_line.move_id
                 LEFT JOIN res_partner partner ON partner.id = move.partner_id
                 LEFT JOIN account_account account ON account.id = account_move_line.account_id
                     WHERE account_move_line.move_id = %(move_id)s
                       AND %(where_clause)s
                  ORDER BY account_move_line.name
            """,
                column_group_key=column_group_key,
                account_code=self.env["account.account"]._field_to_sql("account", "code", report_query),
                account_name=self.env["account.account"]._field_to_sql("account", "name", report_query),
                debit_select=report_query.table.consolidation_debit,
                credit_select=report_query.table.consolidation_credit,
                from_clause=report_query.from_clause,
                where_clause=report_query.where_clause,
                move_id=move_id
            ))

        results = self.env.execute_query_dict(SQL(" UNION ALL ").join(queries))
        lines_values = {}
        for res in results:
            lid = res["line_id"]
            if lid not in lines_values:
                lines_values[lid] = res.copy()
                lines_values[lid]["parent_id"] = line_dict_id
                lines_values[lid]["csv_data"] = res.copy()
            lines_values[lid][res["column_group_key"]] = res

        return [_get_aml_line(report, options, lid, lvals, parent_id=line_dict_id) for lid, lvals in lines_values.items()]

    def _get_csv_row_from_line(self, line, options):
        report = self.env["account.report"].browse(options["report_id"])
        _markup, model, _res_id = report._parse_line_id(line.id)[-1]

        if model != "account.move.line":
            return None

        # Extract the hidden CSV data from the dataclass's custom dictionary
        csv_data = line.get_custom().get("csv_data", {})
        cols = self._boa_map_cols(line, options)
        return [
            self._boa_clean(csv_data.get("move_name", "")),
            csv_data.get("move_date", ""),
            self._boa_get_str(cols, "account_code"),
            self._boa_get_str(cols, "account_name"),
            self._boa_clean(csv_data.get("partner_name", "")),
            csv_data.get("partner_vat", ""),
            self._boa_clean(csv_data.get("partner_address", "")),
            self._boa_clean(csv_data.get("reference", "")),
            self._boa_clean(line.name or ""),
            self._boa_get_amt(cols, "debit"),
            self._boa_get_amt(cols, "credit"),
        ]


class L10nPhBoaCashReceiptReportHandler(models.AbstractModel):
    _name = "l10n_ph.boa.cash.receipt.report.handler"
    _inherit = "l10n_ph.boa.cash.report.handler"
    _description = "Book of Accounts (Subsidiary) - Cash Receipts Custom Handler"

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options)
        options["ph_boa_book_type"] = "cash_receipts"


class L10nPhBoaCashDisbursementReportHandler(models.AbstractModel):
    _name = "l10n_ph.boa.cash.disbursement.report.handler"
    _inherit = "l10n_ph.boa.cash.report.handler"
    _description = "Book of Accounts (Subsidiary) - Cash Disbursements Custom Handler"

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options)
        options["ph_boa_book_type"] = "cash_disbursements"

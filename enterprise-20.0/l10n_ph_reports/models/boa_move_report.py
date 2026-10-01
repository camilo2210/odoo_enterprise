# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models
from odoo.exceptions import UserError
from odoo.fields import Domain
from odoo.tools import SQL, format_date
from odoo.addons.account_reports.utils.report_data_objects import AccountReportLineData


class L10nPhBoaMoveReportHandler(models.AbstractModel):
    _name = "l10n_ph.boa.move.report.handler"
    _inherit = ["l10n_ph.boa.report.handler", "l10n_ph.generic.report.handler"]
    _description = "Book of Accounts - Move-Based Handler"

    MONTH_LINE_LEVEL, DETAIL_LINE_LEVEL = 3, 5

    def _get_options_domain(self, options):
        domain = Domain.TRUE
        journal_type = options.get("journal_type")
        if journal_type == "sale":
            domain = Domain("move_id.move_type", "in", self.env["account.move"].get_sale_types(include_receipts=True))
        elif journal_type == "purchase":
            domain = Domain("move_id.move_type", "in", self.env["account.move"].get_purchase_types(include_receipts=True))

        return domain

    def _build_grand_total_line(self, report, options):
        # Disable tax-grid-based totals from the generic handler
        return None

    def _build_month_lines(self, report, options):
        lines, queries = [], []
        strict_domain = self._get_options_domain(options)
        for column_group_options in report._split_options_per_column_group(options).values():
            query = report._get_report_query(column_group_options, "strict_range", domain=strict_domain)
            queries.append(SQL("""
                   SELECT DISTINCT TO_CHAR(account_move_line.date, 'YYYY-MM')   AS month_key,
                                   DATE_TRUNC('month', account_move_line.date)  AS date_start
                              FROM %(table_references)s
                             WHERE %(search_condition)s
            """,
                table_references=query.from_clause,
                search_condition=query.where_clause,
            ))

        full_query = SQL("""
                      SELECT * FROM (%s) AS month_folders
                    ORDER BY date_start ASC
        """, SQL(" UNION ").join(queries))
        results = self.env.execute_query_dict(full_query)
        for res in results:
            month_key = res["month_key"]
            date_obj = res["date_start"]
            line_id = report._get_generic_line_id(None, None, markup=f"month_{month_key}")
            is_unfolded = options.get("unfold_all") or line_id in options.get("unfolded_lines", [])

            lines.append(AccountReportLineData(
                id=line_id,
                name=format_date(self.env, date_obj, date_format="MMMM yyyy"),
                level=self.MONTH_LINE_LEVEL,
                unfoldable=True,
                unfolded=is_unfolded,
                columns=[report._build_column_data(None, col) for col in options["columns"]],
                expand_function="_report_expand_unfoldable_line_l10n_ph_move",
            ))

        return lines

    def _report_expand_unfoldable_line_l10n_ph_move(self, line_id, groupby, options, unfold_all_batch_data=None, limit_to_load=None):
        """Expands the report line to show each AML.
        The SQL calculates the last 4 columns as follows:
        - gross_amount: The line's total price converted to company currency using an implied rate (balance / foreign_amount) to match the ledger.
        - discount_amount: Reverse-calculated from the discount percentage (since the DB only stores the %) and converted to company currency.
        - tax_amount: The total move tax re-distributed to lines based on weight, correcting for rounding differences that occur when splitting tax per line.
        - taxable_amount: The net balance of the line (company currency).
        """
        report = self.env["account.report"].browse(options["report_id"])
        markup = report._parse_line_id(line_id)[-1][0]
        target_month_key = markup.replace("month_", "")
        report.load_more_limit + 1 if report.load_more_limit and options["export_mode"] != "print" else None
        journal_type = options.get("journal_type")
        if journal_type == "sale":
            target_move_types = self.env["account.move"].get_sale_types(include_receipts=True)
        elif journal_type == "purchase":
            target_move_types = self.env["account.move"].get_purchase_types(include_receipts=True)
        else:
            raise UserError(self.env._("Unsupported journal_type: %s", journal_type))

        lines_values = {}
        for column_group_index, column_group_options in report._split_options_per_column_group(options).items():
            report_query = report._get_report_query(column_group_options, "strict_range")
            month_filter = SQL("TO_CHAR(account_move_line.date, 'YYYY-MM') = %s", target_month_key)

            query = SQL("""
                WITH raw_filtered_lines AS (
                     SELECT account_move_line.id                                   AS line_id,
                            account_move_line.move_id,
                            account_move_line.name                                 AS line_name,
                            account_move_line.price_subtotal                       AS foreign_taxable,
                            account_move_line.price_total                          AS foreign_gross,
                            account_move_line.discount,
                            -account_move_line.balance                             AS company_taxable,
                            %(column_group_index)s                                   AS column_group_index
                       FROM %(from_clause)s
                      WHERE %(where_clause)s
                        AND account_move_line.display_type = 'product'
                        AND %(month_filter)s
                ),
                target_moves AS (
                     SELECT DISTINCT move_id
                       FROM raw_filtered_lines
                ),
                actual_tax_per_type AS (
                     SELECT l.move_id,
                            l.tax_line_id                                          AS tax_id,
                            SUM(l.balance)                                         AS actual_tax_amt
                       FROM account_move_line l
                      WHERE l.move_id IN (SELECT move_id FROM target_moves)
                        AND l.display_type = 'tax'
                   GROUP BY l.move_id, l.tax_line_id
                ),
                base_per_type AS (
                     SELECT l.move_id,
                            tr.account_tax_id                                      AS tax_id,
                            SUM(l.price_subtotal)                                  AS total_base_amt
                       FROM account_move_line l
                       JOIN account_move_line_account_tax_rel tr ON tr.account_move_line_id = l.id
                      WHERE l.move_id IN (SELECT move_id FROM target_moves)
                        AND l.display_type = 'product'
                   GROUP BY l.move_id, tr.account_tax_id
                ),
                line_tax_weights AS (
                     SELECT l.id                                                   AS line_id,
                            l.move_id,
                            tr.account_tax_id                                      AS tax_id,
                            SUM(l.price_subtotal) OVER (
                                PARTITION BY l.move_id, tr.account_tax_id
                                    ORDER BY l.id
                            )                                                      AS running_base
                       FROM account_move_line l
                       JOIN account_move_line_account_tax_rel tr ON tr.account_move_line_id = l.id
                      WHERE l.move_id IN (SELECT move_id FROM target_moves)
                        AND l.display_type = 'product'
                ),
                distributed_taxes AS (
                     SELECT w.line_id,
                            COALESCE(
                                ROUND((w.running_base / NULLIF(b.total_base_amt, 0)) * a.actual_tax_amt, 2) -
                                COALESCE(
                                    LAG(ROUND((w.running_base / NULLIF(b.total_base_amt, 0)) * a.actual_tax_amt, 2))
                                    OVER (PARTITION BY w.move_id, w.tax_id ORDER BY w.line_id),
                                    0
                                ),
                                0
                            )                                                      AS allocated_tax
                       FROM line_tax_weights w
                       JOIN base_per_type b        ON b.move_id = w.move_id AND b.tax_id = w.tax_id
                       JOIN actual_tax_per_type a  ON a.move_id = w.move_id AND a.tax_id = w.tax_id
                ),
                final_line_tax AS (
                     SELECT line_id,
                            SUM(allocated_tax)                                     AS total_adjusted_tax
                       FROM distributed_taxes
                   GROUP BY line_id
                ),
                augmented_data AS (
                     SELECT rfl.*,
                            move.name                                              AS move_name,
                            move.invoice_date,
                            move.invoice_currency_rate,
                            move.move_type,
                            partner.vat,
                            partner.name                                           AS partner_name,
                            CONCAT_WS(', ', partner.street, partner.city)          AS partner_address,
                            -COALESCE(flt.total_adjusted_tax, 0)                   AS company_tax_adjusted,
                            CASE WHEN move.move_type IN ('out_refund', 'in_refund')
                                 THEN -1
                                 ELSE 1
                            END                                                    AS move_sign
                       FROM raw_filtered_lines rfl
                       JOIN account_move move      ON move.id = rfl.move_id
                  LEFT JOIN res_partner partner    ON partner.id = move.commercial_partner_id
                  LEFT JOIN final_line_tax flt     ON flt.line_id = rfl.line_id
                ),
                calculated_data AS (
                     SELECT augmented_data.*,
                            CASE WHEN foreign_taxable <> 0 AND company_taxable <> 0
                                 THEN ABS(company_taxable / foreign_taxable)
                                 WHEN invoice_currency_rate IS NOT NULL
                                 THEN invoice_currency_rate
                                 ELSE 1.0
                            END                                                    AS implied_rate,
                            CASE WHEN discount != 0 AND discount < 100
                                 THEN (foreign_taxable / (1 - (discount / 100.0))) - foreign_taxable
                                 ELSE 0.0
                            END                                                    AS foreign_discount_calc
                       FROM augmented_data
                )
                -- === MAIN SELECTION ===
                     SELECT line_id,
                            column_group_index,
                            move_name,
                            invoice_date,
                            vat                                                    AS partner_vat,
                            partner_name                                           AS register_name,
                            partner_address,
                            line_name                                              AS invoice_line,
                            (foreign_gross * implied_rate * move_sign)             AS gross_amount,
                            (foreign_discount_calc * implied_rate * move_sign)     AS discount_amount,
                            company_tax_adjusted                                   AS tax_amount,
                            company_taxable                                        AS taxable_amount
                       FROM calculated_data
                      WHERE move_type IN %(move_types)s
                   ORDER BY move_name, line_id
            """,
                column_group_index=column_group_index,
                from_clause=report_query.from_clause,
                where_clause=report_query.where_clause,
                month_filter=month_filter,
                move_types=tuple(target_move_types),
            )

            results = self.env.execute_query_dict(query)
            for res in results:
                key = res["line_id"]
                if key not in lines_values:
                    lines_values[key] = {
                        "move_name": res["move_name"],
                        "invoice_line": res["invoice_line"],
                    }
                lines_values[key][res["column_group_index"]] = res

        lines = []
        for aml_id, line_vals in lines_values.items():
            if limit_to_load and len(lines) >= limit_to_load:
                break
            child_id = report._get_generic_line_id("account.move.line", aml_id, parent_line_id=line_id)
            columns = []
            for col in options["columns"]:
                value = line_vals.get(col.get("column_group_index"), {}).get(col.get("expression_label"))
                if col.get("figure_type") in ("monetary", "float", "integer", "percentage") and value is None:
                    value = 0.0

                columns.append(report._build_column_data(
                    value,
                    col,
                    options=options,
                    currency=self.env.company.currency_id
                ))

            lines.append(AccountReportLineData(
                id=child_id,
                name=line_vals["move_name"],
                level=self.DETAIL_LINE_LEVEL,
                unfoldable=False,
                caret_options="account.move.line",
                parent_id=line_id,
                columns=columns,
            ))

        load_more_count = max(len(lines_values) - limit_to_load, 0) if limit_to_load else 0
        if load_more_count:
            lines.append(report._create_load_more_line(
                self.env["account.report.line"],  # little hack since we don't have a real report line here
                line_id,
                options,
                None,
                load_more_count,
                self.MONTH_LINE_LEVEL,
                groupby,
                "_report_expand_unfoldable_line_l10n_ph_move",
                None
            ))

        return lines

    # ================
    # .CSV file export
    # ================

    def _get_csv_row_from_line(self, line, options):
        report = self.env["account.report"].browse(options["report_id"])
        _markup, model, _res_id = report._parse_line_id(line.id)[-1]
        if model != "account.move.line":
            return None

        cols = self._boa_map_cols(line, options)
        return [
            self._boa_get_str(cols, "invoice_date"),
            self._boa_get_str(cols, "partner_vat"),
            self._boa_get_str(cols, "register_name"),
            self._boa_get_str(cols, "partner_address"),
            self._boa_get_str(cols, "invoice_line"),
            self._boa_get_amt(cols, "gross_amount"),
            self._boa_get_amt(cols, "discount_amount"),
            self._boa_get_amt(cols, "tax_amount"),
            self._boa_get_amt(cols, "taxable_amount"),
        ]

# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import models
from odoo.addons.account_reports.models.account_report import NUMBER_FIGURE_TYPES
from odoo.addons.account_reports.utils.report_data_objects import AccountReportLineData
from odoo.tools import SQL


class L10nPhBoaFalReportHandler(models.AbstractModel):
    _name = "l10n_ph.boa.fal.report.handler"
    _inherit = ["l10n_ph.boa.report.handler"]
    _description = "Fixed Asset Listing"

    LEVEL_ROOT, LEVEL_ASSET = 1, 3

    def _caret_options_initializer(self):
        return {
            "account_asset_line": [
                {"name": self.env._("Open Asset"), "action": "caret_option_open_record_form"},
            ]
        }

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options)
        options.setdefault("custom_display_config", {}).setdefault("components", {})["AccountReportFilters"] = "L10nPhBoaFalReportFilters"
        self._init_options_asset_groups(options, previous_options)
        self._init_options_asset_groups_names(options, previous_options)
        self._init_options_asset_status(options, previous_options)

    def _init_options_asset_status(self, options, previous_options):
        prev_states = {s["id"]: s.get("selected", False) for s in previous_options.get("asset_states", []) if "selected" in s}
        options["asset_states"] = [
            {"id": k, "name": l, "selected": prev_states.get(k, False)}
            for k, l in self.env["account.asset.variant"]._fields["state"]._description_selection(self.env)
        ]

    def _get_filter_asset_groups(self, options, additional_asset_groups_domain=None):
        return self.env["account.asset.group"].search([
            ("company_id", "in", self.env.companies.ids),
            *(additional_asset_groups_domain or []),
        ], order="company_id, name")

    def _init_options_asset_groups_names(self, options, previous_options, additional_asset_groups_domain=None):
        """Similar to _init_options_journals_names."""
        all_asset_groups = [
            m for m in options.get("asset_groups", [])
            if m.get("model") == "account.asset.group"
        ]
        asset_groups_selected = [m for m in all_asset_groups if m.get("selected")]
        if options.get("selected_asset_group_groups"):
            names_to_display = [options["selected_asset_group_groups"]["name"]]
        elif len(all_asset_groups) == len(asset_groups_selected) or not asset_groups_selected:
            names_to_display = [self.env._("All Asset Groups")]
        else:
            names_to_display = [m["name"] for m in asset_groups_selected]

        max_nb_displayed = 5
        nb_remaining = len(names_to_display) - max_nb_displayed
        displayed_names = ", ".join(names_to_display[:max_nb_displayed])

        if nb_remaining == 1:
            options["name_asset_groups_group"] = self.env._("%(names)s and one other", names=displayed_names)
        elif nb_remaining > 1:
            options["name_asset_groups_group"] = self.env._("%(names)s and %(remaining)s others", names=displayed_names, remaining=nb_remaining)
        else:
            options["name_asset_groups_group"] = displayed_names

    def _init_options_asset_groups(self, options, previous_options, additional_asset_groups_domain=None):
        """Similar to _init_options_journals_names."""
        def option_value(value, selected=False):
            return {
                "id": value.id,
                "model": value._name,
                "name": value.display_name,
                "selected": selected,
                "title": value.display_name,
                "visible": True,
            }

        previous_asset_groups = previous_options.get("asset_groups", [])
        all_asset_groups = self._get_filter_asset_groups(options, additional_asset_groups_domain=additional_asset_groups_domain)
        options["asset_groups"] = []
        # First time opening the report, and make sure it's not specifically stated that we should not reset the filter
        is_opening_report = previous_options.get("is_opening_report")  # key from JS controller when report is being opened

        # Handle asset models selection
        previous_selected_ids = {
            m["id"] for m in previous_asset_groups
            if m.get("model") == "account.asset.group" and m.get("selected")
        }

        company_asset_groups_map = defaultdict(list)
        asset_groups_selected = set()
        for asset_group in all_asset_groups:
            is_selected = asset_group.id in previous_selected_ids
            if is_selected:
                asset_groups_selected.add(asset_group.id)
            company_asset_groups_map[asset_group.company_id].append(option_value(asset_group, selected=is_selected))

        # Unselect all asset models if all are selected
        if asset_groups_selected == set(all_asset_groups.ids):
            for asset_groups in company_asset_groups_map.values():
                for m in asset_groups:
                    m["selected"] = False

        if not company_asset_groups_map:
            options["name_asset_groups_group"] = self.env._("No Asset Groups")
            return

        # Build asset model options
        if len(company_asset_groups_map) > 1:
            for company, asset_groups in company_asset_groups_map.items():
                company_name = company.sudo().display_name

                # if not is_opening_report, then gets the unfolded attribute of the company from the previous options
                unfolded = False if is_opening_report else next(
                    (entry.get("unfolded") for entry in previous_asset_groups
                     if entry.get("model") == "res.company" and entry.get("name") == company_name), False
                )
                for asset_group in asset_groups:
                    asset_group["visible"] = unfolded

                options["asset_groups"].append({
                    "id": "divider",
                    "model": "res.company",
                    "name": company_name,
                    "unfolded": unfolded,
                })
                options["asset_groups"] += asset_groups
        else:
            options["asset_groups"].extend(next(iter(company_asset_groups_map.values()), []))

    def _build_custom_columns(self, report, options, vals):
        """Deduplicate columns values across colgroups."""
        columns = []
        last_cg_key = len(cg) - 1 if (cg := options.get("column_groups")) else None
        for c in options["columns"]:
            current_key = c.get("column_group_index")
            if (current_key) != last_cg_key and c.get("expression_label") != "accumulated_depreciation":
                columns.append(report._build_column_data("", c, options=options))
                continue
            columns.append(report._build_column_data(
                (vals.get(current_key) or {}).get(c["expression_label"]) or (0.0 if c.get("figure_type") in NUMBER_FIGURE_TYPES else ""),
                c,
                options=options,
                currency=self.env.company.currency_id
            ))
        return columns

    def _get_fal_query_common(self, report, options, column_group_options):
        analytic_existence_sql = SQL("TRUE")
        if analytic_ids := [str(id) for id in column_group_options.get("analytic_accounts", [])]:
            analytic_existence_sql = SQL(
                "(depreciation.asset_variant_id IS NOT NULL OR %s && %s)",
                analytic_ids,
                self.env["account.asset"]._query_analytic_accounts("asset")
            )

        selected_states = [s["id"] for s in options.get("asset_states", []) if s.get("selected")]
        state_filter_sql = SQL("variant.state IN %s", tuple(selected_states)) if selected_states else SQL("TRUE")

        group_filter_sql = SQL("TRUE")
        asset_groups = options.get("asset_groups", [])

        # We must filter out dividers (id='divider') to find real IDs
        selected_group_ids = [
            m["id"] for m in asset_groups
            if m.get("model") == "account.asset.group" and m.get("selected") and m.get("id") != "divider"
        ]

        if selected_group_ids:
            group_filter_sql = SQL("asset.asset_group_id IN %s", tuple(selected_group_ids))

        report_query = report._get_report_query(column_group_options, "from_beginning")
        from_and_join_clause = SQL("""
                 FROM account_asset asset
                 JOIN account_asset_variant variant ON asset.main_variant_id = variant.id
            LEFT JOIN (
                SELECT sub.asset_variant_id,
                       SUM(sub.depreciation_value) AS balance
                  FROM (
                      SELECT DISTINCT move.id,
                                      move.asset_variant_id,
                                      move.depreciation_value
                                 FROM %(from_clause)s
                                 JOIN account_move move ON move.id = account_move_line.move_id
                                WHERE %(where_clause)s
                                  AND move.asset_move_type = 'depreciation'
                  ) sub
              GROUP BY sub.asset_variant_id
            ) depreciation ON depreciation.asset_variant_id = variant.id
            LEFT JOIN account_depreciation_model model ON variant.model_id = model.id
            LEFT JOIN account_asset_group asset_group ON asset.asset_group_id = asset_group.id
            LEFT JOIN account_account asset_account ON asset.account_asset_id = asset_account.id
            LEFT JOIN LATERAL (
                SELECT model.method_number * CAST(model.method_period AS INTEGER) AS total_months
            ) duration ON TRUE
        """,
            from_clause=report_query.from_clause,
            where_clause=report_query.where_clause
        )

        where_clause = SQL("""
             WHERE asset.company_id IN %(company_ids)s
               AND asset.acquisition_date <= %(date_to)s
               AND (
                   model.method_number <= 0
                   OR COALESCE(
                        variant.disposal_date,
                        asset.acquisition_date
                            + make_interval(
                                months => FLOOR(duration.total_months)::int,
                                days => ROUND((duration.total_months - FLOOR(duration.total_months)) * 30)::int - 1
                            )
                    ) >= %(date_from)s
               )
               AND %(state_filter_sql)s
               AND %(group_filter_sql)s
               AND (
                    %(analytic_existence_sql)s
                    OR depreciation.balance IS NOT NULL
                   )
        """,
            company_ids=tuple(self.env.companies.ids),
            date_from=column_group_options["date"]["date_from"],
            date_to=column_group_options["date"]["date_to"],
            state_filter_sql=state_filter_sql,
            group_filter_sql=group_filter_sql,
            analytic_existence_sql=analytic_existence_sql
        )

        return from_and_join_clause, where_clause

    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals=None, warnings=None):
        queries = []
        for column_group_key, column_group_options in report._split_options_per_column_group(options).items():
            from_join_sql, where_sql = self._get_fal_query_common(report, options, column_group_options)
            queries.append(SQL("""
                SELECT %(column_group_key)s                                                AS column_group_key,
                       COALESCE(SUM(asset.original_value), 0)                              AS purchase_price,
                       COALESCE(
                            SUM(depreciation.balance) +
                            SUM(variant.already_depreciated_amount_import)
                       ,0)                                                                 AS accumulated_depreciation,
                       COALESCE(SUM(variant.salvage_value), 0)                             AS residual_value,
                       COUNT(asset.id)                                                     AS asset_count
                  %(from_join_sql)s
                  %(where_sql)s
            """,
                column_group_key=column_group_key,
                from_join_sql=from_join_sql,
                where_sql=where_sql
            ))

        results = self.env.execute_query_dict(SQL(" UNION ALL ").join(queries))
        if all(res["asset_count"] == 0 for res in results):
            return []

        vals = {res["column_group_key"]: res for res in results}
        return [(0, AccountReportLineData(
            id=report._get_generic_line_id(None, None, markup="root"),
            name=self.env._("Fixed Asset Listing"),
            level=self.LEVEL_ROOT,
            unfoldable=False,
            unfolded=True,
            columns=self._build_custom_columns(report, options, vals),
            expand_function="_report_expand_unfoldable_line_l10n_ph_fal_root",
        ))]

    def _report_expand_unfoldable_line_l10n_ph_fal_root(self, line_dict_id, groupby, options, unfold_all_batch_data=None, limit_to_load=None):
        report = self.env["account.report"].browse(options["report_id"])
        queries = []
        for column_group_key, column_group_options in report._split_options_per_column_group(options).items():
            from_join_sql, where_sql = self._get_fal_query_common(report, options, column_group_options)
            queries.append(SQL("""
                SELECT %(column_group_key)s                                      AS column_group_key,
                       asset.id                                                  AS asset_id,
                       %(asset_name_sql)s                                        AS asset_name,
                       asset.acquisition_date                                    AS purchase_date,
                       asset.l10n_ph_fixed_asset_code                            AS fa_code,
                       %(asset_group_name_sql)s                                  AS asset_type,
                       model.method_number                                       AS useful_life_number,
                       model.method_period                                       AS useful_life_period,
                       variant.prorata_date                                      AS depreciation_start_date,
                       asset.original_value                                      AS purchase_price,
                       COALESCE(depreciation.balance, 0) +
                       variant.already_depreciated_amount_import                 AS accumulated_depreciation,
                       variant.salvage_value                                     AS residual_value,
                       %(account_code_sql)s                                      AS account_code,
                       %(account_name_sql)s                                      AS account_name
                  %(from_join_sql)s
                  %(where_sql)s
            """,
                column_group_key=column_group_key,
                asset_name_sql=self.env["account.asset"]._field_to_sql("asset", "name"),
                asset_group_name_sql=self.env["account.asset.group"]._field_to_sql("asset_group", "name"),
                account_code_sql=self.env["account.account"]._field_to_sql("asset_account", "code"),
                account_name_sql=self.env["account.account"]._field_to_sql("asset_account", "name"),
                from_join_sql=from_join_sql,
                where_sql=where_sql
            ))

        results = self.env.execute_query_dict(SQL("""
                      SELECT * FROM (%(union_query)s) AS all_assets
                    ORDER BY asset_name,
                             purchase_date,
                             asset_id
        """, union_query=SQL(" UNION ALL ").join(queries)))

        period_map = dict(self.env["account.asset.variant"]._fields["method_period"]._description_selection(self.env))
        lines_values = {}
        for res in results:
            res["useful_life"] = f"{round(res['useful_life_number'], 2):g} {period_map[res['useful_life_period']]}"
            lines_values.setdefault(res["asset_id"], {})[res["column_group_key"]] = res

        lines = []
        for asset_id, line_vals in lines_values.items():
            if limit_to_load and len(lines) >= limit_to_load:
                break

            lines.append(AccountReportLineData(
                id=report._get_generic_line_id("account.asset", asset_id, parent_line_id=line_dict_id),
                parent_id=line_dict_id,
                name=next(iter(line_vals.values()))["asset_name"],
                level=self.LEVEL_ASSET,
                caret_options="account_asset_line",
                columns=self._build_custom_columns(report, options, line_vals),
            ))

        load_more_count = max(len(lines_values) - limit_to_load, 0) if limit_to_load else 0
        if load_more_count > 0:
            lines.append(report._create_load_more_line(
                self.env["account.report.line"],  # little hack since we don't have a real report line here
                line_dict_id,
                options,
                None,
                load_more_count,
                self.LEVEL_ASSET,
                groupby,
                "_report_expand_unfoldable_line_l10n_ph_fal_root",
                None
            ))

        return lines

    # ================
    # .CSV file export
    # ================

    def _get_csv_row_from_line(self, line, options):
        if line.level != self.LEVEL_ASSET:
            return None

        cols = self._boa_map_cols(line, options)
        return [
            self._boa_clean(line.name),
            self._boa_get_str(cols, "fa_code"),
            self._boa_get_str(cols, "asset_type"),
            self._boa_get_str(cols, "purchase_date"),
            self._boa_get_amt(cols, "purchase_price"),
            self._boa_get_str(cols, "depreciation_start_date"),
            self._boa_get_amt(cols, "accumulated_depreciation"),
            self._boa_get_str(cols, "useful_life"),
            self._boa_get_amt(cols, "residual_value"),
        ]

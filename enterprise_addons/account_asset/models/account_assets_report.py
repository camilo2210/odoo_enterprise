# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, _
from odoo.tools import format_date, SQL

MAX_NAME_LENGTH = 50


class AccountAssetReportHandler(models.AbstractModel):
    _name = 'account.asset.report.handler'
    _inherit = ['account.report.custom.handler']
    _description = 'Assets Report Custom Handler'

    def _get_custom_groupby_map(self):
        def asset_label_builder(grouping_keys):
            key_to_label = {}
            assets = self.env['account.asset'].browse(grouping_keys)
            for asset in assets:
                key_to_label[asset.id] = asset.display_name
            return key_to_label

        def asset_group_label_builder(grouping_keys):
            asset_groups = self.env['account.asset.group'].browse(filter(None, grouping_keys))
            key_to_label = {ag.id: ag.name for ag in asset_groups}
            if None in grouping_keys:
                key_to_label[None] = _("(No Asset Group)")
            return key_to_label

        return {
            'asset_id': {
                'model': 'account.asset',
                'domain_builder': lambda _grouping_keys: [],
                'label_builder': asset_label_builder,
                'caret_builder': lambda _grouping_key: 'account_asset_line',
            },
            'asset_group_id': {
                'model': 'account.asset.group',
                'domain_builder': lambda grouping_keys: [],
                'label_builder': asset_group_label_builder,
            },
            'account_root': {
                'model': 'account.root',
                'domain_builder': lambda _grouping_keys: [],
                'label_builder': lambda grouping_keys: {root: root or _("(No Root)") for root in grouping_keys},
            },
        }

    def _caret_options_initializer(self):
        # Use 'caret_option_open_record_form' defined in account_reports rather than a custom function
        return {
            'account_asset_line': [
                {'name': _("Open Asset"), 'action': 'caret_option_open_record_form'},
            ]
        }

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        column_group_options_map = report._split_options_per_column_group(options)

        for col in options['columns']:
            column_group_options = column_group_options_map[col['column_group_index']]
            # Dynamic naming of columns containing dates
            if col['expression_label'] == 'balance':
                col['name'] = '' # The column label will be displayed in the subheader
            if col['expression_label'] in ['assets_date_from', 'depre_date_from']:
                col['name'] = format_date(self.env, column_group_options['date']['date_from'])
            elif col['expression_label'] in ['assets_date_to', 'depre_date_to']:
                col['name'] = format_date(self.env, column_group_options['date']['date_to'])

        options['custom_columns_subheaders'] = [
            {"name": _("Characteristics"), "colspan": 3},
            {"name": _("Assets"), "colspan": 4},
            {"name": _("Depreciation"), "colspan": 4},
            {"name": _("Book Value"), "colspan": 1}
        ]
        options['multi_currency'] = False

        # Remove the shadowing of the analytics done in the account report, as we handle it ourselves in the custom engine
        for col_group_data in options['column_groups']:
            if 'analytic_groupby_option' in col_group_data['forced_options']:
                col_group_data['forced_options']['analytic_groupby_option'] = False

    def _report_expand_unfoldable_line_with_groupby(self, line_dict_id, groupby, options, unfold_all_batch_data=None, limit_to_load=None):
        ''' This function is called when unfolding a line with groupby in the report. It gets the id of the line being unfolded from the report line id,
            and adds it to the options to pass it to the custom engine to be able to filter on it '''
        report = self.env['account.report'].browse(options['report_id'])
        grouping_key = report._get_model_info_from_id(line_dict_id)   # returns a tuple (model, field_value)
        options['depreciation_schedule_grouping_key'] = grouping_key
        return report._report_expand_unfoldable_line_with_groupby(
            line_dict_id, groupby, options, unfold_all_batch_data=unfold_all_batch_data, limit_to_load=limit_to_load
        )

    def _get_selected_ledgers(self, options):
        return [
            group
            for group in options.get('journal_groups', [])
            if group.get('selected') and group['id'] != 'local_gaap'
        ]

    def _report_engine_depreciation_schedule(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        report = self.env['account.report'].browse(options['report_id'])
        selected_ledgers = self._get_selected_ledgers(options)
        if current_groupby:
            report._check_groupby_fields([current_groupby])

        # We need sudo for correct results in case of record rules incompatible with the "AML shadowing"
        query = report.sudo()._get_report_query(options, date_scope)

        # Shadow fields as `account.move.line` fields to be able to use `_get_report_query`
        _stored_aml_fields, fields_to_insert = self.env['account.move.line']._prepare_aml_shadowing_for_report({
            'company_id': SQL.identifier('asset', 'company_id'),
            'journal_id': SQL.identifier('variant', 'journal_id'),
            'account_id': SQL.identifier('account_account', 'id'),
            'parent_state': 'posted',
            'display_type': 'product',
            'date': SQL('%(date_from)s::date', date_from=options['date']['date_from']),
            'analytic_distribution': SQL.identifier('asset', 'analytic_distribution'),
        }, prefix_fields=False)

        # Getting the grouping key from options to filter on it in the query
        # The grouping key is a tuple (model, field_value) where field_value can be None
        # The field_value is the id of the unfolded group in the report
        custom_grouping_model, custom_grouping_value = options.get('depreciation_schedule_grouping_key', (None, None))
        grouping_filter = None
        if custom_grouping_model == 'account.asset.group':
            grouping_filter = SQL('%s %s %s', SQL.identifier('asset_group_id'), SQL('=') if custom_grouping_value else SQL('is'), custom_grouping_value)
        elif custom_grouping_model == 'account.root':
            if custom_grouping_value is None:
                grouping_filter = SQL('%s %s %s', SQL.identifier('account_root'), SQL('is'), None)
            else:
                custom_grouping_value = str(custom_grouping_value).zfill(2)
                grouping_filter = SQL('%s %s %s', SQL.identifier('account_root'), SQL('='), custom_grouping_value)

        # Checking for analytics accounting
        analytic_account_ids = []
        if options.get('analytic_accounts_list'):
            analytic_account_ids += [str(account_id) for account_id in options.get('analytic_accounts_list')]
        analytics_where = SQL('%s && %s', analytic_account_ids, self.env['account.asset']._query_analytic_accounts('asset')) if analytic_account_ids else SQL('TRUE')
        analytics_distribution = SQL("""
            SELECT SUM(value::numeric) / 100.0
            FROM jsonb_each_text(%(analytic_distribution_col)s)
            WHERE key IN %(analytic_account_ids)s
            """,
            analytic_distribution_col=SQL.identifier('asset', 'analytic_distribution'),
            analytic_account_ids=tuple(analytic_account_ids),
        ) if analytic_account_ids else SQL('1')

        # Query condition to check if an asset is closed within the reporting period (includes rounding considerations)
        assets_closing_check = SQL("""
            variant_state = 'close'
            AND variant_disposal_date <= %(date_to)s
            AND ABS(ROUND(depre_date_to - (assets_date_to - variant_salvage_value), COALESCE(currency.decimal_places, 2))) < COALESCE(currency.rounding, 0.01)
            """, date_to=options['date']['date_to'])

        groupby_fields = SQL('%s,', SQL.identifier('account_move_line', current_groupby)) if current_groupby else SQL('')
        groupby_query = SQL('GROUP BY %s', SQL.identifier('account_move_line', current_groupby)) if current_groupby else SQL('')
        asset_fields_to_select = SQL('')
        asset_order_by = SQL('')

        # Special handling when grouping by asset to include additional asset details in the results
        if current_groupby == 'asset_id':
            asset_fields_to_select = SQL("""
                asset_acquisition_date AS asset_acquisition_date,
                asset_method AS asset_method,
                asset_method_number AS asset_method_number,
                asset_method_period AS asset_method_period,
                asset_method_progress_factor AS asset_method_progress_factor,
            """)
            # All those fields exist on the table called account_move_line because of the local shadowing we do below
            groupby_query = SQL("""
                GROUP BY
                    account_move_line.asset_id, account_move_line.account_code, account_move_line.asset_acquisition_date,
                    account_move_line.asset_method, account_move_line.asset_method_number, account_move_line.asset_method_period,
                    account_move_line.asset_method_progress_factor
                """)
            asset_order_by = SQL('ORDER BY account_move_line.account_code, account_move_line.asset_acquisition_date, account_move_line.asset_id')

        sql = SQL(
            """
                -- Filters variants and calculates accumulated depreciation totals (prior and current) within the specified reporting period.
                WITH variant_data AS (
                    SELECT
                        asset.id AS asset_id,
                        variant.id AS variant_id,
                        COALESCE(variant.parent_id, variant.id) AS parent_variant_id,
                        asset.currency_id AS asset_currency_id,
                        (asset.original_value * (%(analytics_distribution)s)) AS asset_original_value,
                        asset.acquisition_date AS asset_acquisition_date,
                        variant.state AS variant_state,
                        variant.model_id AS variant_model_id,
                        COALESCE(variant.salvage_value, 0) AS variant_salvage_value,
                        variant.disposal_date AS variant_disposal_date,
                        MIN(move.date) AS variant_date,
                        COALESCE(SUM(move.depreciation_value * (%(analytics_distribution)s)) FILTER (WHERE move.date < %(date_from)s), 0) + COALESCE(variant.already_depreciated_amount_import, 0) AS depreciated_before,
                        COALESCE(SUM(move.depreciation_value * (%(analytics_distribution)s)) FILTER (WHERE move.date BETWEEN %(date_from)s AND %(date_to)s), 0) AS depreciated_during,
                        COALESCE(SUM(move.depreciation_value * (%(analytics_distribution)s)) FILTER (WHERE move.date BETWEEN %(date_from)s AND %(date_to)s AND move.asset_number_days IS NULL), 0) AS variant_disposal_value
                    FROM account_asset AS asset
                        JOIN account_asset_variant AS variant
                            ON asset.id = variant.asset_id
                        LEFT JOIN account_move move
                            ON move.asset_variant_id = variant.id
                           AND (
                                CASE
                                    WHEN %(all_entries)s THEN move.state != 'cancel'
                                    ELSE move.state = 'posted'
                                END
                            )
                    WHERE asset.company_id in %(company_ids)s
                        AND (asset.acquisition_date <= %(date_to)s OR move.date <= %(date_to)s)
                        AND (variant.disposal_date >= %(date_from)s OR variant.disposal_date IS NULL)
                        AND (variant.state not in ('draft', 'cancelled') OR (variant.state = 'draft' AND %(all_entries)s))
                        AND asset.active IS TRUE
                        AND %(analytics_where)s
                    GROUP BY asset.id, variant.id
                ),
                -- Groups up child variants values into parent-level movements, calculating opening, accumulated, and closing balances for cost and depreciation.
                variants_grouped_by_parent AS (
                    SELECT
                        variant.parent_variant_id,
                        parent_variant.asset_currency_id,
                        parent_variant.asset_original_value,
                        parent_variant.variant_state,
                        parent_variant.variant_salvage_value,
                        parent_variant.variant_disposal_date,
                        parent_variant.variant_disposal_value,
                        SUM(CASE WHEN COALESCE(variant.asset_acquisition_date, variant.variant_date) < %(date_from)s
                                THEN variant.asset_original_value
                                ELSE 0.0
                            END) AS assets_date_from,
                        SUM(CASE WHEN COALESCE(variant.asset_acquisition_date, variant.variant_date) >= %(date_from)s
                                THEN variant.asset_original_value
                                ELSE 0.0
                            END) AS assets_plus,
                        0.0 AS assets_minus,
                        SUM(variant.asset_original_value) AS assets_date_to,
                        SUM(variant.depreciated_before) AS depre_date_from,
                        SUM(variant.depreciated_during) AS depre_plus,
                        0.0 AS depre_minus,
                        SUM(variant.depreciated_before + variant.depreciated_during) AS depre_date_to
                    FROM variant_data variant
                    JOIN variant_data parent_variant
                        ON parent_variant.variant_id = variant.parent_variant_id
                    GROUP BY
                            variant.parent_variant_id,
                            parent_variant.asset_currency_id,
                            parent_variant.asset_original_value,
                            parent_variant.variant_state,
                            parent_variant.variant_salvage_value,
                            parent_variant.variant_disposal_date,
                            parent_variant.variant_disposal_value
                ),
                -- Adjusts asset and depreciation values for variants that have been closed within the reporting period, accounting for disposals and ensuring a zero closing balance.
                closing_value_adjustments AS (
                    SELECT
                        parent_variant_id,
                        asset_original_value,
                        assets_date_from,
                        assets_plus,
                        (CASE WHEN %(assets_closing_check)s
                                THEN assets_minus + assets_date_to
                                ELSE assets_minus
                            END) AS assets_minus,
                        (CASE WHEN %(assets_closing_check)s
                                THEN 0.0
                                ELSE assets_date_to
                            END) AS assets_date_to,
                        depre_date_from,
                        (CASE WHEN %(assets_closing_check)s
                                THEN depre_plus - variant_disposal_value
                                ELSE depre_plus
                            END) AS depre_plus,
                        (CASE WHEN %(assets_closing_check)s
                                THEN depre_minus + depre_date_to - variant_disposal_value
                                ELSE depre_minus
                            END) AS depre_minus,
                        (CASE WHEN %(assets_closing_check)s
                                THEN 0.0
                                ELSE depre_date_to
                            END) AS depre_date_to
                    FROM variants_grouped_by_parent
                    LEFT JOIN res_currency currency
                        ON currency.id = asset_currency_id
                ),
                -- Retrieves detailed asset depreciation moves and model values, conditionally isolating main asset totals to prevent duplication during aggregation.
                final_adjustments AS (
                    SELECT %(fields_to_insert)s,
                        asset.id AS asset_id,
                        asset.asset_group_id AS asset_group_id,
                        asset.acquisition_date AS asset_acquisition_date,
                        asset.original_value < 0 AS asset_is_credit_note,
                        SUBSTRING(account_account.code_store->>asset.company_id::text, 1, 2) AS account_root,
                        %(account_code)s AS account_code,
                        %(account_name)s AS account_name,
                        CASE WHEN %(selected_ledger_count)s > 1 THEN NULL
                             WHEN %(selected_ledger_count)s = 1 THEN ledger_model.method
                             ELSE main_model.method END AS asset_method,
                        CASE WHEN %(selected_ledger_count)s > 1 THEN NULL
                             WHEN %(selected_ledger_count)s = 1 THEN ledger_model.method_number
                             ELSE main_model.method_number END AS asset_method_number,
                        CASE WHEN %(selected_ledger_count)s > 1 THEN NULL
                             WHEN %(selected_ledger_count)s = 1 THEN ledger_model.method_period
                             ELSE main_model.method_period END AS asset_method_period,
                        CASE WHEN %(selected_ledger_count)s > 1 THEN NULL
                             WHEN %(selected_ledger_count)s = 1 THEN ledger_model.method_progress_factor
                             ELSE main_model.method_progress_factor END AS asset_method_progress_factor,

                        -- "Main Asset Vals"
                        -- We use asset values values ONLY if this is the main variant
                        -- to be able to group by assets while not duplicating values
                        CASE WHEN variant.id = asset.main_variant_id
                            THEN variant_depre.asset_original_value
                            ELSE 0 END AS asset_original_value,
                        CASE WHEN variant.id = asset.main_variant_id
                            THEN variant_depre.assets_date_from
                            ELSE 0 END AS assets_date_from,
                        CASE WHEN variant.id = asset.main_variant_id
                            THEN variant_depre.assets_plus
                            ELSE 0 END AS assets_plus,
                        CASE WHEN variant.id = asset.main_variant_id
                            THEN variant_depre.assets_minus
                            ELSE 0 END AS assets_minus,
                        CASE WHEN variant.id = asset.main_variant_id
                            THEN variant_depre.assets_date_to
                            ELSE 0 END AS assets_date_to,

                        -- Standard Variant Depreciation
                        variant_depre.depre_date_from,
                        variant_depre.depre_plus,
                        variant_depre.depre_minus,
                        variant_depre.depre_date_to
                    FROM
                        closing_value_adjustments variant_depre
                    JOIN account_asset_variant variant
                        ON variant.id = variant_depre.parent_variant_id
                    JOIN account_asset AS asset
                        ON asset.id = variant.asset_id
                    JOIN account_asset_variant main_variant
                        ON asset.main_variant_id = main_variant.id
                    JOIN account_depreciation_model main_model
                        ON main_variant.model_id = main_model.id
                    -- The variant depreciating in the picked ledger, at most one per asset
                    LEFT JOIN (
                        SELECT DISTINCT ON (asset_id) asset_id, model_id
                        FROM account_asset_variant
                        WHERE journal_id IN %(selected_ledger_journal_ids)s
                        ORDER BY asset_id, id
                    ) ledger_variant
                        ON ledger_variant.asset_id = asset.id
                    LEFT JOIN account_depreciation_model ledger_model
                        ON ledger_model.id = ledger_variant.model_id
                    JOIN account_account
                        ON account_account.id = asset.account_asset_id
                )
                SELECT
                    %(groupby_fields)s
                    %(asset_fields_to_select)s
                    SUM(assets_date_from) AS assets_date_from,
                    SUM(CASE WHEN asset_is_credit_note THEN -1 * assets_minus ELSE assets_plus END) AS assets_plus,
                    SUM(CASE WHEN asset_is_credit_note THEN -1 * assets_plus ELSE assets_minus END) AS assets_minus,
                    SUM(assets_date_to) AS assets_date_to,
                    SUM(depre_date_from) AS depre_date_from,
                    SUM(CASE
                        WHEN asset_is_credit_note THEN -1 * depre_minus
                        WHEN depre_plus < 0 THEN 0.0
                        ELSE depre_plus
                        END) AS depre_plus,
                    SUM(CASE
                        WHEN asset_is_credit_note THEN -1 * depre_plus
                        WHEN depre_plus < 0 THEN -1 * depre_plus + depre_minus
                        ELSE depre_minus
                        END) AS depre_minus,
                    SUM(depre_date_to) AS depre_date_to,
                    SUM(assets_date_to) - SUM(depre_date_to) AS balance
                FROM final_adjustments AS %(table_references)s       -- local shadowing of account.move.line
                WHERE %(search_condition)s
                      %(grouping_filter)s
                %(groupby_query)s
                %(asset_order_by)s
            """,
            fields_to_insert=fields_to_insert,
            selected_ledger_count=len(selected_ledgers),
            selected_ledger_journal_ids=tuple(
                journal_id for ledger in selected_ledgers for journal_id in ledger['journals']
            ) or (0,),
            account_code=self.env['account.account']._field_to_sql('account_account', 'code'),
            account_name=self.env['account.account']._field_to_sql('account_account', 'name'),
            date_from=options['date']['date_from'],
            date_to=options['date']['date_to'],
            company_ids=tuple(self.env['account.report'].get_report_company_ids(options)),
            all_entries=options.get('all_entries', False),
            analytics_distribution=analytics_distribution,
            analytics_where=analytics_where,
            assets_closing_check=assets_closing_check,
            groupby_fields=groupby_fields,
            asset_fields_to_select=asset_fields_to_select or SQL(''),
            table_references=query.from_clause,
            search_condition=query.where_clause,
            grouping_filter=SQL("AND %s", grouping_filter) if grouping_filter else SQL(),
            groupby_query=groupby_query,
            asset_order_by=asset_order_by or SQL(''),
        )

        self.env.cr.execute(sql)
        query_results = self.env.cr.dictfetchall()

        if not current_groupby:
            # If no grouping is applied, we return the results directly
            return {next(iter(formulas_dict.values())): {
                'assets_date_from': None,
                'assets_plus': None,
                'assets_minus': None,
                'assets_date_to': None,
                'depre_date_from': None,
                'depre_plus': None,
                'depre_minus': None,
                'depre_date_to': None,
                'balance': None,
                'acquisition_date': None,
                'method': None,
                'duration_rate': None,
                'has_sublines': True,
                **(query_results[0] if query_results else {})
            }}

        # If grouping is applied, we need to format the results
        results = []
        for res in query_results:
            full_res = {
                'acquisition_date': None,
                'method': None,
                'duration_rate': None,
                'has_sublines': True,
                **res}
            if current_groupby == 'asset_id':
                asset_method = res['asset_method']
                full_res.update({
                    'acquisition_date': res['asset_acquisition_date'] and format_date(self.env, res['asset_acquisition_date']) or '',
                    'method': {
                        'linear': _("Linear"),
                        'degressive': _("Declining"),
                        'no_depreciation': _("No depreciation"),
                    }.get(asset_method, _("Dec. then Straight")) if asset_method else None,
                    'duration_rate': self._get_depreciation_rate(asset_method, res.get('asset_method_number'), res.get('asset_method_period'), res.get('asset_method_progress_factor')) if asset_method else None,
                    'has_sublines': True,
                })
            results.append((res[current_groupby], full_res))

        return {next(iter(formulas_dict.values())): results}

    def _get_depreciation_rate(self, asset_method, asset_method_number=None, asset_method_period=None, asset_method_progress_factor=None):
        """Compute the depreciation rate string"""
        match asset_method:
            case 'linear':
                rate = 100.0 / asset_method_number if asset_method_number else 0.0
                period_suffix = ' p.m.' if asset_method_period == '1' else ' p.a.'
            case 'degressive':
                rate = 100.0 * asset_method_progress_factor
                period_suffix = ' p.a.'
            case _:
                rate = 0.0
                period_suffix = ''
        return f'{rate:.2f} %{period_suffix}'


class AccountReport(models.Model):
    _inherit = 'account.report'

    def _get_caret_option_view_map(self):
        view_map = super()._get_caret_option_view_map()
        view_map['account.asset.line'] = 'account_asset.view_account_asset_expense_form'
        return view_map

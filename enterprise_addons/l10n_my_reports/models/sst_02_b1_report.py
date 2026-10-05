from collections import defaultdict

from odoo import models
from odoo.tools.sql import SQL
from odoo.addons.account_reports.utils.report_data_objects import AccountReportLineData


class L10n_MySST02B1ReportHandler(models.AbstractModel):
    _name = 'l10n_my.sst_02_b1.report.handler'
    _inherit = ['account.tax.report.handler']
    _description = 'SST-02 (B1) Tax Report Custom Handler'

    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals, warnings=None):
        report_lines = self._build_product_lines(report, options)
        if grand_total_line := self._build_grand_total_line(report, options):
            report_lines += grand_total_line

        # Inject sequences on the dynamic lines
        return [(0, line) for line in report_lines]

    def _get_line_columns(self, report, options, data):
        line_columns = []
        for column in options['columns']:
            col_group = data['column_groups'].get(column['column_group_index'])
            if col_group:
                col_val = col_group.get(column['expression_label'])
            else:
                col_val = None
            line_columns.append(report._build_column_data(
                col_val,
                column,
                options=options,
            ))
        return line_columns

    def _build_product_lines(self, report, options):
        domain = [('product_id', '!=', False)]
        queries = []

        for column_group_index, column_group_options in report._split_options_per_column_group(options).items():
            query = report._get_report_query(column_group_options, date_scope="strict_range", domain=domain)

            queries.append(SQL(
                """
                  SELECT %(column_group_index)s                                                           AS column_group_index,
                         pt.l10n_my_tax_classification_code                                             AS customs_code,
                         SUM(CASE WHEN %(account_tag_name)s = 'SST02_8'
                             THEN account_move_line.price_subtotal
                             ELSE 0
                         END)                                                                           AS value_goods_sold,
                         SUM(CASE WHEN %(account_tag_name)s = 'SST02_9'
                             THEN account_move_line.price_subtotal
                             ELSE 0
                         END)                                                                           AS value_goods_own_use,
                         SUM(CASE WHEN %(account_tag_name)s = 'SST02_10'
                             THEN account_move_line.price_subtotal
                             ELSE 0
                         END)                                                                           AS value_taxable_service
                    FROM %(table_references)s
                    JOIN product_product pp ON pp.id = account_move_line.product_id
                    JOIN product_template pt ON pt.id = pp.product_tmpl_id
                    JOIN account_account_tag_account_move_line_rel rel ON account_move_line.id = rel.account_move_line_id
                    JOIN account_account_tag tag ON rel.account_account_tag_id = tag.id
                   WHERE %(search_condition)s
                     AND %(account_tag_name)s IN ('SST02_8', 'SST02_9', 'SST02_10')
                GROUP BY pt.l10n_my_tax_classification_code
                """,
                table_references=query.from_clause,
                search_condition=query.where_clause,
                column_group_index=column_group_index,
                account_tag_name=self.env['account.account.tag'].with_context(lang='en_US')._field_to_sql('tag', 'name'),
            ))

        # Line without customs_code ("Unassigned" line) should appear at the bottom of the product lines
        combined_query = SQL(
            """
            SELECT * FROM (
                %(concat_queries)s
            ) AS t
            ORDER BY CASE WHEN t.customs_code IS NULL THEN 1 ELSE 0 END
            """,
            concat_queries=SQL(" UNION ALL ").join(queries),
        )
        self.env.cr.execute(combined_query)

        product_lines = defaultdict(lambda: {'column_groups': {}})
        for res in self.env.cr.dictfetchall():
            product_lines[res['customs_code']]['column_groups'][res['column_group_index']] = res

        unfold_all = options['export_mode'] == 'print' or options.get('unfold_all')
        result_lines = []
        for customs_code, line_data in product_lines.items():
            line_id = report._get_generic_line_id('', '', customs_code)
            result_lines.append(AccountReportLineData(
                id=line_id,
                # Product line without 'customs_code' is given a special name "Unassigned". This line is
                # for grouping child invoice lines with product that are not yet assigned 'customs_code'.
                # The rest of lines are given an ascending number sequence as their names.
                name=customs_code or self.env._("Unassigned"),
                unfoldable=True,
                unfolded=line_id in options['unfolded_lines'] or unfold_all,
                columns=self._get_line_columns(report, options, line_data),
                level=0,
                expand_function='_report_expand_unfoldable_line_l10n_my_expand_product',
            ))

        return result_lines

    def _report_expand_unfoldable_line_l10n_my_expand_product(self, line_dict_id, groupby, options, unfold_all_batch_data=None, limit_to_load=None):
        report = self.env['account.report'].browse(options['report_id'])
        parent_line_customs_code, _, _ = report._parse_line_id(line_dict_id, markup_as_string=True)[-1]
        domain = ['&', ('product_id', '!=', False), ('product_id.l10n_my_tax_classification_code', '=', parent_line_customs_code)]
        queries = []

        for column_group_index, column_group_options in report._split_options_per_column_group(options).items():
            query = report._get_report_query(column_group_options, date_scope="strict_range", domain=domain)

            queries.append(SQL(
                """
                  SELECT account_move_line.id                                                           AS move_line_id,
                         %(column_group_index)s                                                           AS column_group_index,
                         account_move_line__move_id.name                                                AS move_name,
                         %(product_name)s                                                               AS product_name,
                         pt.l10n_my_tax_classification_code                                             AS customs_code,
                         SUM(CASE WHEN REGEXP_REPLACE(%(account_tag_name)s, '^[+-]', '') = 'SST02_8'
                             THEN account_move_line.price_subtotal
                             ELSE 0
                         END)                                                                           AS value_goods_sold,
                         SUM(CASE WHEN REGEXP_REPLACE(%(account_tag_name)s, '^[+-]', '') = 'SST02_9'
                             THEN account_move_line.price_subtotal
                             ELSE 0
                         END)                                                                           AS value_goods_own_use,
                         SUM(CASE WHEN REGEXP_REPLACE(%(account_tag_name)s, '^[+-]', '') = 'SST02_10'
                             THEN account_move_line.price_subtotal
                             ELSE 0
                         END)                                                                           AS value_taxable_service
                    FROM %(table_references)s
                    JOIN product_product pp ON pp.id = account_move_line.product_id
                    JOIN product_template pt ON pt.id = pp.product_tmpl_id
                    JOIN account_account_tag_account_move_line_rel rel ON account_move_line.id = rel.account_move_line_id
                    JOIN account_account_tag tag ON rel.account_account_tag_id = tag.id
                   WHERE %(search_condition)s
                     AND REGEXP_REPLACE(%(account_tag_name)s, '^[+-]', '') IN ('SST02_8', 'SST02_9', 'SST02_10')
                GROUP BY account_move_line.id, account_move_line__move_id.name, pt.name, pt.l10n_my_tax_classification_code
                """,
                table_references=query.from_clause,
                search_condition=query.where_clause,
                column_group_index=column_group_index,
                product_name=self.env['product.template']._field_to_sql('pt', 'name'),
                account_tag_name=self.env['account.account.tag'].with_context(lang='en_US')._field_to_sql('tag', 'name'),
                parent_line_customs_code=parent_line_customs_code or None,
            ))

        # Paginate query if report has 'load_more_limit' set
        self.env.cr.execute(SQL(" UNION ALL ").join(queries))

        move_lines = {}
        for res in self.env.cr.dictfetchall():
            product_entry = move_lines.setdefault(res['move_line_id'], {
                'move_name': res['move_name'],
                'column_groups': {},
            })

            product_entry['column_groups'][res['column_group_index']] = res

        result_lines = []
        for move_line_id, move_line_data in move_lines.items():
            if limit_to_load and len(result_lines) >= limit_to_load:
                break

            line_id = report._get_generic_line_id('account.move.line', str(move_line_id), parent_line_id=line_dict_id)
            result_lines.append(AccountReportLineData(
                id=line_id,
                name=move_line_data['move_name'],
                unfoldable=False,
                unfolded=False,
                columns=self._get_line_columns(report, options, move_line_data),
                level=1,
            ))

        load_more_count = max(len(move_lines) - limit_to_load, 0) if limit_to_load else 0
        if load_more_count:
            result_lines.append(report._create_load_more_line(
                self.env['account.report.line'],  # little hack since we don't have a real report line here
                line_dict_id,
                options,
                None,
                load_more_count,
                1,
                groupby,
                '_report_expand_unfoldable_line_l10n_my_expand_product',
                None,
            ))

        return result_lines

    def _build_grand_total_line(self, report, options):
        domain = [('product_id', '!=', False)]
        queries = []

        for column_group_index, column_group_options in report._split_options_per_column_group(options).items():
            query = report._get_report_query(column_group_options, date_scope="strict_range", domain=domain)
            queries.append(SQL(
                """
                  SELECT %(column_group_index)s AS column_group_index,
                         SUM(CASE WHEN REGEXP_REPLACE(%(account_tag_name)s, '^[+-]', '') = 'SST02_8'
                             THEN account_move_line.price_subtotal
                             ELSE 0
                         END)                                                                           AS value_goods_sold,
                         SUM(CASE WHEN REGEXP_REPLACE(%(account_tag_name)s, '^[+-]', '') = 'SST02_9'
                             THEN account_move_line.price_subtotal
                             ELSE 0
                         END)                                                                           AS value_goods_own_use,
                         SUM(CASE WHEN REGEXP_REPLACE(%(account_tag_name)s, '^[+-]', '') = 'SST02_10'
                             THEN account_move_line.price_subtotal
                             ELSE 0
                         END)                                                                           AS value_taxable_service
                    FROM %(table_references)s
                    JOIN account_account_tag_account_move_line_rel rel ON account_move_line.id = rel.account_move_line_id
                    JOIN account_account_tag tag ON rel.account_account_tag_id = tag.id
                   WHERE %(search_condition)s
                GROUP BY column_group_index
                """,
                table_references=query.from_clause,
                search_condition=query.where_clause,
                column_group_index=column_group_index,
                account_tag_name=self.env['account.account.tag'].with_context(lang='en_US')._field_to_sql('tag', 'name'),
            ))
        self.env.cr.execute(SQL(" UNION ALL ").join(queries))
        res_lines = self.env.cr.dictfetchall()

        # Do not show total lines if the report is empty
        if not res_lines:
            return []

        total_line = {
            'column_groups': {},
        }
        net_total_line = {
            'column_groups': {},
        }
        for res in res_lines:
            total_line['column_groups'][res['column_group_index']] = res
            # Calculate net total and display the value on the rightmost column of the column group
            net_total_line['column_groups'][res['column_group_index']] = {
                'value_taxable_service': (res.get('value_goods_sold', 0) +
                                          res.get('value_goods_own_use', 0) +
                                          res.get('value_taxable_service', 0)),
            }

        return [
            AccountReportLineData(
                id=report._get_generic_line_id('', '', markup='total'),
                name=self.env._('Total'),
                unfoldable=False,
                unfolded=False,
                columns=self._get_line_columns(report, options, total_line),
                level=0,
            ),
            AccountReportLineData(
                id=report._get_generic_line_id('', '', markup='net_total'),
                name=self.env._('Net Total'),
                unfoldable=False,
                unfolded=False,
                columns=self._get_line_columns(report, options, net_total_line),
                level=0,
            ),
        ]

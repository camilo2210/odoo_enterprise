# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, fields, models
from odoo.tools import date_utils, SQL
from odoo.tools.misc import format_date
from odoo.addons.account_reports.utils.report_data_objects import AccountReportLineData


class L10n_VnTaxReportHandler(models.AbstractModel):
    _name = 'l10n_vn.tax.report.handler'
    _inherit = ['account.tax.report.handler']
    _description = 'Taxes Custom Handler'

    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals, warnings=None):
        report_lines = self._build_month_lines(report, options)

        if grand_total_line := self._build_grand_total_line(report, options):
            report_lines.append(grand_total_line)

        # Inject sequences on the dynamic lines
        return [(0, line) for line in report_lines]

    # First level, month rows
    def _build_month_lines(self, report, options):
        """ Fetches the months for which we have entries *that have tax grids* and build a report line for each of them. """
        month_lines = []
        queries = []

        # 1) Build the queries to get the months
        for column_group_index, column_group_options in report._split_options_per_column_group(options).items():
            domain = [('move_id.move_type', '=', options['move_type'])]
            query = report._get_report_query(column_group_options, date_scope="strict_range", domain=domain)
            # The joins are there to filter out months for which we would not have any lines in the report.
            queries.append(SQL(
                """
                  SELECT (date_trunc('month', account_move_line.date::date) + interval '1 month' - interval '1 day')::date AS taxable_month,
                         %(column_group_index)s                                                                              AS column_group_index
                    FROM %(table_references)s
                    JOIN account_account_tag_account_move_line_rel account_tag_rel ON account_tag_rel.account_move_line_id = account_move_line.id
                    JOIN account_account_tag account_tag ON account_tag.id = account_tag_rel.account_account_tag_id
                   WHERE %(search_condition)s
                GROUP BY taxable_month
                ORDER BY taxable_month DESC
                """,
                column_group_index=column_group_index,
                table_references=query.from_clause,
                search_condition=query.where_clause,
            ))

        self.env.cr.execute(SQL(" UNION ALL ").join(queries))

        # 2) Make the lines
        unfold_all = options['export_mode'] == 'print' or options.get('unfold_all')
        for res in self.env.cr.dictfetchall():
            line_id = report._get_generic_line_id('', '', markup=str(res['taxable_month']))
            month_lines.append(AccountReportLineData(
                id=line_id,
                name=format_date(self.env, res['taxable_month'], date_format='MMMM y'),
                unfoldable=True,
                unfolded=line_id in options['unfolded_lines'] or unfold_all,
                columns=[report._build_column_data(None, column) for column in options['columns']],
                level=0,
                expand_function='_report_expand_unfoldable_line_l10n_vn_expand_month',
            ))

        return month_lines

    # Second level, tax group rows
    def _report_expand_unfoldable_line_l10n_vn_expand_month(self, line_dict_id, groupby, options, unfold_all_batch_data=None, limit_to_load=None):
        """ Used to expand a month line and load the second level, being the tax groups lines. """
        report = self.env['account.report'].browse(options['report_id'])
        month = report._get_markup(line_dict_id)
        tax_group_lines_values = self._query_tax_groups(options, report, month)
        return self._get_report_expand_unfoldable_line_value(report, options, line_dict_id, tax_group_lines_values,
                                                             limit_to_load, 1, groupby, '_report_expand_unfoldable_line_l10n_vn_expand_month',
                                                             report_line_method=self._get_report_line_tax_group)

    def _query_tax_groups(self, options, report, month):
        """ Query the values for the tax group line.
        The tax group line will sum up the values for the different columns, while being filtered by the month only.
        """
        # Month is already set to the last day of the month.
        end_date = fields.Date.from_string(month)
        start_date = date_utils.start_of(end_date, 'month')
        queries = []
        for column_group_index, column_group_options in report._split_options_per_column_group(options).items():
            domain = [
                ('move_id.move_type', '=', options['move_type']),
                # Make sure to only fetch records that are in the parent's row month
                ('date', '>=', start_date),
                ('date', '<=', end_date),
            ]
            query = report._get_report_query(column_group_options, date_scope="strict_range", domain=domain)
            tag_t = query.table._sudo()._join('tax_tag_ids')
            queries.append(SQL(
                """
                  SELECT %(column_group_index)s AS column_group_index,
                         %(account_tag_name)s                                                                               AS tag_name,
                         SUM(account_move_line.tax_base_amount)                                                             AS tax_base_amount,
                         SUM(%(balance_select)s * CASE WHEN %(balance_negate)s THEN -1 ELSE 1 END)                          AS balance
                    FROM %(table_references)s
                   WHERE %(search_condition)s
                GROUP BY %(account_tag_name)s
                """,
                balance_select=query.table.consolidation_balance,
                column_group_index=column_group_index,
                account_tag_name=tag_t.name,
                balance_negate=tag_t.balance_negate,
                table_references=query.from_clause,
                search_condition=query.where_clause,
            ))

        self.env.cr.execute(SQL(" UNION ALL ").join(queries))
        return self._process_tax_group_lines(self.env.cr.dictfetchall(), options)

    def _process_tax_group_lines(self, data_dict, options):
        """ Taking in the values from the database, this will construct the column values by using the tax groups and
        tax grid mapping set in the option of each report section.
        """
        lines_values = {}
        for values in data_dict:
            for tax_group, tax_group_values in options['tax_groups'].items():
                if tax_group not in lines_values:
                    lines_values[tax_group] = {
                        'name': tax_group_values['name'],
                        values['column_group_index']: {
                            'column_group_index': values['column_group_index'],
                        }
                    }
                self._eval_report_grids_map(options, tax_group, values, column_values=lines_values[tax_group][values['column_group_index']])
        return lines_values

    def _get_report_line_tax_group(self, report, options, tax_group, line_values, parent_line_id):
        """ Format the given values to match the report line format. """
        line_columns = self._get_line_column(report, options, line_values)
        line_id = report._get_generic_line_id('', '', markup=tax_group, parent_line_id=parent_line_id)
        unfold_all = options['export_mode'] == 'print' or options.get('unfold_all')
        return AccountReportLineData(
            id=line_id,
            parent_id=parent_line_id,
            name=line_values['name'],
            unfoldable=True,
            unfolded=line_id in options['unfolded_lines'] or unfold_all,
            columns=line_columns,
            level=1,
            expand_function='_report_expand_unfoldable_line_l10n_vn_expand_tax_group',
        )

    def _report_expand_unfoldable_line_l10n_vn_expand_tax_group(self, line_dict_id, groupby, options, unfold_all_batch_data=None, limit_to_load=None):
        """ Used to expand a tax group line and load the third level, being the account moves lines. """
        report = self.env['account.report'].browse(options['report_id'])
        month = report._parse_line_id(line_dict_id)[1][0]
        tax_group = report._get_markup(line_dict_id)
        lines_values = self._query_moves(options, report, tax_group, month)
        return self._get_report_expand_unfoldable_line_value(report, options, line_dict_id, lines_values,
                                                             limit_to_load, 2, groupby, '_report_expand_unfoldable_line_l10n_vn_expand_tax_group',
                                                             report_line_method=self._get_report_line_move)

    def _query_moves(self, options, report, tax_group, month):
        """ Fetches the moves for a given month and returns a dictionary mapping partner ids to line values. """
        end_date = fields.Date.from_string(month)
        start_date = date_utils.start_of(end_date, 'month')
        tax_groups = [grid for grids in options['tax_groups'][tax_group]['report_grids_map'].values() for grid in grids]
        queries = []
        for column_group_index, column_group_options in report._split_options_per_column_group(options).items():
            domain = [
                ('move_id.move_type', '=', options['move_type']),
                # Make sure to only fetch records that are in the parent's row month
                ('date', '>=', start_date),
                ('date', '<=', end_date),
            ]
            query = report._get_report_query(column_group_options, date_scope="strict_range", domain=domain)
            tag_t = query.table._sudo()._join('tax_tag_ids')
            invoice_number_column = SQL('l10n_vn_e_invoice_number' if options['move_type'] == 'out_invoice' else 'payment_reference')
            queries.append(SQL(
                """
                  SELECT %(column_group_index)s                                                                               AS column_group_index,
                         partner.name                                                                                       AS partner_name,
                         partner.vat                                                                                        AS vat,
                         %(account_tag_name)s                                                                               AS tag_name,
                         account_move_line__move_id.id                                                                      AS move_id,
                         account_move_line__move_id.name                                                                    AS move_name,
                         account_move_line__move_id.ref                                                                     AS move_ref,
                         account_move_line__move_id.%(invoice_number_column)s                                               AS invoice_number,
                         account_move_line__move_id.invoice_date                                                            AS invoice_date,
                         SUM(%(balance_select)s * CASE WHEN %(balance_negate)s THEN -1 ELSE 1 END)                          AS balance
                    FROM %(table_references)s
                    JOIN res_partner partner ON partner.id = account_move_line.partner_id
                   WHERE %(search_condition)s
                     AND %(account_tag_name)s = ANY(%(tax_groups)s)
                GROUP BY partner.id, account_move_line__move_id.id, %(account_tag_name)s
                """,
                balance_select=query.table.consolidation_balance,
                column_group_index=column_group_index,
                account_tag_name=tag_t.name,
                balance_negate=tag_t.balance_negate,
                invoice_number_column=invoice_number_column,
                table_references=query.from_clause,
                search_condition=query.where_clause,
                tax_groups=tax_groups,
            ))

        self.env.cr.execute(SQL(" UNION ALL ").join(queries))
        return self._process_moves(self.env.cr.dictfetchall(), tax_group, options)

    def _process_moves(self, data_dict, tax_group, options):
        """ Process the data_dict and group the lines in four categories """
        lines_values = {}
        for values in data_dict:
            if values['move_id'] not in lines_values:
                lines_values[values['move_id']] = {
                    'name': values['move_name'],
                    values['column_group_index']: {
                        'column_group_index': values['column_group_index'],
                        'move_id': values['move_id'],
                        'move_name': values['move_name'],
                        'ref': values['move_ref'],
                        'invoice_number': values['invoice_number'],
                        'invoice_date': values['invoice_date'],
                        'partner_id': values['partner_name'],
                        'tax_id': values['vat'],
                    }
                }
            self._eval_report_grids_map(options, tax_group, values, column_values=lines_values[values['move_id']][values['column_group_index']])

        return self._filter_lines_with_values(options, tax_group, lines_values)

    def _get_report_line_move(self, report, options, move_id, line_values, parent_line_id):
        """ Format the given values to match the report line format. """
        report = self.env['account.report'].browse(options['report_id'])
        line_columns = self._get_line_column(report, options, line_values)
        line_id = report._get_generic_line_id('account.move', move_id, parent_line_id=parent_line_id)
        unfold_all = options['export_mode'] == 'print' or options.get('unfold_all')
        return AccountReportLineData(
            id=line_id,
            parent_id=parent_line_id,
            name=line_values['name'],
            unfoldable=True,
            unfolded=line_id in options['unfolded_lines'] or unfold_all,
            columns=line_columns,
            level=2,
            caret_options='account.move',
            expand_function='_report_expand_unfoldable_line_l10n_vn_expand_move',
        )

    def _report_expand_unfoldable_line_l10n_vn_expand_move(self, line_dict_id, groupby, options, unfold_all_batch_data=None, limit_to_load=None):
        """ Used to expand a move line and load the fourth level, being the account tax lines. """
        report = self.env['account.report'].browse(options['report_id'])
        month = report._parse_line_id(line_dict_id)[1][0]
        tax_group = report._parse_line_id(line_dict_id)[2][0]
        move_id = report._get_res_id_from_line_id(line_dict_id, 'account.move')
        lines_values = self._query_tax_lines(options, report, move_id, tax_group, month)
        return self._get_report_expand_unfoldable_line_value(report, options, line_dict_id, lines_values,
                                                             limit_to_load, 3, groupby, '_report_expand_unfoldable_line_l10n_vn_expand_move',
                                                             report_line_method=self._get_report_line_tax)

    def _query_tax_lines(self, options, report, move_id, tax_group, month):
        """ Query the values for the partner line.
        The move line will sum up the values for the different columns, while being filtered for the given month only.
        """
        end_date = fields.Date.from_string(month)
        start_date = date_utils.start_of(end_date, 'month')
        tax_groups = [grid for grids in options['tax_groups'][tax_group]['report_grids_map'].values() for grid in grids]
        queries = []
        for column_group_index, column_group_options in report._split_options_per_column_group(options).items():
            domain = [
                ('move_id.move_type', '=', options['move_type']),
                # Make sure to only fetch records that are in the parent's row month
                ('date', '>=', start_date),
                ('date', '<=', end_date),
                ('move_id', '=', move_id),
            ]
            query = report._get_report_query(column_group_options, date_scope="strict_range", domain=domain)
            tag_t = query.table._sudo()._join('tax_tag_ids')
            queries.append(SQL(
                """
                  SELECT %(column_group_index)s                                                                               AS column_group_index,
                         account_tax.id                                                                                     AS tax_id,
                         REGEXP_REPLACE(%(account_tax_description)s, '(<([^>]+)>)', '', 'g')                                AS tax_description,
                         %(account_tag_name)s                                                                               AS tag_name,
                         ABS(account_move_line.tax_base_amount)                                                             AS untaxed_amount,
                         SUM(%(balance_select)s * CASE WHEN %(balance_negate)s THEN -1 ELSE 1 END)                          AS balance
                    FROM %(table_references)s
                    JOIN account_tax account_tax ON account_tax.id = account_move_line.tax_line_id
                   WHERE %(search_condition)s
                     AND %(account_tag_name)s = ANY(%(tax_groups)s)
                GROUP BY %(account_tag_name)s, account_tax.id, account_move_line.id
                """,
                balance_select=query.table.consolidation_balance,
                column_group_index=column_group_index,
                account_tax_description=self.env['account.tax']._field_to_sql('account_tax', 'description', query),
                account_tag_name=tag_t.name,
                balance_negate=tag_t.balance_negate,
                table_references=query.from_clause,
                search_condition=query.where_clause,
                tax_groups=tax_groups,
            ))

        self.env.cr.execute(SQL(" UNION ALL ").join(queries))
        return self._process_tax_lines(self.env.cr.dictfetchall(), tax_group, options)

    def _process_tax_lines(self, data_dict, tax_group, options):
        """ Taking in the values from the database, this will construct the column values by using the tax grid mapping
        set in the option of each report section.
        """
        lines_values = {}
        for values in data_dict:
            if values['tax_id'] not in lines_values:
                lines_values[values['tax_id']] = {
                    'name': values['tax_description'],
                    values['column_group_index']: {
                        'column_group_index': values['column_group_index'],
                        # Because we group by tax line, we need to find the untaxed amount from the tax
                        'untaxed_amount': values['untaxed_amount'],
                    }
                }
            self._eval_report_grids_map(options, tax_group, values, column_values=lines_values[values['tax_id']][values['column_group_index']])

        return self._filter_lines_with_values(options, tax_group, lines_values)

    def _get_report_line_tax(self, report, options, tax_id, line_values, parent_line_id):
        """ Format the given values to match the report line format. """
        line_columns = self._get_line_column(report, options, line_values)
        line_id = report._get_generic_line_id('account.tax', tax_id, parent_line_id=parent_line_id)
        return AccountReportLineData(
            id=line_id,
            parent_id=parent_line_id,
            name=line_values['name'],
            unfoldable=False,
            unfolded=False,
            columns=line_columns,
            level=3,
            caret_options='account.tax',
        )

    def _build_grand_total_line(self, report, options):
        """ The grand total line is the sum of all values in the given reporting period. """
        queries = []
        for column_group_index, column_group_options in report._split_options_per_column_group(options).items():
            domain = [('move_id.move_type', '=', options['move_type'])]
            query = report._get_report_query(column_group_options, date_scope="strict_range", domain=domain)
            tag_t = query.table._sudo()._join('tax_tag_ids')
            queries.append(SQL(
                """
                  SELECT %(column_group_index)s                                                                               AS column_group_index,
                         %(account_tag_name)s                                                                               AS tag_name,
                         SUM(%(balance_select)s * CASE WHEN %(balance_negate)s THEN -1 ELSE 1 END)                          AS balance
                    FROM %(table_references)s
                   WHERE %(search_condition)s
                GROUP BY column_group_index, %(account_tag_name)s
                """,
                balance_select=query.table.consolidation_balance,
                column_group_index=column_group_index,
                account_tag_name=tag_t.name,
                balance_negate=tag_t.balance_negate,
                table_references=query.from_clause,
                search_condition=query.where_clause,
            ))
        self.env.cr.execute(SQL(" UNION ALL ").join(queries))
        results = self.env.cr.dictfetchall()
        return results and self._get_report_line_grand_total(report, options, self._process_grand_total_line(report, options, results))

    def _process_grand_total_line(self, report, options, data_dict):
        """ Taking in the values from the database, this will construct the column values by using the tax grid mapping
        set in the option of each report section.
        """
        lines_values = {}
        for values in data_dict:
            if values['column_group_index'] not in lines_values:
                lines_values[values['column_group_index']] = lines_values
            # Sum the balances on the right expression label.
            # We use a map of tax grids to do that easily
            for tax_group in options['tax_groups']:
                self._eval_report_grids_map(options, tax_group, values, column_values=lines_values[values['column_group_index']])
        return lines_values

    def _get_report_line_grand_total(self, report, options, data):
        """ Format the given values to match the report line format. """
        return AccountReportLineData(
            id=report._get_generic_line_id('', '', markup='grand_total'),
            name=_('Grand Total'),
            unfoldable=False,
            unfolded=False,
            columns=self._get_line_column(report, options, data),
            level=0,
        )

    def _get_report_expand_unfoldable_line_value(self, report, options, line_dict_id, lines_values, limit_to_load, level, groupby, expand_function_name, *, report_line_method):
        lines = []

        for line_key, line_values in lines_values.items():
            if limit_to_load and len(lines) >= limit_to_load:
                break

            new_line = report_line_method(report, options, line_key, line_values, parent_line_id=line_dict_id)
            lines.append(new_line)

        load_more_count = max(len(lines_values) - limit_to_load, 0) if limit_to_load else 0
        if load_more_count:
            lines.append(report._create_load_more_line(
                self.env['account.report.line'],  # little hack since we don't have a real report line here
                line_dict_id,
                options,
                None,
                load_more_count,
                level,
                groupby,
                expand_function_name,
                None,
            ))

        return lines

    def _get_line_column(self, report, options, data):
        line_columns = []
        for column in options['columns']:
            col_value = data[column['column_group_index']].get(column['expression_label'])
            line_columns.append(report._build_column_data(
                col_value or '',
                column,
                options=options,
            ))
        return line_columns

    def _eval_report_grids_map(self, options, tax_group, data, *, column_values):
        """ Evaluate the report grids map for the given tax group and lines values. """
        report_grids_map = options['tax_groups'][tax_group]['report_grids_map']
        for expression_label, grids in report_grids_map.items():
            if expression_label not in column_values:
                column_values[expression_label] = 0
            if data['tag_name'] in grids:  # In this report, we always sum, so it's easy
                column_values[expression_label] += data['balance']

    def _filter_lines_with_values(self, options, tax_group, lines_values, ignored_grids=[]):
        lines_with_values = {}
        report_grids_map = options['tax_groups'][tax_group]['report_grids_map']
        for line, value in lines_values.items():
            for column_group_index in range(len(options['column_groups'])):
                if any(value[column_group_index][grid] != 0 for grid in report_grids_map if grid not in ignored_grids):
                    lines_with_values[line] = value

        return lines_with_values


class L10n_VnSalesTaxReportHandler(models.AbstractModel):
    _name = 'l10n_vn.sales.tax.report.handler'
    _inherit = ['l10n_vn.tax.report.handler']
    _description = 'Taxes Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        options.update({
            'move_type': 'out_invoice',
            'tax_groups': {
                'tax_0': {
                    'name': _('VAT on sales of goods and services 0%'),
                    'report_grids_map': {
                        'untaxed_amount': [
                            self.env.ref("l10n_vn.form_01_gtgt_report_C_II_a_amount_untaxed").formula.lstrip('-'),
                        ],
                        'tax_amount': [],
                    },
                },
                'tax_5': {
                    'name': _('VAT on sales of goods and services 5%'),
                    'report_grids_map': {
                        'untaxed_amount': [
                            self.env.ref("l10n_vn.form_01_gtgt_report_C_II_b_amount_untaxed").formula.lstrip('-')
                        ],
                        'tax_amount': [
                            self.env.ref("l10n_vn.form_01_gtgt_report_C_II_b_balance").formula.lstrip('-')
                        ],
                    },
                },
                'tax_8': {
                    'name': _('VAT on sales of goods and services 8%'),
                    'report_grids_map': {
                        'untaxed_amount': [
                            self.env.ref("l10n_vn.form_01_gtgt_report_C_II_c_amount_untaxed_8").formula.lstrip('-')
                        ],
                        'tax_amount': [
                            self.env.ref("l10n_vn.form_01_gtgt_report_C_II_c_balance_8").formula.lstrip('-')
                        ],
                    },
                },
                'tax_10': {
                    'name': _('VAT on sales of goods and services 10%'),
                    'report_grids_map': {
                        'untaxed_amount': [
                            self.env.ref("l10n_vn.form_01_gtgt_report_C_II_c_amount_untaxed_10").formula.lstrip('-')
                        ],
                        'tax_amount': [
                            self.env.ref("l10n_vn.form_01_gtgt_report_C_II_c_balance_10").formula.lstrip('-')
                        ],
                    }
                },
                'tax_exempt': {
                    'name': _('VAT Exemption on sales of goods and services'),
                    'report_grids_map': {
                        'untaxed_amount': [
                            self.env.ref("l10n_vn.form_01_gtgt_report_C_II_1_amount_untaxed").formula.lstrip('-'),
                        ],
                        'tax_amount': [],
                    }
                },
            }
        })


class L10n_VnPurchaseTaxReportHandler(models.AbstractModel):
    _name = 'l10n_vn.purchase.tax.report.handler'
    _inherit = ['l10n_vn.tax.report.handler']
    _description = 'Taxes Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        options.update({
            'move_type': 'in_invoice',
            'tax_groups': {
                'tax_0': {
                    'name': _('VAT on purchase of goods and services 0%'),
                    'report_grids_map': {
                        'untaxed_amount': [
                            self.env.ref("l10n_vn.form_01_gtgt_report_C_I_1_amount_untaxed_0").formula.lstrip('-'),
                            self.env.ref("l10n_vn.form_01_gtgt_report_C_I_a_amount_untaxed_0").formula.lstrip('-'),
                        ],
                        'tax_amount': [],
                    },
                },
                'tax_5': {
                    'name': _('VAT on purchase of goods and services 5%'),
                    'report_grids_map': {
                        'untaxed_amount': [
                            self.env.ref("l10n_vn.form_01_gtgt_report_C_I_1_amount_untaxed_5").formula.lstrip('-'),
                            self.env.ref("l10n_vn.form_01_gtgt_report_C_I_a_amount_untaxed_5").formula.lstrip('-')
                        ],
                        'tax_amount': [
                            self.env.ref("l10n_vn.form_01_gtgt_report_C_I_1_balance_5").formula.lstrip('-'),
                            self.env.ref("l10n_vn.form_01_gtgt_report_C_I_a_balance_5").formula.lstrip('-')
                        ],
                    },
                },
                'tax_8': {
                    'name': _('VAT on purchase of goods and services 8%'),
                    'report_grids_map': {
                        'untaxed_amount': [
                            self.env.ref("l10n_vn.form_01_gtgt_report_C_I_1_amount_untaxed_8").formula.lstrip('-'),
                            self.env.ref("l10n_vn.form_01_gtgt_report_C_I_a_amount_untaxed_8").formula.lstrip('-')
                        ],
                        'tax_amount': [
                            self.env.ref("l10n_vn.form_01_gtgt_report_C_I_1_balance_8").formula.lstrip('-'),
                            self.env.ref("l10n_vn.form_01_gtgt_report_C_I_a_balance_8").formula.lstrip('-')
                        ],
                    },
                },
                'tax_10': {
                    'name': _('VAT on purchase of goods and services 10%'),
                    'report_grids_map': {
                        'untaxed_amount': [
                            self.env.ref("l10n_vn.form_01_gtgt_report_C_I_1_amount_untaxed_10").formula.lstrip('-'),
                            self.env.ref("l10n_vn.form_01_gtgt_report_C_I_a_amount_untaxed_10").formula.lstrip('-')
                        ],
                        'tax_amount': [
                            self.env.ref("l10n_vn.form_01_gtgt_report_C_I_1_balance_10").formula.lstrip('-'),
                            self.env.ref("l10n_vn.form_01_gtgt_report_C_I_a_balance_10").formula.lstrip('-')
                        ],
                    },
                },
                'tax_exempt': {
                    'name': _('VAT on Purchase of Goods and Services Tax Exempt'),
                    'report_grids_map': {
                        'untaxed_amount': [
                            self.env.ref("l10n_vn.form_01_gtgt_report_C_I_1_amount_untaxed_exempt").formula.lstrip('-')
                        ],
                        'tax_amount': [],
                    }
                },
            }
        })

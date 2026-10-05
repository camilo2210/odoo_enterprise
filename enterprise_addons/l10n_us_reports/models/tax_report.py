from odoo import models
from odoo.fields import Domain
from odoo.tools import SQL
from odoo.addons.account_reports.utils.report_data_objects import AccountReportLineData


class L10nUSTaxreportHandler(models.AbstractModel):
    _name = 'l10n_us.tax.report.handler'
    _inherit = 'account.generic.tax.report.handler'
    _description = "US Tax Report Custom Handler"

    JURISDICTION_ORDER = {'state': 0, 'county': 1, 'city': 2, 'special': 3}

    def _custom_options_initializer(self, report, options, previous_options=None):
        super()._custom_options_initializer(report, options, previous_options=previous_options)

        # Restrict the content of the generic tax report to US taxes only
        options.setdefault('forced_domain', []).extend([
            '|',
            ('tax_ids.country_id', 'in', report.country_id.ids),
            ('tax_line_id.country_id', 'in', report.country_id.ids),
        ])

    def _l10n_us_reports_get_type_tax_use_selection(self):
        """ Return the [(value, label)] of 'type_tax_use', in selection order. """
        return self.env['account.tax']._fields['type_tax_use']._description_selection(self.env)

    def _l10n_us_reports_get_taxes_domain(self, report):
        """ Return the domain of the US taxes shown on the report. """
        return Domain([
            ('country_id', 'in', report.country_id.ids),
            ('type_tax_use', 'in', ('sale', 'purchase')),
            ('l10n_us_exempt_parent_tax_id', '=', False),
            ('l10n_us_nontaxable_parent_tax_id', '=', False),
        ])

    def _l10n_us_reports_get_rows(self, report):
        """ Group US taxes into report rows by state.

        :return: {type_tax_use: {res.country.state: [account.tax rows]}}
        """
        rows = {}
        if taxes := self.env['account.tax'].with_context(active_test=False).search(
            self._l10n_us_reports_get_taxes_domain(report)):
            type_tax_use_order = {
                value: index
                for index, (value, _label) in enumerate(self._l10n_us_reports_get_type_tax_use_selection())
            }
            taxes = taxes.sorted(key=lambda t: (
                type_tax_use_order.get(t.type_tax_use, 99),
                not t.l10n_us_state_id,
                t.l10n_us_state_id.name or '',
                self.JURISDICTION_ORDER.get(t.l10n_us_jurisdiction_type, 99),
                t.sequence,
                t.id,
            ))
            rows = {
                type_tax_use: type_taxes.grouped('l10n_us_state_id')
                for type_tax_use, type_taxes in taxes.grouped('type_tax_use').items()
            }
        return rows

    def _l10n_us_reports_categorize_taxes(self, taxes):
        """ Return the taxes according to its type.
        A reduced rate tax is split into its own category because
        its base needs to be reported as taxable and its
        tax amount on the parent's row. """
        exempt_taxes = taxes.l10n_us_exempt_tax_ids
        nontaxable_taxes = taxes.l10n_us_nontaxable_tax_ids
        reduced_taxes = (exempt_taxes | nontaxable_taxes).filtered('amount')
        return exempt_taxes - reduced_taxes, nontaxable_taxes - reduced_taxes, reduced_taxes

    def _l10n_us_reports_get_base_lines_domain(self, taxes):
        groups = self.env['account.tax'].with_context(active_test=False).search([('children_tax_ids', 'in', taxes.ids)])
        return Domain([('tax_ids', 'in', (taxes | groups).ids), ('tax_line_id', '=', False)])

    def _l10n_us_reports_sum_base_lines(self, base_amounts, taxes):
        """ Return the sum of the base lines levied by any of 'taxes'.
        A line taxed by several, such as by the state and the city,
        is only counted once. """
        tax_ids = set(taxes.ids)
        return sum(balance for line_taxes, balance in base_amounts.items() if tax_ids & line_taxes)

    def _l10n_us_reports_get_row_values(self, taxes, type_tax_use, options, amounts):
        exempt_taxes, nontaxable_taxes, reduced_taxes = self._l10n_us_reports_categorize_taxes(taxes)
        taxable_taxes = taxes | reduced_taxes
        sign = -1 if type_tax_use == 'sale' else 1
        values = {}
        for column_group_index in {column['column_group_index'] for column in options['columns']}:
            base = amounts[column_group_index]['base']
            tax_amounts = amounts[column_group_index]['tax']
            values[column_group_index] = {
                'net': sign * self._l10n_us_reports_sum_base_lines(base, taxable_taxes | exempt_taxes | nontaxable_taxes),
                'exempt': sign * self._l10n_us_reports_sum_base_lines(base, exempt_taxes),
                'non_taxable': sign * self._l10n_us_reports_sum_base_lines(base, nontaxable_taxes),
                'taxable': sign * self._l10n_us_reports_sum_base_lines(base, taxable_taxes),
                'tax': sign * sum(tax_amounts.get(tax.id, 0.0) for tax in taxable_taxes),
                'rate': taxes.amount if len(taxes) == 1 else None,  # a total spans several rates
            }
        return values

    def _l10n_us_reports_compute_tax_amounts(self, report, options):
        """
        Return the summed tax details per column group. A cash basis tax is left out
        until its cash basis entry makes it exigible.
        - 'base': base amounts, keyed by the set of taxes the line is levied by, so that the
          totals can count a line taxed by several jurisdictions only once;
        - 'tax': tax amounts (keyed by the tax they are due for).

        :return: {column_group_index: {'base': {frozenset(tax ids): balance}, 'tax': {tax_id: balance}}}
        """
        amounts = {}
        for column_group_index, cg_options in report._split_options_per_column_group(options).items():
            query = report._get_report_query(cg_options, 'strict_range')
            tax_details = self.env['account.move.line']._get_query_tax_details(query)

            self.env.cr.execute(SQL(
                '''
                SELECT base_line.tax_ids, SUM(base_line.base_amount) AS balance
                FROM (
                    SELECT ARRAY_AGG(DISTINCT tdr.tax_id) AS tax_ids,
                           MAX(tdr.base_amount) AS base_amount
                    FROM (%(tax_details)s) AS tdr
                    WHERE tdr.tax_exigible
                    GROUP BY tdr.base_line_id
                ) base_line
                GROUP BY base_line.tax_ids
                ''',
                tax_details=tax_details,
            ))
            base = {frozenset(tax_ids): balance for tax_ids, balance in self.env.cr.fetchall()}

            self.env.cr.execute(SQL(
                '''
                SELECT tdr.tax_id, SUM(tdr.tax_amount) AS balance
                FROM (%(tax_details)s) AS tdr
                WHERE tdr.tax_exigible
                GROUP BY tdr.tax_id
                ''',
                tax_details=tax_details,
            ))
            tax = dict(self.env.cr.fetchall())

            amounts[column_group_index] = {'base': base, 'tax': tax}
        return amounts

    def _l10n_us_reports_build_column(self, report, options, column, values):
        """ Build the column data of the taxes. """
        label = column['expression_label']
        value = values[column['column_group_index']].get(label)
        if label == 'rate':
            return report._build_column_data(value if value is not None else '', column, options=options, digits=4)
        cell = report._build_column_data(value if value is not None else '', column, options=options)
        cell.auditable = value is not None
        return cell

    def _l10n_us_reports_build_total_column(self, report, options, column, values):
        """ Build the total column of the headers (e.g., type of tax use, state). """
        if column['expression_label'] == 'rate':
            return report._build_column_data('', column, options=options)
        value = values[column['column_group_index']].get(column['expression_label'])
        return report._build_column_data(value if value is not None else '', column, options=options)

    def _l10n_us_reports_build_tax_line(self, report, options, parent_line_id, tax, type_tax_use, amounts):
        """ Return the report line for the tax."""
        values = self._l10n_us_reports_get_row_values(tax, type_tax_use, options, amounts)
        if not any(values[idx].get(label) for idx in values for label in ('net', 'exempt', 'non_taxable', 'taxable', 'tax')):
            return None
        return AccountReportLineData(
            id=report._get_generic_line_id('account.tax', tax.id, parent_line_id=parent_line_id),
            name=tax.name,
            level=3,
            parent_id=parent_line_id,
            columns=[self._l10n_us_reports_build_column(report, options, column, values) for column in options['columns']],
            unfoldable=False,
        )

    def _l10n_us_reports_build_state_lines(self, report, options, parent_line_id, state, taxes, type_tax_use, amounts):
        """ Return the report lines of the taxes specific to the state or without a state. """
        line_id = report._get_generic_line_id('res.country.state', state.id or None, parent_line_id=parent_line_id)
        tax_lines = [
            line
            for tax in taxes
            if (line := self._l10n_us_reports_build_tax_line(report, options, line_id, tax, type_tax_use, amounts))
        ]
        if not tax_lines:
            return []
        values = self._l10n_us_reports_get_row_values(taxes, type_tax_use, options, amounts)
        return [
            AccountReportLineData(
                id=line_id, name=state.name or self.env._("Undefined"), level=2, parent_id=parent_line_id,
                columns=[self._l10n_us_reports_build_total_column(report, options, column, values) for column in options['columns']],
                unfoldable=True,
                unfolded=line_id in options['unfolded_lines'] or options['unfold_all'],
            ),
            *tax_lines,
        ]

    def _l10n_us_reports_build_type_tax_use_lines(self, report, options, type_tax_use, states, amounts):
        """ Return the report lines of the taxes grouped by its state specific to the type tax use. """
        line_id = report._get_generic_line_id(None, None, markup=type_tax_use)
        type_taxes = self.env['account.tax']
        state_lines = []
        for state, taxes in states.items():
            if lines := self._l10n_us_reports_build_state_lines(report, options, line_id, state, taxes, type_tax_use, amounts):
                type_taxes |= taxes
                state_lines.extend(lines)

        if not state_lines:
            return []
        labels = dict(self._l10n_us_reports_get_type_tax_use_selection())
        values = self._l10n_us_reports_get_row_values(type_taxes, type_tax_use, options, amounts)
        return [
            AccountReportLineData(
                id=line_id, name=labels.get(type_tax_use, type_tax_use), level=0,
                columns=[self._l10n_us_reports_build_total_column(report, options, column, values) for column in options['columns']],
                unfoldable=False,
            ),
            *state_lines,
        ]

    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals, warnings=None):
        amounts = self._l10n_us_reports_compute_tax_amounts(report, options)
        return [
            (0, line)
            for type_tax_use, states in self._l10n_us_reports_get_rows(report).items()
            for line in self._l10n_us_reports_build_type_tax_use_lines(report, options, type_tax_use, states, amounts)
        ]

    def action_audit_cell(self, options, params):
        report = self.env['account.report'].browse(options['report_id'])
        model, tax_id = report._get_model_info_from_id(params['calling_line_dict_id'])
        if model != 'account.tax':
            return report.action_audit_cell(options, params)

        tax = self.env['account.tax'].browse(tax_id)
        exempt_taxes, nontaxable_taxes, reduced_taxes = self._l10n_us_reports_categorize_taxes(tax)

        label = params['expression_label']
        if label == 'tax':
            column_domain = Domain([('tax_line_id', 'in', (tax | reduced_taxes).ids)])
        elif label == 'exempt':
            column_domain = self._l10n_us_reports_get_base_lines_domain(exempt_taxes)
        elif label == 'non_taxable':
            column_domain = self._l10n_us_reports_get_base_lines_domain(nontaxable_taxes)
        elif label == 'taxable':
            column_domain = self._l10n_us_reports_get_base_lines_domain(tax | reduced_taxes)
        else:
            column_domain = self._l10n_us_reports_get_base_lines_domain(tax | exempt_taxes | nontaxable_taxes | reduced_taxes)

        cg_options = report._get_column_group_options(options, params['column_group_index'])
        domain = Domain(report._get_options_domain(cg_options, 'strict_range')) & column_domain
        return {
            'name': self.env._("Journal Items"),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move.line',
            'view_mode': 'list',
            'views': [(False, 'list')],
            'domain': domain,
            'context': {'active_test': False},
        }

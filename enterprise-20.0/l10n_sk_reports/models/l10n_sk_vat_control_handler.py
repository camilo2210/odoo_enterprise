from collections import defaultdict
from lxml import etree

from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools import date_utils
from odoo.tools import SQL
from odoo.tools.float_utils import float_repr
from odoo.tools.xml_utils import cleanup_xml_node

from odoo.addons.account_reports.utils.report_data_objects import AccountReportLineChatterData

# Used by _build_sql_query to conditionally include SQL fragments.
# ruff: noqa: E241
SECTION_PROFILES = {
    'a1':  {'has_tax_rate': True,  'has_goods': False, 'has_quantity': True,  'is_correction': False},
    'a2':  {'has_tax_rate': False, 'has_goods': True,  'has_quantity': True,  'is_correction': False},
    'b1':  {'has_tax_rate': True,  'has_goods': False, 'has_quantity': False, 'is_correction': False},
    'b2':  {'has_tax_rate': True,  'has_goods': False, 'has_quantity': False, 'is_correction': False},
    'b31': {'has_tax_rate': False, 'has_goods': False, 'has_quantity': False, 'is_correction': False},
    'b32': {'has_tax_rate': False, 'has_goods': False, 'has_quantity': False, 'is_correction': False},
    'c1':  {'has_tax_rate': True,  'has_goods': True,  'has_quantity': True,  'is_correction': True},
    'c2':  {'has_tax_rate': True,  'has_goods': False, 'has_quantity': True,  'is_correction': True},
}


class SlovakVATControlReportCustomHandler(models.AbstractModel):
    """
        Generate the VAT Control Statement for Slovakia.
        Reference: https://www.financnasprava.sk/sk/podnikatelia/dane/dan-z-pridanej-hodnoty/kontrolny-vykaz-dph
    """
    _name = 'l10n_sk.vat.control.report.handler'
    _inherit = 'account.tax.report.handler'
    _description = 'Slovak Report Custom Handler (Control Statement)'

    def _custom_options_initializer(self, report, options, previous_options=None):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        options['ignore_totals_below_sections'] = True

        options.setdefault('buttons', []).append({
            'name': self.env._('XML'),
            'sequence': 30,
            'action': 'export_file',
            'action_param': 'l10n_sk_export_vat_control_report_to_xml',
            'file_export_type': self.env._('XML'),
        })

    def _get_custom_groupby_map(self):
        return {
            'tax_rate': {
                'model': None,
                'domain_builder': lambda grouping_key: [],
                'label_builder': lambda keys: {
                    key: f"{int(key)}%" if key else self.env._("No Tax") for key in keys
                },
            },
            'sk_product_tag': {
                'model': None,
                'domain_builder': lambda grouping_key: [],
                'label_builder': self._get_sk_product_tag_labels,
            },
        }

    def _custom_groupby_line_completer(self, report, options, line_data, current_groupby):
        if current_groupby == 'move_id':
            line_data.caret_options = 'account.move'
            record_id = report._get_model_info_from_id(line_data.id)[1]
            line_data.chatter = AccountReportLineChatterData(model='account.move', id=record_id)

    ####################################################
    # CUSTOM ENGINES
    ####################################################

    def _report_engine_control_statement_A1(self, options, date_scope, formulas_dict, current_groupby, warnings=None, **kwargs):
        """ A.1: Standard issued invoices where supplier is liable for VAT. """
        tag_ids = self._get_tag_ids_from_report_lines(['sk_ops_out_dom_sale'])
        # A.1 is only for registered business entities (have VAT ID or IČO).
        # Sales to pure consumers (no VAT, no IČO) fall under D.2 instead.
        domain = [
            ('tax_tag_ids', 'in', list(tag_ids)),
            '|',
            ('move_id.commercial_partner_id.additional_identifiers', '!=', False),
            ('move_id.commercial_partner_id.vat', '!=', False),
            *self._get_regular_document_domain(),
        ]
        return self._common_report_engine_control_statement(formulas_dict, options, current_groupby, domain, 'a1', **kwargs)

    def _report_engine_control_statement_A2(self, options, date_scope, formulas_dict, current_groupby, warnings=None, **kwargs):
        """ A.2: Domestic reverse charge issued invoices (§69). """
        rc_tax = self.env['account.chart.template'].ref('vy_rc', raise_if_not_found=False)
        domain = [
            ('tax_ids', 'in', rc_tax.ids if rc_tax else ()),
            ('move_id.move_type', '=', 'out_invoice'),
            *self._get_regular_document_domain(),
        ]
        return self._common_report_engine_control_statement(formulas_dict, options, current_groupby, domain, 'a2', **kwargs)

    def _report_engine_control_statement_B1(self, options, date_scope, formulas_dict, current_groupby, warnings=None, **kwargs):
        """ B.1: Reverse charge purchases (EU acquisitions, triangular, §69, §84a imports). """
        tag_ids = self._get_tag_ids_from_report_lines(self._get_b1_tag_xmlids())
        domain = [
            ('tax_tag_ids', 'in', list(tag_ids)),
            *self._get_regular_document_domain(),
        ]
        return self._common_report_engine_control_statement(formulas_dict, options, current_groupby, domain, 'b1', **kwargs)

    def _report_engine_control_statement_B2(self, options, date_scope, formulas_dict, current_groupby, warnings=None, **kwargs):
        """ B.2: Standard purchases with VAT deduction from Slovak suppliers. """
        tag_ids = self._get_tag_ids_from_report_lines(self._get_standard_purchase_tag_xmlids())
        # Simplified invoices are reported separately in B.3
        domain = [
            '|',
            ('tax_tag_ids', 'in', list(tag_ids)),
            ('tax_ids', 'in', self._get_standard_purchase_taxes().ids),
            ('move_id.commercial_partner_id.country_id.code', '=', 'SK'),
            ('move_id.move_type', '=', 'in_invoice'),
            *self._get_regular_document_domain(),
        ]
        return self._common_report_engine_control_statement(formulas_dict, options, current_groupby, domain, 'b2', **kwargs)

    def _report_engine_control_statement_B31(self, options, date_scope, formulas_dict, current_groupby, warnings=None, **kwargs):
        """ B.3.1: Simplified invoices aggregated (total deduction < 3,000€). """
        report = self.env['account.report'].browse(options['report_id'])
        if self._compute_simplified_invoice_total_deduction(report, options) >= 3000:
            return {next(iter(formulas_dict.values())): ([] if current_groupby else self._empty_result_dict())}

        return self._common_report_engine_control_statement(
            formulas_dict, options, current_groupby,
            self._get_simplified_invoice_domain(), 'b31', **kwargs
        )

    def _report_engine_control_statement_B32(self, options, date_scope, formulas_dict, current_groupby, warnings=None, **kwargs):
        """ B.3.2: Simplified invoices per supplier (total deduction >= 3,000€). """
        report = self.env['account.report'].browse(options['report_id'])
        if self._compute_simplified_invoice_total_deduction(report, options) < 3000:
            return {next(iter(formulas_dict.values())): ([] if current_groupby else self._empty_result_dict())}

        return self._common_report_engine_control_statement(
            formulas_dict, options, current_groupby,
            self._get_simplified_invoice_domain(), 'b32', **kwargs
        )

    def _report_engine_control_statement_C1(self, options, date_scope, formulas_dict, current_groupby, warnings=None, **kwargs):
        """ C.1: Corrections to issued supplies (credit notes and debit notes for A.1/A.2). """
        tag_ids = self._get_tag_ids_from_report_lines(['sk_adjustments_24_25', 'sk_ops_out_dom_sale'])
        rc_tax = self.env['account.chart.template'].ref('vy_rc', raise_if_not_found=False)
        domain = self._get_correction_domain(
            tag_ids, rc_tax.ids if rc_tax else (),
            refund_type='out_refund', invoice_type='out_invoice',
        )
        return self._common_report_engine_control_statement(formulas_dict, options, current_groupby, domain, 'c1', **kwargs)

    def _report_engine_control_statement_C2(self, options, date_scope, formulas_dict, current_groupby, warnings=None, **kwargs):
        """ C.2: Corrections to received supplies (credit notes and debit notes for B sections). """
        tag_ids = self._get_tag_ids_from_report_lines([
            'sk_adjustments_28',
            *self._get_b1_tag_xmlids(),
            *self._get_standard_purchase_tag_xmlids(),
        ])
        domain = self._get_correction_domain(
            tag_ids, self._get_standard_purchase_taxes().ids + self._get_reverse_charge_purchase_taxes().ids,
            refund_type='in_refund', invoice_type='in_invoice',
        )
        return self._common_report_engine_control_statement(formulas_dict, options, current_groupby, domain, 'c2', **kwargs)

    ####################################################
    # MAIN QUERY ENGINE
    ####################################################

    def _empty_result_dict(self):
        """ Return empty result dictionary with all report fields initialized. """
        return {
            'vat_number': None, 'invoice_number': None, 'taxable_supply_date': None,
            'tax_base': 0, 'tax_amount': 0, 'tax_rate': 0, 'deducted_amount': 0,
            'goods_code': None, 'goods_type': None, 'quantity': None, 'uom': None,
            'corrective_invoice': None, 'original_invoice': None,
            'tax_base_diff': 0, 'tax_diff': 0, 'deducted_diff': 0,
            'is_bad_debt': False, 'has_sublines': False,
        }

    def _common_report_engine_control_statement(self, formulas_dict, options, current_groupby, domain, code, export_flat=False):
        """ Build report lines by executing the section-specific SQL query and grouping results.

        :param options:             The report options.
        :param current_groupby:     The current groupby field ('move_id', 'partner_id', 'tax_rate', 'sk_product_tag', or None).
        :param domain:              Domain filter for the specific section.
        :param code:                Section code (a1, a2, b1, b2, b31, b32, c1, c2).
        :param export_flat:         If True, return one result dict per SQL row instead of grouping
                                    by key. Used by the XML export path to avoid collapsing rows from
                                    different moves that share the same grouping key (e.g. tax rate).
        :return:                    List of (grouping_key, result_dict) tuples or aggregated result dict.
        """
        report = self.env['account.report'].browse(options['report_id'])
        if current_groupby:
            report._check_groupby_fields([current_groupby])

        needs_product_tags = code in {'a2', 'c1'} or current_groupby == 'sk_product_tag'
        sk_product_tag_map = self._get_sk_product_tag_map() if needs_product_tags else {}
        query = report._get_report_query(options, 'strict_range', domain=domain)
        sql_query = self._build_sql_query(query, current_groupby, code, sk_product_tag_map)
        query_results = self.env.execute_query_dict(sql_query)

        if not current_groupby:
            return {next(iter(formulas_dict.values())): self._build_result_dict(query_results, None, code, sk_product_tag_map)}

        if export_flat:
            # Export mode, process each SQL row individually to preserve per-move granularity.
            # Each row already represents a unique (move, groupby_field) combination in the SQL.
            results = [
                self._build_result_dict([row], current_groupby, code, sk_product_tag_map)
                for row in query_results
            ]
            return {next(iter(formulas_dict.values())): results}

        results_by_key = defaultdict(list)
        for row in query_results:
            results_by_key[row['grouping_key']].append(row)

        results = [
            (key, self._build_result_dict(rows, current_groupby, code, sk_product_tag_map))
            for key, rows in results_by_key.items()
        ]

        # Drop NULL groups created by the LEFT JOIN (untagged tax lines), keep only if they
        # carry a base amount, meaning some lines genuinely lack a product tag assignment.
        if current_groupby == 'sk_product_tag':
            amount_field = 'tax_base_diff' if SECTION_PROFILES[code]['is_correction'] else 'tax_base'
            results = [(k, r) for k, r in results if k is not None or r.get(amount_field, 0)]

        return {next(iter(formulas_dict.values())): results}

    def _build_sql_query(self, query, current_groupby, code, sk_product_tag_map):
        """ Construct the SQL query for the control statement section.

        Uses section profiles to declaratively control which SQL fragments
        (move details, tax rate, goods attributes, correction handling) are included.
        """
        # Create section profile with runtime flags
        profile = dict(SECTION_PROFILES[code])
        profile['needs_move_details'] = (code != 'b31' and not (code == 'b32' and current_groupby == 'partner_id'))
        profile['needs_partner_details_only'] = (code == 'b32' and current_groupby == 'partner_id')

        # Move and partner fields
        select_clauses, groupby_clauses = self._build_move_detail_clauses(profile, current_groupby)

        # Goods attributes and quantity/UoM
        goods_select, goods_groupby, goods_joins = self._build_goods_clauses(profile, current_groupby, sk_product_tag_map)
        select_clauses += goods_select
        groupby_clauses += goods_groupby

        # Tax rate fields
        tax_select, tax_groupby, tax_joins = self._build_tax_rate_clauses(profile)
        select_clauses += tax_select
        groupby_clauses += tax_groupby

        # Drill-down grouping key
        groupby_field_sql = self._build_groupby_field_sql(profile, current_groupby, query)
        if groupby_field_sql:
            groupby_clauses.append(groupby_field_sql)

        # Amount and correction fields
        (amount_expr, base_field, tax_field, deducted_clause, correction_joins, correction_where) = (
            self._build_amount_and_correction_clauses(profile, code)
        )

        # sk_aml_move is needed by:
        #   - move/partner display clauses  (needs_move_details / needs_partner_details_only)
        #   - correction amount and WHERE clauses  (is_correction)
        needs_move_join = (
            profile.get('needs_move_details')
            or profile.get('needs_partner_details_only')
            or profile['is_correction']
        )
        move_join = SQL(
            "LEFT JOIN account_move sk_aml_move ON sk_aml_move.id = account_move_line.move_id"
        ) if needs_move_join else SQL()

        partner_join = SQL("""
            LEFT JOIN res_partner partner ON partner.id = sk_aml_move.commercial_partner_id
            LEFT JOIN res_country country ON country.id = partner.country_id
        """) if (profile.get('needs_move_details') or profile.get('needs_partner_details_only')) else SQL()

        return SQL("""
            SELECT
                %(select_groupby)s
                %(select_clauses)s
                COALESCE(SUM(CASE WHEN account_move_line.tax_line_id IS NULL
                    THEN %(amount_expr)s ELSE 0 END), 0) AS %(base_field)s,
                COALESCE(SUM(CASE WHEN account_move_line.tax_line_id IS NOT NULL
                    THEN %(amount_expr)s ELSE 0 END), 0) AS %(tax_field)s
                %(deducted_clause)s
            FROM %(table_references)s
            %(move_join)s
            %(partner_join)s
            %(tax_joins)s
            %(correction_joins)s
            %(goods_joins)s
            WHERE %(where_clause)s %(correction_where)s
            %(groupby_clause)s
            %(orderby_clause)s
        """,
            select_groupby=SQL('%s AS grouping_key,', groupby_field_sql) if groupby_field_sql else SQL(),
            select_clauses=SQL('%s,', SQL(', ').join(select_clauses)) if select_clauses else SQL(),
            amount_expr=amount_expr,
            base_field=base_field,
            tax_field=tax_field,
            deducted_clause=deducted_clause,
            table_references=query.from_clause,
            move_join=move_join,
            partner_join=partner_join,
            tax_joins=tax_joins,
            correction_joins=correction_joins,
            goods_joins=goods_joins,
            where_clause=query.where_clause,
            correction_where=correction_where,
            groupby_clause=SQL('GROUP BY %s', SQL(', ').join(groupby_clauses)) if groupby_clauses else SQL(),
            orderby_clause=SQL('ORDER BY %s', groupby_field_sql) if groupby_field_sql else SQL(),
        )

    def _build_move_detail_clauses(self, profile, current_groupby):
        """ Build SELECT/GROUP BY fragments for move and partner data. """
        select_clauses = []
        groupby_clauses = []

        if profile['needs_partner_details_only']:
            select_clauses.append(SQL('MIN(partner.vat) AS vat_number, MIN(country.code) AS country_code'))
        elif profile['needs_move_details'] and profile['is_correction']:
            select_clauses.append(SQL("""
                MIN(sk_aml_move.name) AS corrective_invoice,
                MIN(sk_aml_move.ref) AS corrective_invoice_ref,
                BOOL_OR(sk_aml_move.l10n_sk_is_bad_debt) AS is_bad_debt,
                MIN(partner.vat) AS vat_number,
                MIN(original_move.name) AS original_invoice_name,
                MIN(original_move.ref) AS original_invoice_ref
            """))
            if current_groupby in ('tax_rate', 'sk_product_tag'):
                groupby_clauses.append(SQL('sk_aml_move.id'))
        elif profile['needs_move_details']:
            select_clauses.append(SQL("""
                MIN(partner.vat) AS vat_number,
                MIN(country.code) AS country_code,
                MIN(sk_aml_move.taxable_supply_date) AS taxable_supply_date,
                MIN(sk_aml_move.name) AS move_name,
                MIN(sk_aml_move.move_type) AS move_type,
                MIN(sk_aml_move.ref) AS ref
            """))
            if current_groupby in ('tax_rate', 'sk_product_tag'):
                groupby_clauses.append(SQL('sk_aml_move.id'))

        return select_clauses, groupby_clauses

    def _build_goods_clauses(self, profile, current_groupby, sk_product_tag_map):
        """ Build SELECT/GROUP BY/JOIN fragments for goods and quantity. """
        select_clauses = []
        groupby_clauses = []
        goods_joins = SQL()

        # Convert invoice units to standard units (m, kg, ks) required by Slovak tax law.
        # E.g. 100 ft² --> 9.29 m² (both in category 11, matched by split_part parent_path).
        uom_joins = SQL("""
            LEFT JOIN uom_uom line_uom ON line_uom.id = account_move_line.product_uom_id
            LEFT JOIN uom_uom mapped_uom ON
                line_uom.id IS NOT NULL
                AND line_uom.parent_path IS NOT NULL
                AND mapped_uom.parent_path IS NOT NULL
                AND mapped_uom.l10n_sk_vat_code IS NOT NULL
                AND split_part(mapped_uom.parent_path, '/', 1)
                    = split_part(line_uom.parent_path, '/', 1)
        """)

        # Skip tax lines; convert using qty * source_factor / target_factor.
        # Return raw qty if no UoM or reference unit found (fallback).
        # Round to 2 decimals and extract VAT code (m, kg, ks).
        quantity_uom_clause = SQL("""
            ROUND(SUM(
                CASE WHEN account_move_line.tax_line_id IS NULL THEN
                    CASE
                        WHEN line_uom.id IS NOT NULL AND mapped_uom.id IS NOT NULL
                        THEN account_move_line.quantity * line_uom.factor / NULLIF(mapped_uom.factor, 0)
                        ELSE account_move_line.quantity
                    END
                ELSE 0 END
            ), 2) AS quantity,
            MAX(CASE WHEN mapped_uom.id IS NOT NULL THEN mapped_uom.l10n_sk_vat_code ELSE NULL END) AS uom
        """)

        if profile['has_goods']:
            tag_ids = tuple(sk_product_tag_map)
            tag_join = SQL()
            if tag_ids:
                # At sk_product_tag level, GROUP BY tag for per-commodity lines.
                # At other levels, MAX for a single representative value.
                tag_agg = SQL('sk_product_tag.tag_id') if current_groupby == 'sk_product_tag' else SQL('MAX(sk_product_tag.tag_id)')
                select_clauses.append(SQL("""
                    %(tag_agg)s AS sk_product_tag_id,
                    %(quantity_uom_clause)s
                """, tag_agg=tag_agg, quantity_uom_clause=quantity_uom_clause))
                if current_groupby == 'sk_product_tag':
                    groupby_clauses.append(SQL('sk_product_tag.tag_id'))
                tag_join = SQL("""
                    LEFT JOIN LATERAL (
                        SELECT MIN(tag.id) AS tag_id
                        FROM account_account_tag_account_move_line_rel rel
                        JOIN account_account_tag tag
                            ON tag.id = rel.account_account_tag_id
                        WHERE rel.account_move_line_id = account_move_line.id
                        AND tag.id IN %s
                    ) sk_product_tag ON TRUE
                """, tag_ids)
            else:
                select_clauses.append(SQL("""
                    NULL::integer AS sk_product_tag_id,
                    %(quantity_uom_clause)s
                """, quantity_uom_clause=quantity_uom_clause))
            goods_joins = SQL("""
                %(tag_join)s
                %(uom_joins)s
            """, tag_join=tag_join, uom_joins=uom_joins)
        elif profile['has_quantity']:
            select_clauses.append(quantity_uom_clause)
            goods_joins = uom_joins

        return select_clauses, groupby_clauses, goods_joins

    def _build_tax_rate_clauses(self, profile):
        """ Build SELECT/GROUP BY/JOIN fragments for tax rate. """
        select_clauses = []
        groupby_clauses = []
        tax_joins = SQL()

        if profile['has_tax_rate']:
            tax_joins = SQL("""
                LEFT JOIN account_tax net_tax ON account_move_line.tax_line_id = net_tax.id
                LEFT JOIN account_move_line_account_tax_rel aml_tax_rel
                    ON account_move_line.id = aml_tax_rel.account_move_line_id
                LEFT JOIN account_tax base_tax ON aml_tax_rel.account_tax_id = base_tax.id
            """)
            select_clauses.append(SQL('COALESCE(net_tax.amount, base_tax.amount, 0) AS tax_rate'))
            groupby_clauses.append(SQL('COALESCE(net_tax.amount, base_tax.amount, 0)'))

        return select_clauses, groupby_clauses, tax_joins

    def _build_amount_and_correction_clauses(self, profile, code):
        """ Build amount and correction SQL fragments. """
        has_debit_origin = 'debit_origin_id' in self.env['account.move']._fields

        amount_expr = SQL('ABS(account_move_line.balance)')
        base_field, tax_field = SQL('tax_base'), SQL('tax_amount')
        deducted_clause = SQL(
            ", COALESCE(SUM(CASE WHEN account_move_line.tax_line_id IS NOT NULL "
            "THEN ABS(account_move_line.balance) ELSE 0 END), 0) AS deducted_amount"
        )
        correction_joins = SQL()
        correction_where = SQL()

        if profile['is_correction']:
            origin_expr = (
                SQL('COALESCE(sk_aml_move.reversed_entry_id, sk_aml_move.debit_origin_id)')
                if has_debit_origin else SQL('sk_aml_move.reversed_entry_id')
            )
            correction_joins = SQL("""
                LEFT JOIN account_move original_move ON original_move.id = %(origin_expr)s
            """, origin_expr=origin_expr)
            amount_expr = SQL("""
                CASE
                    WHEN sk_aml_move.move_type = 'in_refund'
                    THEN -ABS(account_move_line.balance)
                    ELSE ABS(account_move_line.balance)
                END
            """) if code == 'c2' else SQL('-account_move_line.balance')
            base_field, tax_field = SQL('tax_base_diff'), SQL('tax_diff')
            deducted_clause = SQL()
            correction_where = SQL(
                'AND (sk_aml_move.reversed_entry_id IS NOT NULL '
                'OR sk_aml_move.debit_origin_id IS NOT NULL)'
            ) if has_debit_origin else SQL('AND sk_aml_move.reversed_entry_id IS NOT NULL')

        return amount_expr, base_field, tax_field, deducted_clause, correction_joins, correction_where

    def _build_groupby_field_sql(self, profile, current_groupby, query):
        """Return the grouping_key SQL expression for the current drill-down.

        For custom groupby fields that are not supported by the current section
        (e.g. sk_product_tag on A.1 which has no goods), return a NULL constant
        so all rows collapse into one "N/A" bucket rather than crashing on a
        missing column alias.
        """
        if current_groupby == 'tax_rate':
            return (
                SQL('COALESCE(net_tax.amount, base_tax.amount, 0)')
                if profile['has_tax_rate'] else SQL('NULL::numeric')
            )
        if current_groupby == 'sk_product_tag':
            return (
                SQL('sk_product_tag.tag_id')
                if profile['has_goods'] else SQL('NULL::integer')
            )
        if current_groupby:
            return query.table[current_groupby]
        return SQL()

    def _build_result_dict(self, query_results, current_groupby, code, sk_product_tag_map):
        """ Build result dictionary from query results for a single grouping key. """
        result = self._empty_result_dict()
        if not query_results:
            return result

        is_move_tax_section = current_groupby == 'move_id' and code in {'a1', 'b1', 'b2', 'c1', 'c2'}

        for index, row in enumerate(query_results):
            is_first_row = index == 0
            if not current_groupby:
                result['has_sublines'] = True
                result['tax_base_diff'] += row.get('tax_base_diff', 0)
                result['tax_diff'] += row.get('tax_diff', 0)
                result['tax_base'] += row.get('tax_base', 0)
                result['tax_amount'] += row.get('tax_amount', 0)
                result['deducted_amount'] += row.get('deducted_amount', 0)
                continue

            is_a2_correction = code == 'c1' and current_groupby == 'move_id' and row.get('tax_rate', 0) == 0

            if is_first_row:
                result['tax_rate'] = int(row.get('tax_rate', 0)) if not is_move_tax_section else 0
                result['has_sublines'] = bool(current_groupby)
                result.update({
                    'vat_number': row.get('vat_number'),
                    'corrective_invoice': (row.get('corrective_invoice_ref') or '' if code == 'c2' else row.get('corrective_invoice') or '').replace(' ', ''),
                    'original_invoice': (row.get('original_invoice_ref') or row.get('original_invoice_name') or '').replace(' ', ''),
                    'tax_base_diff': row.get('tax_base_diff', 0),
                    'tax_diff': row.get('tax_diff', 0),
                    'is_bad_debt': row.get('is_bad_debt', False),
                    'tax_base': row.get('tax_base', 0),
                    'tax_amount': row.get('tax_amount', 0),
                    'deducted_amount': row.get('deducted_amount', 0),
                    'taxable_supply_date': row.get('taxable_supply_date') and row['taxable_supply_date'].strftime('%Y-%m-%d'),
                })
                if code == 'a2' and current_groupby == 'sk_product_tag':
                    self._resolve_goods_tag(result, row.get('sk_product_tag_id'), sk_product_tag_map)
                if row.get('move_type') in self.env['account.move'].get_purchase_types(include_receipts=True):
                    invoice_ref = row.get('ref') or row.get('move_name')
                else:
                    invoice_ref = row.get('move_name')
                result['invoice_number'] = (invoice_ref or '').replace(' ', '')
                if current_groupby != 'move_id':
                    result['quantity'] = row.get('quantity')
                    result['uom'] = row.get('uom')
                continue

            if SECTION_PROFILES[code]['is_correction']:
                result['tax_base_diff'] += row.get('tax_base_diff', 0)
                result['tax_diff'] += row.get('tax_diff', 0)
            else:
                result['tax_base'] += row.get('tax_base', 0)
                result['tax_amount'] += row.get('tax_amount', 0)
                result['deducted_amount'] += row.get('deducted_amount', 0)
            if current_groupby != 'move_id' and row.get('quantity') is not None:
                result['quantity'] = (result.get('quantity') or 0) + row['quantity']

        if code == 'c2':
            result['deducted_diff'] = result['tax_diff']

        if not current_groupby:
            return result

        # Clear per-invoice detail columns when multiple invoices are aggregated
        # under the same groupby key, showing one invoice's data on an aggregate
        # line is misleading.
        if current_groupby == 'partner_id':
            # Partner aggregate - invoice_number/date do not belong to a single invoice;
            # vat_number is kept because it identifies the partner.
            # tax_rate is reset to 0 because the line spans potentially multiple rates.
            result['invoice_number'] = None
            result['taxable_supply_date'] = None
            result['tax_rate'] = 0
        elif current_groupby != 'move_id' and len(query_results) > 1:
            # Multiple invoices collapsed into one group (e.g. tax_rate or
            # sk_product_tag used as a top-level groupby with several invoices
            # sharing the same key). Per-invoice fields have no single owner here.
            result['vat_number'] = None
            result['invoice_number'] = None
            result['taxable_supply_date'] = None

        if code == 'c1':
            # Detect A.2 correction lines at leaf groupby levels.
            # Skip for partner_id groupby, the aggregate spans both correction types
            # so A.2 detection is not applicable, and tax_rate was already reset to 0.
            if current_groupby not in ('move_id', 'partner_id'):
                is_a2_correction = not result['tax_rate']
                quantity = result.get('quantity')
                if quantity and result.get('tax_base_diff', 0) < 0:
                    quantity = -abs(quantity)
                result['quantity'] = quantity

            if is_a2_correction:
                last_row = query_results[-1]
                self._resolve_goods_tag(result, last_row.get('sk_product_tag_id'), sk_product_tag_map)

        return result

    ####################################################
    # EXPORT
    ####################################################

    def l10n_sk_export_vat_control_report_to_xml(self, options):
        """ Generate XML export of the VAT Control Statement (Regular filing).

        Calls report engines directly with the leaf-level groupby to fetch
        detail-level records in a single query per section, bypassing the
        hierarchy computation of _get_lines().
        """
        main_report = self.env.ref('l10n_sk_reports.control_statement_report')
        sender_company = main_report._get_sender_company_for_export(options)

        if not sender_company.vat:
            raise UserError(self.env._("Please set the company VAT number before exporting."))

        date_from = fields.Date.to_date(options['date']['date_from'])
        period_type = options['date'].get('period_type', 'month')

        section_lines, d1_data, d2_data = self._l10n_sk_collect_section_lines(main_report, options)

        data = {
            'identification': {
                'ic_dph_platitela': sender_company.vat,
                'druh': 'R',
                'rok': date_from.year,
                'mesiac': date_from.month if period_type == 'month' else None,
                'stvrtrok': date_utils.get_quarter_number(date_from) if period_type == 'quarter' else None,
                'nazov': sender_company.name,
                'stat': sender_company.country_id.name or '',
                'obec': sender_company.city or '',
                'psc': sender_company.zip or '',
                'ulica': sender_company.street or '',
                'cislo': sender_company.street2 or '',
                'tel': sender_company.phone or '',
                'email': sender_company.email or '',
            },
            'd1_data': d1_data,
            'd2_data': d2_data,
            **section_lines,
        }

        xml_content = self.env['ir.qweb']._render('l10n_sk_reports.control_statement_export_template', data)
        tree = etree.fromstring(xml_content)
        cleanup_xml_node(tree, remove_blank_nodes=False)
        formatted_xml = etree.tostring(tree, pretty_print=True, xml_declaration=True, encoding='UTF-8')

        return {
            'file_name': main_report.get_default_report_filename(options, 'xml'),
            'file_content': formatted_xml,
            'file_type': 'xml',
        }

    def _l10n_sk_collect_section_lines(self, main_report, options):
        """ Collect all section data for XML export.

        For sections A-C, calls each engine with the leaf-level groupby and
        export_flat=True to get all detail records in a single SQL query per
        section, processing each row individually to avoid the recursive descent.

        :return: (section_lines dict, d1_data, d2_data)
        """
        section_lines = {f'{code}_lines': [] for code in ('a1', 'a2', 'b1', 'b2', 'b31', 'b32', 'c1', 'c2')}
        d1_data = d2_data = None
        formulas_dict = {'result': 'result'}

        for section_report in main_report.section_report_ids:
            section_options = section_report.get_options(previous_options={
                **options,
                'no_report_reroute': True,
                'export_mode': 'file',
            })
            # Pre-compute figure_type mapping once per section (shared by all lines).
            figure_type_by_label = {
                col.expression_label: (col.figure_type or 'string')
                for col in section_report.column_ids
            }

            for section_line in section_report.line_ids:
                code = section_line.code
                if not code:
                    continue

                if code in {'D1', 'D2'}:
                    # Fetch D1/D2 aggregate data via _get_lines() (external engine, manually entered values)
                    line_data = None
                    for line in section_report._get_lines({**section_options}):
                        if line.code == code:
                            line_data = {
                                col.expression_label: self._l10n_sk_format_export_value(col.no_format, col.figure_type)
                                for col in line.columns
                            }
                            break
                    if code == 'D1':
                        d1_data = line_data
                    else:
                        d2_data = line_data
                    continue

                leaf_groupby = self._l10n_sk_get_leaf_groupby(section_line)
                section_lines[f'{code.lower()}_lines'].extend(
                    self._l10n_sk_collect_export_records(
                        section_options, code, leaf_groupby,
                        formulas_dict, figure_type_by_label,
                    )
                )

        return section_lines, d1_data, d2_data

    def _l10n_sk_get_leaf_groupby(self, section_line):
        """ Return the deepest groupby field from the line's groupby chain.

        For XML export, we query at the leaf level directly (e.g. 'tax_rate' for
        'move_id,tax_rate') to get all detail records in one SQL query instead of
        recursively expanding each level.
        """
        groupby_chain = [g for g in (section_line.groupby or '').replace(' ', '').split(',') if g]
        return groupby_chain[-1] if groupby_chain else None

    def _l10n_sk_collect_export_records(self, options, code, leaf_groupby, formulas_dict, figure_type_by_label):
        """ Collect export records by calling the engine with the leaf-level groupby.

        Calls the engine method once with export_flat=True, which processes each SQL
        row individually instead of grouping by key. This eliminates the recursive
        descent while preserving per-move granularity in the results.

        :param options:                 Report options for the engine call.
        :param code:                    Section code (e.g. 'A1', 'B32', 'C2').
        :param leaf_groupby:            The deepest groupby field (e.g. 'tax_rate'), or None.
        :param formulas_dict:           Dummy formula dict for engine compatibility.
        :param figure_type_by_label:    Pre-computed {label: figure_type} for formatting.
        :return:                        List of formatted export record dicts.
        """
        engine_method = {
            'A1': self._report_engine_control_statement_A1,
            'A2': self._report_engine_control_statement_A2,
            'B1': self._report_engine_control_statement_B1,
            'B2': self._report_engine_control_statement_B2,
            'B31': self._report_engine_control_statement_B31,
            'B32': self._report_engine_control_statement_B32,
            'C1': self._report_engine_control_statement_C1,
            'C2': self._report_engine_control_statement_C2,
        }[code]
        engine_result = engine_method(options, None, formulas_dict, leaf_groupby, export_flat=bool(leaf_groupby))
        result_data = next(iter(engine_result.values()))

        if not leaf_groupby:
            # Aggregate section (e.g. B31): single result dict, no grouping.
            if result_data and self._l10n_sk_has_export_data(result_data):
                return [self._l10n_sk_format_export_record(result_data, figure_type_by_label)]
            return []

        # Flat results --> each element is a result dict (one per SQL row).
        # Keep the same business order as the unfolded report, newest documents first,
        # then invoice/correction reference descending, then tax rate ascending.
        result_data.sort(
            key=lambda row: (
                row.get('taxable_supply_date') or '',
                row.get('corrective_invoice') or row.get('invoice_number') or '',
                -(row.get('tax_rate') or 0),  # Negate to sort ascending while using reverse=True overall
            ),
            reverse=True,
        )
        return [
            self._l10n_sk_format_export_record(record_dict, figure_type_by_label)
            for record_dict in result_data
            if self._l10n_sk_has_export_data(record_dict)
        ]

    def _l10n_sk_format_export_value(self, value, figure_type):
        """ Format a single value for XML export based on its figure type. """
        if value is None:
            return None
        if figure_type == 'monetary':
            return float_repr(value, 2)
        if figure_type == 'float':
            return float_repr(value, 2) if value else 0.0
        if figure_type == 'integer':
            return int(value)
        return value

    def _l10n_sk_format_export_record(self, record_dict, figure_type_by_label):
        """ Format a record dict for XML export, applying figure_type formatting. """
        return {
            label: self._l10n_sk_format_export_value(value, figure_type_by_label.get(label, 'string'))
            for label, value in record_dict.items()
        }

    def _l10n_sk_has_export_data(self, record_dict):
        """ Check whether a record dict contains any non-zero amounts or invoice references. """
        return any(
            record_dict.get(field, 0) != 0
            for field in ('tax_base', 'tax_amount', 'tax_base_diff', 'tax_diff', 'deducted_amount', 'deducted_diff')
        ) or bool(record_dict.get('invoice_number')) or bool(record_dict.get('corrective_invoice'))

    ####################################################
    # HELPER FUNCTIONS
    ####################################################

    def _get_tag_ids_from_report_lines(self, xmlids):
        tag_ids = set()
        for xmlid in xmlids:
            report_line = self.env.ref(f'l10n_sk.{xmlid}', raise_if_not_found=False)
            if report_line:
                if report_line.children_ids:
                    tag_ids.update(report_line.children_ids.expression_ids._get_matching_tags().ids)
                else:
                    tag_ids.update(report_line.expression_ids._get_matching_tags().ids)
        return tag_ids

    def _get_correction_domain(self, tag_ids, tax_ids, refund_type, invoice_type):
        """ Build domain for correction sections (C.1/C.2), including debit note support. """
        correction_line_domain = [
            '|',
            ('tax_tag_ids', 'in', list(tag_ids)),
            ('tax_ids', 'in', tax_ids),
        ]
        domain = [
            *correction_line_domain,
            ('move_id.move_type', '=', refund_type),
        ]
        # Debit notes (account_debit_note) are invoice-type moves referencing an original
        if 'debit_origin_id' in self.env['account.move']._fields:
            domain = [
                *correction_line_domain,
                '|',
                ('move_id.move_type', '=', refund_type),
                '&',
                ('move_id.move_type', '=', invoice_type),
                ('move_id.debit_origin_id', '!=', False),
            ]
        return domain

    def _resolve_goods_tag(self, result, tag_id, tag_map):
        """ Set goods_code or goods_type on result dict from the product tag mapping. """
        tag_info = tag_map.get(tag_id)
        if tag_info:
            field = 'goods_code' if tag_info['type'] == 'tk' else 'goods_type'
            result[field] = tag_info['code']

    def _get_standard_purchase_tag_xmlids(self):
        """ Return XMLIDs for standard purchase deduction tags (§20, §20a, §21). """
        return ['sk_deductible_specific_20', 'sk_deductible_specific_20a', 'sk_deductible_specific_21']

    def _get_b1_tag_xmlids(self):
        """ Return XMLIDs for B.1 reverse charge purchase tags. """
        return [
            'sk_ops_in_purchase',
            'sk_rev_charge_supplier',
            'sk_imp_standard',
            'sk_imp_postponed',
        ]

    def _get_simplified_invoice_domain(self):
        """ Build domain for simplified purchase receipt sections (B.3.1/B.3.2). """
        tag_ids = self._get_tag_ids_from_report_lines([
            'sk_deductible_specific_20_simpl',
            'sk_deductible_specific_20a_simpl',
            'sk_deductible_specific_21_simpl',
        ])
        return [
            '|',
            ('tax_tag_ids', 'in', list(tag_ids)),
            ('tax_ids', 'in', self._get_simplified_purchase_taxes().ids),
            ('move_id.move_type', '=', 'in_receipt'),
            *self._get_regular_document_domain(),
        ]

    def _get_standard_purchase_taxes(self):
        """ Get standard Slovak purchase taxes (vs_tuz_*). """
        return self._get_taxes_from_xmlids(['vs_tuz_23', 'vs_tuz_19', 'vs_tuz_5'])

    def _get_reverse_charge_purchase_taxes(self):
        """ Get Slovak reverse charge purchase taxes based on B.1 tags. """
        tag_ids = self._get_tag_ids_from_report_lines(self._get_b1_tag_xmlids())
        return self.env['account.tax'].search([
            ('invoice_repartition_line_ids.tag_ids', 'in', list(tag_ids))
        ])

    def _get_simplified_purchase_taxes(self):
        """ Get simplified Slovak purchase taxes for purchase receipts (vs_tuz_*_simpl). """
        return self._get_taxes_from_xmlids(['vs_tuz_23_simpl', 'vs_tuz_19_simpl', 'vs_tuz_5_simpl'])

    def _get_taxes_from_xmlids(self, xml_ids):
        """ Return a tax recordset built from chart template XML IDs. """
        return self.env['account.tax'].union(
            self.env['account.chart.template'].ref(xml_id, raise_if_not_found=False) or self.env['account.tax']
            for xml_id in xml_ids
        )

    def _compute_simplified_invoice_total_deduction(self, report, options):
        """ Compute total VAT deduction from simplified purchase receipts for B.3 threshold check. """
        if 'b3_total_deduction_cache' in options:
            return options['b3_total_deduction_cache']

        query = report._get_report_query(options, 'strict_range', domain=self._get_simplified_invoice_domain())

        sql_query = SQL("""
            SELECT COALESCE(SUM(CASE WHEN account_move_line.tax_line_id IS NOT NULL
                THEN account_move_line.balance ELSE 0 END), 0) AS total_deduction
            FROM %(table_references)s
            WHERE %(search_condition)s
        """,
            table_references=query.from_clause,
            search_condition=query.where_clause,
        )
        result = self.env.execute_query(sql_query)
        total_deduction = result[0][0] if result else 0
        options['b3_total_deduction_cache'] = total_deduction
        return total_deduction

    def _get_regular_document_domain(self):
        """Exclude debit notes from regular sections; debit notes are reported in C sections."""
        if 'debit_origin_id' in self.env['account.move']._fields:
            return [('move_id.debit_origin_id', '=', False)]
        return []

    def _get_sk_product_tag_labels(self, keys, options=None):
        """ Build display labels for commodity code groupby keys. """
        tag_map = self._get_sk_product_tag_map()
        labels = {}
        for key in keys:
            if key is None:
                labels[key] = self.env._("Other")
            else:
                tag_info = tag_map.get(key, {})
                if tag_info.get('type') == 'tk':
                    labels[key] = self.env._("TK %s", tag_info['code'])
                elif tag_info.get('type') == 'td':
                    labels[key] = self.env._("TD %s", tag_info['code'])
                else:
                    labels[key] = str(key)
        return labels

    def _get_sk_product_tag_map(self):
        """ Return a mapping of tag IDs to their commodity code or goods type,
        derived from XML ID naming conventions (tag_tk_XXXX for commodity codes,
        tag_td_XX for goods types). Used by sections A.2 and C.1 to resolve
        the TK/TD columns in the KVDPH export.

        :return: dict {tag_id: {'type': 'tk'/'td', 'code': str}}
        """
        records = self.env['ir.model.data'].search([
            ('module', '=', 'l10n_sk_reports'),
            ('model', '=', 'account.account.tag'),
            ('name', 'like', 'tag_t'),
        ])
        tag_map = {}
        for rec in records:
            if rec.name.startswith('tag_tk_'):
                tag_map[rec.res_id] = {'type': 'tk', 'code': rec.name[7:]}
            elif rec.name.startswith('tag_td_'):
                tag_map[rec.res_id] = {'type': 'td', 'code': rec.name[7:].upper()}
        return tag_map

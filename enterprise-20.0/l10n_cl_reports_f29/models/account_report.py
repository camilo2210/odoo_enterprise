from odoo import api, models
from odoo.fields import Domain
from odoo.tools import SQL


class AccountReport(models.Model):
    _inherit = 'account.report'

    def _get_expression_audit_aml_domain(self, expression_to_audit, options):
        # EXTENDS account_reports
        if expression_to_audit.engine == 'custom' and expression_to_audit.formula == '_report_custom_engine_f29_combined':
            return self._l10n_cl_reports_f29_get_audit_domain(expression_to_audit, options, expression_to_audit.label)

        return super()._get_expression_audit_aml_domain(expression_to_audit, options)

    def _l10n_cl_reports_f29_get_audit_domain(self, expression, options, audit_label):
        def get_matching_tags(*xml_ids):
            records = self.env['account.report.expression']
            for xml_id in xml_ids:
                records += self.env.ref(f'l10n_cl.{xml_id}', raise_if_not_found=False)
            return tuple(records._get_matching_tags().ids) or (0,)

        subformula = expression.subformula
        if not subformula:
            return Domain([])

        bucket = subformula.split('_')[-1]

        # Base universal domain (mirrors the WHERE clause)
        domain = [('display_type', '!=', 'payment_term')]

        # --- GROUP 1: Strict Base/Tax pairs mapped by display_type ---
        strict_pairs = {
            '111': (('39', '41'), 'out_invoice'),
            '502': (('33',), 'out_invoice'),
            '510': (('61',), 'out_refund'),
            '513': (('56',), 'out_invoice'),
            '528': (('61',), 'in_refund'),
            '532': (('56',), 'in_invoice'),
            '535': (('914',), 'in_invoice'),
        }

        if bucket in strict_pairs:
            doc_codes, move_type = strict_pairs[bucket]
            domain += [
                ('move_id.l10n_latam_document_type_id.code', 'in', doc_codes),
                ('move_id.move_type', '=', move_type)
            ]
            if audit_label == 'balance':
                domain += [('display_type', 'in', ('product', 'rounding'))]
            elif audit_label == 'tax_balance':
                domain += [('display_type', '=', 'tax')]

        # --- GROUP 2: Static Grids (No display_type split, SQL assigns everything matching to the same grid) ---
        elif bucket == '020':
            domain += [('move_id.l10n_latam_document_type_id.code', 'in', ('110', '111', '112')), ('move_id.move_type', 'in', ('out_invoice', 'out_refund'))]

        elif bucket == '142':
            domain += [('move_id.l10n_latam_document_type_id.code', 'in', ('34', '56', '61')), ('move_id.move_type', 'in', ('out_invoice', 'out_refund'))]
            # Mirror SQL CASE fallthrough: Exclude document/move combinations already caught by Group 1
            domain += ['!', '&', ('move_id.l10n_latam_document_type_id.code', '=', '56'), ('move_id.move_type', '=', 'out_invoice')]
            domain += ['!', '&', ('move_id.l10n_latam_document_type_id.code', '=', '61'), ('move_id.move_type', '=', 'out_refund')]

        elif bucket == '562':
            domain += [('move_id.l10n_latam_document_type_id.code', 'in', ('34', '56', '61')), ('move_id.move_type', 'in', ('in_invoice', 'in_refund'))]
            # Mirror SQL CASE fallthrough: Exclude document/move combinations already caught by Group 1
            domain += ['!', '&', ('move_id.l10n_latam_document_type_id.code', '=', '56'), ('move_id.move_type', '=', 'in_invoice')]
            domain += ['!', '&', ('move_id.l10n_latam_document_type_id.code', '=', '61'), ('move_id.move_type', '=', 'in_refund')]

        elif bucket == '566':
            domain += [('move_id.l10n_latam_document_type_id', '=', False), ('move_id.move_type', 'in', ('in_invoice', 'in_refund'))]

        # --- GROUP 3: Tag-Dependent Grids (Mapped dynamically via the specific base vs tax tags) ---
        elif bucket == '151':
            domain += [('move_id.l10n_latam_document_type_id.code', '=', '71'), ('move_id.move_type', '=', 'in_invoice')]
            if audit_label == 'tax_balance':
                domain += [('tax_tag_ids', 'in', get_matching_tags('tax_report_retencion_segunda_categ_tag'))]

        elif bucket in ('762', '520', '521', '525'):
            domain += [('move_id.l10n_latam_document_type_id.code', 'in', ('33', '46')), ('move_id.move_type', 'in', ('in_invoice', 'in_refund'))]

            if bucket == '762':
                if audit_label == 'balance':
                    domain += [('tax_tag_ids', 'in', get_matching_tags('tax_report_compras_supermercado_tag'))]
                else:
                    domain += [('tax_tag_ids', 'in', get_matching_tags('tax_report_compras_iva_supermercado_tag'))]
            elif bucket == '520':
                if audit_label == 'balance':
                    domain += [('tax_tag_ids', 'in', get_matching_tags('tax_report_compras_netas_gr_iva_recup_tag'))]
                else:
                    domain += [('tax_tag_ids', 'in', get_matching_tags('tax_report_compras_iva_recup_tag'))]
            elif bucket == '521':
                if audit_label == 'balance':
                    domain += [('tax_tag_ids', 'in', get_matching_tags('tax_report_compras_activo_fijo_no_recup_tag', 'tax_report_compras_netas_gr_iva_no_recuperable_tag'))]
                else:
                    domain += [('tax_tag_ids', 'in', get_matching_tags('tax_report_compras_iva_activo_fijo_no_recup_tag', 'tax_report_compras_iva_no_recup_tag'))]
            elif bucket == '525':
                if audit_label == 'balance':
                    domain += [('tax_tag_ids', 'in', get_matching_tags('tax_report_compras_activo_fijo_tag', 'tax_report_compras_activo_fijo_uso_comun_tag', 'tax_report_compras_activo_fijo_no_recup_tag'))]
                else:
                    domain += [('tax_tag_ids', 'in', get_matching_tags('tax_report_compras_iva_activo_fijo_tag', 'tax_report_compras_iva_activo_fijo_uso_comun_tag', 'tax_report_compras_iva_activo_fijo_no_recup_tag'))]

        elif bucket == '039':
            domain += [('move_id.l10n_latam_document_type_id.code', '=', '46'), ('move_id.move_type', 'in', ('in_invoice', 'in_refund'))]
            if audit_label == 'tax_balance':
                domain += [('display_type', '=', 'tax'), ('tax_tag_ids', 'in', get_matching_tags('tax_report_retencion_total_compras_tag'))]

        return Domain(domain)


class L10nClTaxReportHandler(models.AbstractModel):
    _name = 'l10n_cl.tax.report.handler'
    _inherit = 'account.tax.report.handler'
    _description = 'Chilean Tax Report Handler'

    @api.model
    def _get_tag_ids_per_report_grid(self):
        def get_matching_tags(*xml_ids):
            records = self.env['account.report.expression']
            for xml_id in xml_ids:
                records += self.env.ref(f'l10n_cl.{xml_id}')
            return tuple(records._get_matching_tags().ids) or (0,)

        return {
            'tags_039': get_matching_tags('tax_report_retencion_total_compras_tag'),
            'tags_151': get_matching_tags('tax_report_retencion_segunda_categ_tag'),
            'tags_519': get_matching_tags('tax_report_compras_netas_gr_iva_recup_tag'),
            'tags_520': get_matching_tags('tax_report_compras_iva_recup_tag'),
            'tags_521': get_matching_tags(
                'tax_report_compras_iva_activo_fijo_no_recup_tag',
                'tax_report_compras_iva_no_recup_tag',
            ),
            'tags_524': get_matching_tags(
                'tax_report_compras_activo_fijo_tag',
                'tax_report_compras_activo_fijo_uso_comun_tag',
                'tax_report_compras_activo_fijo_no_recup_tag',
            ),
            'tags_525': get_matching_tags(
                'tax_report_compras_iva_activo_fijo_tag',
                'tax_report_compras_iva_activo_fijo_uso_comun_tag',
                'tax_report_compras_iva_activo_fijo_no_recup_tag',
            ),
            'tags_564': get_matching_tags(
                'tax_report_compras_activo_fijo_no_recup_tag',
                'tax_report_compras_netas_gr_iva_no_recuperable_tag',
            ),
            'tags_761': get_matching_tags('tax_report_compras_supermercado_tag'),
            'tags_762': get_matching_tags('tax_report_compras_iva_supermercado_tag'),
            'retention_tag': get_matching_tags('tax_report_retencion_total_compras_tag'),
        }

    @api.model
    def _f29_get_aml_query(self, options, date_scope):
        report = self.env['account.report'].browse(options['report_id'])

        domain_query = report._get_report_query(options, date_scope, domain=[
            ('move_id.l10n_latam_document_type_id.code', 'in', (False, '33', '34', '39', '41', '46', '56', '61', '71', '110', '111', '112', '914'))
        ])
        rhs_alias = domain_query.make_alias('account_move_line', 'move')
        condition = SQL("%s = %s", SQL.identifier('account_move_line', 'move_id'), SQL.identifier(rhs_alias, 'id'))
        domain_query.add_join(kind='JOIN', alias=rhs_alias, table='account_move', condition=condition)

        return SQL(
            '''
                SELECT DISTINCT ON (1, 2, 3, 4)
                    account_move_line.id,
                    account_move_line__move.id AS move_id,
                    doc_type.code AS doc_code,
                    CASE
                        -- Pairs relying on strict Base vs Tax definitions
                        WHEN doc_type.code IN ('39', '41') AND account_move_line__move.move_type = 'out_invoice' THEN
                            CASE
                                WHEN %(base_condition)s THEN '110'
                                WHEN %(tax_condition)s THEN '111'
                                ELSE 'OTHER'
                            END

                        WHEN doc_type.code = '33' AND account_move_line__move.move_type = 'out_invoice' THEN
                            CASE
                                WHEN %(base_condition)s THEN '503'
                                WHEN %(tax_condition)s THEN '502'
                                ELSE 'OTHER'
                            END

                        WHEN doc_type.code = '61' AND account_move_line__move.move_type = 'out_refund' THEN
                            CASE
                                WHEN %(base_condition)s THEN '509'
                                WHEN %(tax_condition)s THEN '510'
                                ELSE 'OTHER'
                            END

                        WHEN doc_type.code = '56' AND account_move_line__move.move_type = 'out_invoice' THEN
                            CASE
                                WHEN %(base_condition)s THEN '512'
                                WHEN %(tax_condition)s THEN '513'
                                ELSE 'OTHER'
                            END

                        WHEN doc_type.code = '61' AND account_move_line__move.move_type = 'in_refund' THEN
                            CASE
                                WHEN %(base_condition)s THEN '527'
                                WHEN %(tax_condition)s THEN '528'
                                ELSE 'OTHER'
                            END

                        WHEN doc_type.code = '56' AND account_move_line__move.move_type = 'in_invoice' THEN
                            CASE
                                WHEN %(base_condition)s THEN '531'
                                WHEN %(tax_condition)s THEN '532'
                                ELSE 'OTHER'
                            END

                        WHEN doc_type.code = '914' AND account_move_line__move.move_type = 'in_invoice' THEN
                            CASE
                                WHEN %(base_condition)s THEN '534'
                                WHEN %(tax_condition)s THEN '535'
                                ELSE 'OTHER'
                            END

                        -- Static Grids
                        WHEN doc_type.code IN ('110', '111', '112') AND account_move_line__move.move_type IN ('out_invoice', 'out_refund') THEN '020'
                        WHEN doc_type.code IN ('34', '56', '61') AND account_move_line__move.move_type IN ('out_invoice', 'out_refund') THEN '142'
                        WHEN doc_type.code IN ('34', '56', '61') AND account_move_line__move.move_type IN ('in_invoice', 'in_refund') THEN '562'
                        WHEN doc_type.code IS NULL AND account_move_line__move.move_type IN ('in_invoice', 'in_refund') THEN '566'

                        -- Tag-Dependent Grids
                        WHEN doc_type.code = '71' AND account_move_line__move.move_type = 'in_invoice' AND tag_rel.account_account_tag_id IN %(tags_151)s THEN '151'

                        WHEN doc_type.code IN ('33', '46') AND account_move_line__move.move_type IN ('in_invoice', 'in_refund') THEN
                            CASE
                                WHEN tag_rel.account_account_tag_id IN %(tags_761)s THEN '761'
                                WHEN tag_rel.account_account_tag_id IN %(tags_762)s THEN '762'
                                WHEN tag_rel.account_account_tag_id IN %(tags_519)s THEN '519'
                                WHEN tag_rel.account_account_tag_id IN %(tags_520)s THEN '520'
                                WHEN tag_rel.account_account_tag_id IN %(tags_521)s THEN '521'
                                WHEN tag_rel.account_account_tag_id IN %(tags_564)s THEN '564'
                                WHEN tag_rel.account_account_tag_id IN %(tags_524)s THEN '524'
                                WHEN tag_rel.account_account_tag_id IN %(tags_525)s THEN '525'
                                WHEN tag_rel.account_account_tag_id IN %(tags_039)s AND %(tax_condition)s THEN '039'
                                ELSE 'OTHER'
                            END

                        ELSE 'OTHER'
                    END as grid,
                    %(tax_condition)s AS has_tax,
                    account_move_line.balance,
                    account_move_line.account_id
                FROM %(from_clause)s
                LEFT JOIN account_account_tag_account_move_line_rel tag_rel ON tag_rel.account_move_line_id = account_move_line.id
                LEFT JOIN l10n_latam_document_type doc_type ON doc_type.id = account_move_line__move.l10n_latam_document_type_id
                LEFT JOIN account_account account ON account.id = account_move_line.account_id
                LEFT JOIN account_journal journal ON journal.id = account_move_line__move.journal_id

                WHERE
                    %(where_clause)s
                    AND COALESCE(account_move_line.display_type, '') != 'payment_term'
            ''',
            from_clause=domain_query.from_clause,
            where_clause=domain_query.where_clause,
            base_condition=SQL("account_move_line.display_type IN ('product', 'rounding')"),
            tax_condition=SQL("account_move_line.display_type = 'tax'"),
            **self._get_tag_ids_per_report_grid(),
        )

    def _report_engine_f29_combined(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        query = SQL(
            '''
            WITH
                account_move_line_data AS (%(aml_query)s),
                account_move_data AS (
                    SELECT
                        aml.move_id,
                        aml.grid,
                        aml.doc_code,
                        aml.has_tax AS has_tax,
                        SUM(aml.balance) AS balance,
                        CASE WHEN aml.grid = '020' AND aml.doc_code = '110' THEN 1 ELSE 0 END AS count_020_110,
                        CASE WHEN aml.grid = '020' AND aml.doc_code = '111' THEN 1 ELSE 0 END AS count_020_111,
                        CASE WHEN aml.grid = '020' AND aml.doc_code = '112' THEN -1 ELSE 0 END AS count_020_112,
                        CASE WHEN aml.grid IN ('142', '562') AND aml.doc_code = '34' THEN 1 ELSE 0 END AS count_142_34,
                        CASE WHEN aml.grid IN ('142', '562') AND aml.doc_code = '56' THEN 1 ELSE 0 END AS count_142_56,
                        CASE WHEN aml.grid IN ('142', '562') AND aml.doc_code = '61' THEN 1 ELSE 0 END AS count_142_61
                    FROM account_move_line_data aml
                    GROUP BY 1, 2, 3, 4
                )

            SELECT
                am.grid,
                SUM(
                    CASE
                        WHEN am.grid = '020' THEN am.count_020_110 + am.count_020_111 - am.count_020_112
                        WHEN am.grid IN ('142', '562') THEN
                            am.count_142_34 +
                            CASE WHEN am.has_tax THEN 0 ELSE am.count_142_56 - am.count_142_61 END
                        ELSE 1
                    END
                ) AS count_rows,
                SUM(
                    am.balance * CASE
                        WHEN am.grid = '020' THEN am.count_020_112 - am.count_020_110 - am.count_020_111
                        WHEN am.grid IN ('110', '111', '503', '502', '509', '510', '512', '513', '142', '151') THEN -1
                        ELSE 1
                    END
                ) AS balance
            FROM account_move_data am
            GROUP BY 1
            ''',
            aml_query=self._f29_get_aml_query(options, date_scope),
        )

        self.env.cr.execute(query)
        grid_results = {res['grid']: res for res in self.env.cr.dictfetchall()}

        final_results = {
            'count_rows_111': grid_results.get('111', {}).get('count_rows', 0),
            'base_sum_111': grid_results.get('110', {}).get('balance', 0.0),
            'tax_sum_111': grid_results.get('111', {}).get('balance', 0.0),

            'count_rows_502': grid_results.get('502', {}).get('count_rows', 0),
            'base_sum_502': grid_results.get('503', {}).get('balance', 0.0),
            'tax_sum_502': grid_results.get('502', {}).get('balance', 0.0),

            'count_rows_510': grid_results.get('510', {}).get('count_rows', 0),
            'base_sum_510': grid_results.get('509', {}).get('balance', 0.0),
            'tax_sum_510': grid_results.get('510', {}).get('balance', 0.0),

            'count_rows_513': grid_results.get('513', {}).get('count_rows', 0),
            'base_sum_513': grid_results.get('512', {}).get('balance', 0.0),
            'tax_sum_513': grid_results.get('513', {}).get('balance', 0.0),

            'count_rows_520': grid_results.get('520', {}).get('count_rows', 0),
            'base_sum_520': grid_results.get('519', {}).get('balance', 0.0),
            'tax_sum_520': grid_results.get('520', {}).get('balance', 0.0),

            'count_rows_525': grid_results.get('525', {}).get('count_rows', 0),
            'base_sum_525': grid_results.get('524', {}).get('balance', 0.0),
            'tax_sum_525': grid_results.get('525', {}).get('balance', 0.0),

            'count_rows_528': grid_results.get('528', {}).get('count_rows', 0),
            'base_sum_528': grid_results.get('527', {}).get('balance', 0.0),
            'tax_sum_528': grid_results.get('528', {}).get('balance', 0.0),

            'count_rows_532': grid_results.get('532', {}).get('count_rows', 0),
            'base_sum_532': grid_results.get('531', {}).get('balance', 0.0),
            'tax_sum_532': grid_results.get('532', {}).get('balance', 0.0),

            'count_rows_762': grid_results.get('762', {}).get('count_rows', 0),
            'base_sum_762': grid_results.get('761', {}).get('balance', 0.0),
            'tax_sum_762': grid_results.get('762', {}).get('balance', 0.0),

            'sii_code2_020': None,
            'count_rows_020': grid_results.get('020', {}).get('count_rows', 0),
            'base_sum_020': grid_results.get('020', {}).get('balance', 0.0),
            'tax_sum_020': None,

            'sii_code_039': None,
            'count_rows_039': grid_results.get('039', {}).get('count_rows', 0),
            'base_sum_039': None,
            'tax_sum_039': grid_results.get('039', {}).get('balance', 0.0),

            'sii_code2_142': None,
            'count_rows_142': grid_results.get('142', {}).get('count_rows', 0),
            'base_sum_142': grid_results.get('142', {}).get('balance', 0.0),
            'tax_sum_142': None,

            'count_rows_521': grid_results.get('521', {}).get('count_rows', 0),
            'base_sum_521': grid_results.get('564', {}).get('balance', 0.0),
            'tax_sum_521': grid_results.get('521', {}).get('balance', 0.0),

            'count_rows_535': grid_results.get('535', {}).get('count_rows', 0),
            'base_sum_535': grid_results.get('534', {}).get('balance', 0.0),
            'tax_sum_535': grid_results.get('535', {}).get('balance', 0.0),

            'sii_code2_562': None,
            'count_rows_562': grid_results.get('562', {}).get('count_rows', 0),
            'base_sum_562': grid_results.get('562', {}).get('balance', 0.0),
            'tax_sum_562': None,

            'sii_code2_566': None,
            'count_rows_566': grid_results.get('566', {}).get('count_rows', 0),
            'base_sum_566': grid_results.get('566', {}).get('balance', 0.0),
            'tax_sum_566': None,

            'sii_code_151': None,
            'count_rows_151': grid_results.get('151', {}).get('count_rows', 0),
            'base_sum_151': None,
            'tax_sum_151': grid_results.get('151', {}).get('balance', 0.0),
        }

        return {next(iter(formulas_dict.values())): final_results}

    def _report_engine_doc_089_include(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        expr_xmlids = (
            'tax_report_iva_debito_fiscal_tag', 'tax_report_ventas_netas_gravadas_c_iva_tag',
            'tax_report_compras_iva_recup_tag', 'tax_report_compras_netas_gr_iva_recup_tag',
            'tax_report_compras_iva_activo_fijo_tag', 'tax_report_compras_activo_fijo_tag',
            'tax_report_compras_iva_activo_fijo_uso_comun_tag', 'tax_report_compras_activo_fijo_uso_comun_tag',
            'tax_report_compras_iva_activo_fijo_no_recup_tag', 'tax_report_compras_activo_fijo_no_recup_tag',
            'tax_report_compras_iva_no_recup_tag', 'tax_report_compras_netas_gr_iva_no_recuperable_tag',
            'tax_report_compras_iva_uso_comun_tag', 'tax_report_compras_netas_gr_iva_uso_comun_tag',
            'tax_report_compras_iva_supermercado_tag', 'tax_report_compras_supermercado_tag',
        )

        report_expr = self.env['account.report.expression']
        for xml_id in expr_xmlids:
            report_expr |= self.env.ref(f'l10n_cl.{xml_id}')

        report = self.env['account.report'].browse(options['report_id'])
        query = report._get_report_query(options, date_scope or 'strict', Domain([
            ('move_id.move_type', 'in', ('in_invoice', 'in_refund', 'out_invoice', 'out_refund')),
            ('account_type', '!=', 'liability_payable'),
            ('tax_tag_ids', 'in', report_expr._get_matching_tags().ids),
        ]))

        result = self.env['account.move.line']._read_group([('id', 'in', query)], [], ['balance:sum'])
        tax_sum = result[0][0] if result else 0.0

        return {
            next(iter(formulas_dict.values())): {
                'include_vat': 1 if tax_sum < 0 else 0,
                'C089': '(089)',
            }
        }

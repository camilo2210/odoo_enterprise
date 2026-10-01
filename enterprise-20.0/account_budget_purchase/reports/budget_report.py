# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models
from odoo.tools import SQL


class BudgetReport(models.Model):
    _inherit = 'budget.report'

    line_type = fields.Selection(selection_add=[('committed', 'Committed')])
    committed = fields.Float('Committed', readonly=True)

    def _get_pol_query(self, plan_fnames):
        budget_line_domain = self.env.context.get('budget_line_domain') or []
        precision_digits = self.env['decimal.precision'].precision_get('Product Unit')

        aml_query = self.env['account.move.line'].sudo()._search([('parent_state', '=', 'posted')])
        aml_table = aml_query.table
        aml_query.groupby = aml_table.purchase_line_id
        qty_invoiced_table = aml_query.select(SQL("""
            %(pol_id)s AS pol_id,
            SUM(
                CASE WHEN COALESCE(%(uom_aml)s != %(uom_pol)s, FALSE)
                     THEN ROUND(CAST((%(quantity)s / %(uom_aml_factor)s) * %(uom_pol_factor)s AS NUMERIC), %(precision_digits)s)
                     ELSE COALESCE(%(quantity)s, 0)
                END
                * CASE WHEN %(move_type)s = 'in_invoice' THEN 1
                       WHEN %(move_type)s = 'in_refund' THEN -1
                       ELSE 0 END
            ) AS qty_invoiced""",
            pol_id=aml_table.purchase_line_id,
            move_type=aml_table.move_id.move_type,
            quantity=aml_table.quantity,
            uom_aml=aml_table.product_uom_id, uom_pol=aml_table.purchase_line_id.uom_id,
            uom_aml_factor=aml_table.product_uom_id.factor, uom_pol_factor=aml_table.purchase_line_id.uom_id.factor,
            precision_digits=precision_digits,
        ))

        budget_lines = self.env['budget.line'].sudo().search(budget_line_domain)
        shape2budget_lines = budget_lines._by_shape()

        # Q1 - PO lines matched to a null-company budget line.
        # Q2 - PO lines matched to a company-specific budget line.
        company_conditions = [
            lambda pol_table, bl_table: SQL('%s IS NULL', bl_table.company_id),
            lambda pol_table, bl_table: SQL('%s = %s', pol_table.order_id.company_id, bl_table.company_id),
        ]

        queries = []
        for company_condition in company_conditions:
            for shape, line_ids in shape2budget_lines.items():
                query = self.env['purchase.order.line'].sudo()._search([('order_id.state', '=', 'purchase')])
                pol_table = query.table
                analytic_table = query.table._make_alias('analytic', None)
                query.add_join('JOIN', analytic_table, SQL(
                    """LATERAL (
                        SELECT rate, %(analytic_columns)s
                        FROM JSONB_TO_RECORDSET(%(analytic_json)s) AS x(rate FLOAT, %(field_cast)s)
                    )""",
                    analytic_json=pol_table.analytic_json,
                    analytic_columns=SQL(', ').join(SQL.identifier(fname) for fname in plan_fnames),
                    field_cast=SQL(', ').join(SQL('%s INT', SQL.identifier(fname)) for fname in plan_fnames),
                ), SQL("TRUE"))
                bl_table = self._shape_join('JOIN', analytic_table, 'budget.line', shape, lambda bl_table: SQL(
                    "%(company_condition)s AND date_trunc('day', %(po_date)s) BETWEEN %(bl_date_from)s AND %(bl_date_to)s AND %(bl_id)s = ANY(%(ids)s)",
                    company_condition=company_condition(pol_table, bl_table),
                    po_date=pol_table.order_id.date_order,
                    bl_date_from=bl_table.date_from, bl_date_to=bl_table.date_to,
                    bl_id=bl_table.id, ids=line_ids.ids,
                ))
                query.add_join('LEFT JOIN', 'qty_invoiced_table', SQL("(%s)", qty_invoiced_table), SQL("qty_invoiced_table.pol_id = %s", pol_table.id))
                query.add_where(SQL("%(product_qty)s > COALESCE(qty_invoiced_table.qty_invoiced, 0)", product_qty=pol_table.product_qty))
                query.add_where(SQL("%s != 'revenue'", bl_table.budget_analytic_id.budget_type))
                queries.append(query.select(
                    SQL("(%(id)s::TEXT || '-' || ROW_NUMBER() OVER (PARTITION BY %(id)s ORDER BY %(id)s)) AS id", id=pol_table.id),
                    bl_table.budget_analytic_id,
                    SQL("%s AS budget_line_id", bl_table.id),
                    SQL("'purchase.order' AS res_model"),
                    SQL("%s AS res_id", pol_table.order_id),
                    SQL("%s AS date", pol_table.order_id.date_order),
                    SQL("%s AS description", pol_table.name),
                    pol_table.company_id,
                    pol_table.order_id.user_id,
                    SQL("'committed' AS line_type"),
                    SQL("0 AS budget"),
                    SQL("0 AS liquidation"),
                    SQL("""
                        (
                            COALESCE(%(price_subtotal)s::FLOAT, %(price_unit)s::FLOAT * %(product_qty)s)
                            + COALESCE(%(non_deductible_tax)s::FLOAT, 0.0)
                        ) / COALESCE(NULLIF(%(product_qty)s, 0), 1)
                        * (%(product_qty)s - COALESCE(qty_invoiced_table.qty_invoiced, 0))
                        / %(currency_rate)s
                        * %(analytic_rate)s
                        * CASE WHEN %(budget_type)s = 'both' THEN -1 ELSE 1 END AS committed""",
                        price_subtotal=pol_table.price_subtotal,
                        price_unit=pol_table.price_unit,
                        non_deductible_tax=pol_table.non_deductible_tax,
                        product_qty=pol_table.product_qty,
                        analytic_rate=analytic_table.rate,
                        currency_rate=pol_table.order_id.currency_rate,
                        budget_type=bl_table.budget_analytic_id.budget_type,
                    ),
                    SQL("0 AS achieved"),
                    SQL("0 AS theoretical"),
                    *(analytic_table[fname] for fname in plan_fnames),
                ))

        return SQL(' UNION ALL ').join(queries)

    @property
    def _table_sql(self):
        project_plan, other_plans = self.env['account.analytic.plan']._get_all_plans()
        plan_fnames = [plan._column_name() for plan in project_plan | other_plans]
        return SQL("(%s)", SQL(" UNION ALL ").join(filter(None, (
            super()._table_sql,
            self._get_pol_query(plan_fnames),
        ))))

# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models
from odoo.fields import Domain
from odoo.models import Query, TableSQL
from odoo.tools import SQL


class BudgetReport(models.Model):
    _name = 'budget.report'
    _inherit = ['analytic.plan.fields.mixin']
    _description = "Budget Report"
    _auto = False
    _order = 'date desc'

    date = fields.Date('Date')
    res_model = fields.Char('Model', readonly=True)
    res_id = fields.Many2oneReference('Document', model_field='res_model', readonly=True)
    description = fields.Char('Description', readonly=True)
    company_id = fields.Many2one('res.company', 'Company', readonly=True)
    user_id = fields.Many2one('res.users', 'User', readonly=True)
    line_type = fields.Selection([('budget', 'Budget'), ('achieved', 'Achieved')], 'Type', readonly=True)
    budget = fields.Float('Commitment', readonly=True)
    liquidation = fields.Float('Liquidation', readonly=True)
    achieved = fields.Float('Achieved', readonly=True)
    theoretical = fields.Float(readonly=True)
    budget_analytic_id = fields.Many2one('budget.analytic', 'Budget Analytic', readonly=True)
    budget_line_id = fields.Many2one('budget.line', 'Budget Line', readonly=True)

    def _get_bl_query(self, plan_fnames):
        budget_line_domain = self.env.context.get('budget_line_domain')
        return SQL(
            """
            SELECT CONCAT('bl', bl.id::TEXT) AS id,
                   bl.budget_analytic_id AS budget_analytic_id,
                   bl.id AS budget_line_id,
                   'budget.analytic' AS res_model,
                   bl.budget_analytic_id AS res_id,
                   bl.date_from AS date,
                   ba.name AS description,
                   bl.company_id AS company_id,
                   NULL AS user_id,
                   'budget' AS line_type,
                   bl.budget_amount AS budget,
                   bl.liquidation_amount AS liquidation,
                   0 AS committed,  -- used in `account_budget_purchase`
                   0 AS achieved,
                   CASE WHEN %(today)s BETWEEN bl.date_from AND bl.date_to
                        THEN (((%(today)s::DATE - bl.date_from::DATE + 1)) / (bl.date_to::DATE - bl.date_from::DATE + 1)::FLOAT) * bl.budget_amount
                        WHEN %(today)s < bl.date_from
                        THEN 0
                        ELSE bl.budget_amount
                   END AS theoretical,
                   %(plan_fields)s
              FROM budget_line bl
              JOIN budget_analytic ba ON ba.id = bl.budget_analytic_id
              %(budget_line_condition)s
            """,
            plan_fields=SQL(', ').join(self.env['budget.line']._field_to_sql('bl', fname) for fname in plan_fnames),
            budget_line_condition=SQL('WHERE %s', budget_line_domain._to_sql(TableSQL('bl', self.env['budget.line'], None))) if budget_line_domain else SQL(''),
            today=fields.Date.context_today(self),
        )

    def _get_aal_query(self, plan_fnames):
        budget_line_domain = self.env.context.get('budget_line_domain') or []
        aal_domain = ['|', ('general_account_id', '=', False), ('general_account_id', 'any', [
            '|',
            ('internal_group', 'in', ('income', 'expense')),
            ('account_type', 'in', ('asset_current', 'asset_non_current', 'asset_fixed')),
        ])]

        # For performance reasons, we split the query into 3 parts and then UNION ALL the results
        # (faster than doing a single query with an OR on the left join condition):
        # Q1 - analytic lines with no matching budget line at all.
        # Q2 - analytic lines matched to a null-company budget line.
        # Q3 - analytic lines matched to a company-specific budget line.
        queries = []

        # Group budget lines by the shape of their plan fields to optimize the query
        # For each budget line, we only care which fields are set, not their specific values.
        budget_lines = self.env['budget.line'].sudo().search(budget_line_domain)
        shape2budget_lines = budget_lines._by_shape()

        # Q1 - analytic lines with no matching budget line at all.
        if not budget_line_domain:
            query = self.env['account.analytic.line'].sudo()._search(aal_domain)
            aal_table = query.table
            bl_table = self._shape_join('LEFT JOIN', aal_table, 'budget.line', [], lambda bl_table: SQL("FALSE"))
            # filter it so that we only get the aals that have no bl
            sub_queries = []
            for shape, line_ids in shape2budget_lines.items():
                sub_query = Query(self.env['account.analytic.line'], alias='aal')
                self._shape_join('JOIN', sub_query.table, 'budget.line', shape, lambda sub_bl_table: SQL(
                    "%(aal_date)s BETWEEN %(bl_date_from)s AND %(bl_date_to)s AND %(bl_id)s = ANY(%(ids)s)",
                    aal_date=sub_query.table.date,
                    bl_date_from=sub_bl_table.date_from, bl_date_to=sub_bl_table.date_to,
                    bl_id=sub_bl_table.id, ids=line_ids.ids,
                ))
                sub_queries.append(sub_query.select(SQL("DISTINCT aal.id")))
            if sub_queries:
                query.add_where(SQL(
                    "NOT EXISTS (SELECT 1 FROM (%(union)s) matched_aal WHERE matched_aal.id = %(aal_id)s)",
                    union=SQL(' UNION ALL ').join(sub_queries),
                    aal_id=aal_table.id,
                ))
            queries.append(query.select(*self._get_aal_select(aal_table, bl_table, plan_fnames)))

        # Q2 - analytic lines matched to a null-company budget line.
        # Q3 - analytic lines matched to a company-specific budget line.
        company_conditions = [
            lambda al, bl: SQL('%s IS NULL', bl.company_id),
            lambda al, bl: SQL('%s = %s', al.company_id, bl.company_id),
        ]

        for company_condition in company_conditions:
            for shape, line_ids in shape2budget_lines.items():
                query = self.env['account.analytic.line'].sudo()._search(aal_domain)
                aal_table = query.table
                bl_table = self._shape_join('JOIN', aal_table, 'budget.line', shape, lambda bl_table: SQL(
                    "%(company_condition)s AND %(aal_date)s BETWEEN %(bl_date_from)s AND %(bl_date_to)s AND %(bl_id)s = ANY(%(ids)s)",
                    company_condition=company_condition(aal_table, bl_table),
                    aal_date=aal_table.date,
                    bl_date_from=bl_table.date_from, bl_date_to=bl_table.date_to,
                    bl_id=bl_table.id, ids=line_ids.ids,
                ))
                query.add_where(SQL(
                    """CASE %(budget_type)s
                        WHEN 'expense' THEN ((%(profitability)s) = 'loss')
                        WHEN 'revenue' THEN ((%(profitability)s) = 'revenue')
                        ELSE TRUE
                    END""",
                    profitability=aal_table.analytic_profitability,
                    budget_type=bl_table.budget_analytic_id.budget_type,
                ))
                queries.append(query.select(*self._get_aal_select(aal_table, bl_table, plan_fnames)))

        return SQL(' UNION ALL ').join(queries)

    def _get_aal_select(self, aal_table, bl_table, plan_fnames):
        return [
            SQL("CONCAT('aal', %s::TEXT) AS id", aal_table.id),
            bl_table.budget_analytic_id,
            SQL("%s AS budget_line_id", bl_table.id),
            SQL("'account.analytic.line' AS res_model"),
            SQL("%s AS res_id", aal_table.id),
            SQL("%s AS date", aal_table.date),
            SQL("%s AS description", aal_table.name),
            SQL("%s AS company_id", aal_table.company_id),
            SQL("%s AS user_id", aal_table.user_id),
            SQL("'achieved' AS line_type"),
            SQL("0 AS budget"),
            SQL("0 AS liquidation"),
            SQL("%s * CASE WHEN %s = 'expense' THEN -1 ELSE 1 END AS committed", aal_table.amount, bl_table.budget_analytic_id.budget_type),  # used in `account_budget_purchase`
            SQL("%s * CASE WHEN %s = 'expense' THEN -1 ELSE 1 END AS achieved", aal_table.amount, bl_table.budget_analytic_id.budget_type),
            SQL("0 AS theoretical"),
            *(aal_table[fname] for fname in plan_fnames),
        ]

    @property
    def _table_sql(self):
        project_plan, other_plans = self.env['account.analytic.plan']._get_all_plans()
        plan_fnames = [
            fname
            for plan in project_plan | other_plans
            if (fname := plan._column_name()) in self
        ]
        return SQL("(%s)", SQL(" UNION ALL ").join(filter(None, (
            self._get_bl_query(plan_fnames),
            self._get_aal_query(plan_fnames),
        ))))

    def _search(self, domain, offset=0, limit=None, order=None, *, active_test=True, bypass_access=False):
        budget_line_domain = Domain(domain).map_conditions(lambda cond: (
            cond if cond.field_expr == 'budget_analytic_id'
            else Domain('id', cond.operator, cond.value) if cond.field_expr == 'budget_line_id'
            else fields.Domain.TRUE
        )).optimize_full(self.env['budget.line'])
        return super(BudgetReport, self.with_context(budget_line_domain=budget_line_domain))._search(
            domain, offset=offset, limit=limit, order=order, active_test=active_test, bypass_access=bypass_access,
        )

    def action_open_reference(self):
        self.ensure_one()
        if self.res_model == 'account.analytic.line':
            analytical_line = self.env['account.analytic.line'].browse(self.res_id)
            if analytical_line.move_line_id:
                return analytical_line.move_line_id.action_open_business_doc()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self.res_model,
            'view_mode': 'form',
            'res_id': self.res_id,
        }

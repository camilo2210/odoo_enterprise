from odoo import api, fields, models
from odoo.tools import SQL


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    analytic_coverage = fields.Float(
        string="Analytic Coverage",
        compute='_compute_analytic_coverage',
        compute_sql='_compute_sql_analytic_coverage',
        compute_sudo=True,
    )

    def _compute_sql_analytic_coverage(self, table) -> SQL:
        plan_id = self.env.context.get('selected_analytic_plan')
        if not plan_id:
            return SQL("0.0")

        column_name = self.env['account.analytic.plan'].browse(plan_id)._column_name()
        amount_sql = SQL(
            "CASE WHEN %s = %s THEN %s ELSE 0 END",
            table[column_name].plan_id,
            plan_id,
            table.amount,
        )
        return SQL(
            "COALESCE(-(%(amount)s / NULLIF(%(balance)s, 0)), 0)",
            amount=amount_sql,
            balance=table.move_line_id.balance,
        )

    @api.depends('amount', 'move_line_id.balance', 'auto_account_id')
    def _compute_analytic_coverage(self):
        query = self._search([('id', 'in', self.ids)])
        line2coverage = dict(self.env.execute_query(query.select(
            query.table.id,
            query.table.analytic_coverage,
        )))
        for line in self:
            line.analytic_coverage = line2coverage[line._origin.id]

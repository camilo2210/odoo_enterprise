from odoo import api, fields, models
from odoo.tools import SQL


class AccountMove(models.Model):
    _inherit = 'account.move'

    budget_analytic_ids = fields.Many2many(
        comodel_name='budget.analytic',
        compute='_compute_budget_analytic_ids',
    )

    @api.depends('line_ids.analytic_line_ids')
    def _compute_budget_analytic_ids(self):
        query = self.env['account.analytic.line'].sudo()._search([('id', 'in', self.line_ids.analytic_line_ids.ids)])
        budget_line_alias = self.env['account.analytic.line']._get_budget_line_alias(query, kind='JOIN')
        query.groupby = query.table.move_line_id.move_id
        move2budgets = dict(self.env.execute_query(query.select(
            query.table.move_line_id.move_id,
            SQL("ARRAY_AGG(DISTINCT %s)", budget_line_alias.budget_analytic_id),
        )))
        for move in self:
            move.budget_analytic_ids = move2budgets.get(move._origin.id)

    def action_open_budget(self):
        self.ensure_one()
        return self.budget_analytic_ids._get_records_action(name=self.env._("Budgets"))

from odoo import models
from odoo.tools import SQL


class AccountMove(models.Model):
    _inherit = 'account.analytic.line'

    def _get_budget_line_alias(self, query, alias_name='budget_line', kind='LEFT JOIN'):
        budget_line_alias = query.table._make_alias(alias_name, self.env['budget.line'])
        query.add_join(kind, budget_line_alias, None, condition=SQL(' AND ').join(
            SQL('(%s IS NULL OR %s = %s)', budget_line_alias[fname], budget_line_alias[fname], query.table[fname])
            for fname in self.env['account.analytic.line']._get_plan_fnames()
        ))
        return budget_line_alias

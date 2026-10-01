# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models
from odoo.tools import SQL


class AnalyticPlanFields(models.AbstractModel):
    _inherit = 'analytic.plan.fields.mixin'

    def _by_shape(self):
        plan_fnames = self._get_plan_fnames()
        return self.grouped(lambda r: tuple(bool(r[fname]) for fname in plan_fnames))

    def _shape_join(self, kind, from_table, to_model, shape, additional_condition=None):
        plan_fnames = self._get_plan_fnames()
        to_table = from_table._make_alias('shape', self.env[to_model])
        conditions = [
            SQL("%s = %s", from_table[fname], to_table[fname])
            for fname, is_set in zip(plan_fnames, shape)
            if is_set
        ]
        if additional_condition:
            conditions.append(additional_condition(to_table))
        from_table._query.add_join(kind, to_table, self.env[to_model]._table, SQL(' AND ').join(conditions) or SQL('TRUE'))
        return to_table

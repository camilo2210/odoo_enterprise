# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api
from odoo.tools import SQL


class PlanningAnalysisReport(models.Model):
    _inherit = "planning.analysis.report"

    billable_allocated_hours = fields.Float("Billable Time Allocated", readonly=True, help="Sum of hours allocated to shifts linked to a SOL.")
    non_billable_allocated_hours = fields.Float("Non-billable Time Allocated", readonly=True, help="Sum of hours allocated to shifts not linked to a SOL.")

    @property
    def _table_sql(self):
        return SQL("""
            (SELECT S.*,
                (S.allocated_hours - billable_allocated_hours) AS non_billable_allocated_hours
            FROM %s S)
        """, super()._table_sql)

    @api.model
    def _select(self):
        return SQL("""%s,
            CASE WHEN S.sale_line_id IS NULL THEN 0 ELSE S.allocated_hours END AS billable_allocated_hours
        """, super()._select())

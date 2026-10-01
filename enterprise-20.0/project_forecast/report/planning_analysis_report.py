# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api
from odoo.tools import SQL


class PlanningAnalysisReport(models.Model):
    _inherit = "planning.analysis.report"

    project_id = fields.Many2one("project.project", string="Project", readonly=True)
    task_id = fields.Many2one("project.task", string="Task", readonly=True)

    @api.model
    def _select(self):
        return SQL("""%s,
            S.project_id AS project_id,
            S.task_id AS task_id
        """, super()._select())

    @api.model
    def _group_by(self):
        return SQL("""%s,
            S.project_id,
            S.task_id
        """, super()._group_by())

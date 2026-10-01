# Part of Odoo. See LICENSE file for full copyright and licensing details

from odoo import api, fields, models
from odoo.tools import SQL


class ReportProjectTaskUser(models.Model):
    _inherit = 'report.project.task.user'

    planned_date_begin = fields.Datetime("Start date", readonly=True)

    def _select(self):
        return SQL("""%s,
            t.planned_date_begin
        """, super()._select())

    def _group_by(self):
        return SQL("""%s,
            t.planned_date_begin
        """, super()._group_by())

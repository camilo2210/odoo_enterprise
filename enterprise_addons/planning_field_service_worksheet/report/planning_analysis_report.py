from odoo import api, fields, models
from odoo.tools import SQL


class PlanningAnalysisReport(models.Model):
    _inherit = 'planning.analysis.report'

    worksheet_template_id = fields.Many2one('worksheet.template', 'Worksheet Template', readonly=True)

    @api.model
    def _select(self):
        return SQL("%s, S.worksheet_template_id", super()._select())

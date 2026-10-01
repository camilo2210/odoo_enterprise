from odoo import fields, models
from odoo.tools import SQL


class PlanningAnalysisReport(models.Model):
    _inherit = 'planning.analysis.report'

    under_warranty = fields.Boolean('Under Warranty')

    def _select(self):
        return SQL("%s, S.under_warranty", super()._select())

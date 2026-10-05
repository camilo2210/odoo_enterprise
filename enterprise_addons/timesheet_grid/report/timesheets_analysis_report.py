# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.tools import SQL


class TimesheetsAnalysisReport(models.Model):
    _inherit = "timesheets.analysis.report"

    validated = fields.Boolean("Validated line", aggregator="bool_and", readonly=True)
    validated_status = fields.Selection([('draft', 'Draft'), ('validated', 'Validated')], readonly=True)

    @api.model
    def _select(self):
        return SQL("""%s,
            A.validated AS validated,
            CASE WHEN A.validated THEN 'validated' ELSE 'draft' END AS validated_status
        """, super()._select())

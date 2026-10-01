from odoo import api, fields, models
from odoo.tools import SQL


class TimesheetsAnalysisReport(models.Model):
    _inherit = 'timesheets.analysis.report'

    billing_target = fields.Float(readonly=True)
    billing_time_target = fields.Float(readonly=True)

    @api.model
    def _select(self):
        return SQL("""%s,
            E.billable_time_target AS billing_time_target,
            CASE WHEN A.order_id IS NULL THEN 0 ELSE A.unit_amount END / NULLIF(E.billable_time_target, 0) AS billing_target
        """, super()._select())

    @api.model
    def _from(self):
        return SQL("""%s
            LEFT JOIN hr_employee E ON A.employee_id = E.id
        """, super()._from())

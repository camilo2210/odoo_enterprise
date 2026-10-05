# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.tools import SQL


class HelpdeskSlaReportAnalysis(models.Model):
    _inherit = 'helpdesk.sla.report.analysis'

    remaining_hours_so = fields.Float(
        'Remaining Hours on SO',
        readonly=True,
        aggregator="avg",
        groups="hr_timesheet.group_hr_timesheet_user",
    )
    sale_line_id = fields.Many2one('sale.order.line', string="Sales Order Item", readonly=True)

    def _select(self):
        return SQL("""%s,
            NULLIF(sol.remaining_hours, 0) as remaining_hours_so,
            T.sale_line_id as sale_line_id
        """, super()._select())

    def _group_by(self):
        return SQL("""%s,
            sol.remaining_hours,
            T.sale_line_id
        """, super()._group_by())

    def _from(self):
        return SQL("""%s
            LEFT JOIN sale_order_line sol ON T.sale_line_id = sol.id
        """, super()._from())

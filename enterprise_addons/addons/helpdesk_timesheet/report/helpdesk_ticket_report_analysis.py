# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.tools import SQL


class HelpdeskTicketReportAnalysis(models.Model):
    _inherit = 'helpdesk.ticket.report.analysis'

    total_hours_spent = fields.Float(
        "Hours Spent (Timesheets)",
        readonly=True,
        groups="hr_timesheet.group_hr_timesheet_user",
    )
    employee_parent_id = fields.Many2one('hr.employee', string='Manager', readonly=True)
    department_id = fields.Many2one('hr.department', string='Department', readonly=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', readonly=True)

    def _select(self):
        return SQL("""%s,
            NULLIF(T.total_hours_spent, 0) AS total_hours_spent,
            EMP.parent_id AS employee_parent_id,
            DEP.id AS department_id,
            EMP.id AS employee_id
        """, super()._select())

    def _group_by(self):
        return SQL("""%s,
            DEP.id,
            EMP.parent_id,
            EMP.id,
            T.total_hours_spent
        """, super()._group_by())

    def _from(self):
        return SQL("""%s
            LEFT JOIN res_users U ON T.user_id = U.id
            LEFT JOIN hr_employee EMP ON EMP.user_id = U.id AND T.company_id = EMP.company_id
            LEFT JOIN hr_version VER ON VER.id = EMP.current_version_id
            LEFT JOIN hr_department DEP ON VER.department_id = DEP.id
        """, super()._from())

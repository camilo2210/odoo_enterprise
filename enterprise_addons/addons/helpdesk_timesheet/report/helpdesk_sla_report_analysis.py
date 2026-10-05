# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.tools import SQL


class HelpdeskSlaReportAnalysis(models.Model):
    _inherit = 'helpdesk.sla.report.analysis'

    department_id = fields.Many2one('hr.department', string='Department', readonly=True)
    manager_id = fields.Many2one('hr.employee', string='Manager', readonly=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', readonly=True)
    total_hours_spent = fields.Float(
        "Hours Spent (Timesheets)",
        readonly=True,
        groups="hr_timesheet.group_hr_timesheet_user",
    )

    def _select(self):
        return SQL("""%s,
            DEP.id as department_id,
            EMP.parent_id as manager_id,
            EMP.id as employee_id,
            NULLIF(T.total_hours_spent, 0) AS total_hours_spent
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
            LEFT JOIN "res_users" U on T.user_id = U.id AND U.company_id = T.company_id
            LEFT JOIN "hr_employee" EMP on EMP.user_id = U.id AND EMP.company_id = T.company_id
            LEFT JOIN hr_version VER ON VER.id = EMP.current_version_id
            LEFT JOIN "hr_department" DEP on VER.department_id = DEP.id AND DEP.company_id = T.company_id
        """, super()._from())

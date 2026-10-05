from odoo import models
from odoo.tools import SQL


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    def _get_timesheets_and_billable_working_hours_query(self, employee_ids, from_date, to_date):
        return SQL("""
            SELECT aal.employee_id as employee_id, COALESCE(SUM(aal.unit_amount), 0) as worked_hours
              FROM account_analytic_line aal
             WHERE aal.employee_id IN %s AND date >= %s AND date <= %s AND project_id IS NOT NULL
               AND aal.holiday_id is NULL AND aal.global_leave_id is NULL
               AND aal.billable_type IN ('02_billable_fixed', '04_billable_time', '06_billable_milestones', '08_billable_manual')
          GROUP BY aal.employee_id
        """, tuple(employee_ids), from_date, to_date)

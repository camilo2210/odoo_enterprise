from odoo import models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def action_open_last_month_attendances(self):
        res = super().action_open_last_month_attendances()
        res['views'] = res['views'] + [[self.env.ref('hr_attendance_gantt.hr_attendance_gantt_view_employee_monthly_hours').id, 'gantt']]
        return res

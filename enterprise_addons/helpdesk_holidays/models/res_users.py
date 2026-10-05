import datetime

from odoo import models
from odoo.tools.intervals import Intervals


class ResUsers(models.Model):
    _inherit = 'res.users'

    def _get_working_user_interval(self, start_dt, end_dt, calendar, compute_leaves=True):
        leaves = {}
        if compute_leaves:
            leaves = self.env['hr.leave'].sudo()._get_leave_interval(
                date_from=start_dt.astimezone(datetime.UTC).replace(tzinfo=None),
                date_to=end_dt.astimezone(datetime.UTC).replace(tzinfo=None),
                employee_ids=self.employee_id
            )
        # We do not pass compute_leaves as when True, need to take the non validated leaves into account,
        # which is done by calling _get_leave_interval on hr.leave (as it is not the case in _work_intervals_batch).
        res = super()._get_working_user_interval(start_dt, end_dt, calendar, False)
        for employee in self.sudo().employee_ids:
            intervals = res[employee.resource_id.id]
            employee_leaves = leaves.get(employee.id, [])
            for leave in employee_leaves:
                if intervals:
                    leave_intervals = Intervals([(
                        leave.date_from.replace(tzinfo=datetime.UTC),
                        leave.date_to.replace(tzinfo=datetime.UTC),
                        self.env['hr.leave'])])
                    intervals -= leave_intervals
            res[employee.resource_id.id] = intervals
        return res

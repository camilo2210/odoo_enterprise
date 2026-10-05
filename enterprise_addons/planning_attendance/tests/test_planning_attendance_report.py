# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import datetime

from odoo.addons.planning_attendance.tests.test_common import TestPlanningAttendanceCommon


class TestPlanningAttendanceReport(TestPlanningAttendanceCommon):
    def test_planning_attendance_overlapping_shift(self):
        """
        Checks that when a shift overlaps on 2 days (starts in the evening and ends in the morning), the view displays
        the correct hours for this shift.
        """
        slot = self.env['planning.slot'].create({
            'start_datetime': datetime(2026, 4, 26, 21, 0, 0),
            'end_datetime': datetime(2026, 4, 27, 5, 0, 0),
            'resource_ids': self.flexible_employee.resource_id.ids,
            'allocated_hours': 8,
        })
        slot.action_planning_publish_and_send()
        self.env.flush_all()

        domain = [
            ('employee_id', '=', self.flexible_employee.id),
        ]
        planning_attendance_report = self.env['planning.attendance.analysis.report'].search(domain)
        self.assertEqual(sum(planning_attendance_report.mapped('planned_hours')), 8)
